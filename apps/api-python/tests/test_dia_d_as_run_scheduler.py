"""Cron DÍA-D as-run (ADR-049) — gate OFF por defecto y dedupe durable.

Hermético: se sustituyen los repositorios y el caso de uso; no hay PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.dia_d_as_run_scheduler as scheduler


class _Session:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _Factory:
    def __init__(self) -> None:
        self.sessions: list[_Session] = []
        self.opened = 0

    def __call__(self) -> _Session:
        self.opened += 1
        session = _Session()
        self.sessions.append(session)
        return session


def _settings(**overrides: Any) -> SimpleNamespace:
    base = SimpleNamespace(
        dia_d_as_run_scheduled=False,
        dia_d_as_run_lookback_days=1,
        dia_d_as_run_interval_seconds=3600.0,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: SimpleNamespace,
    account_id: str | None = "acc-1",
    existing: list[Any] | None = None,
    enqueued: str = "job-9",
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class _AccountRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def resolve_default_account_for_owner(self) -> str | None:
            return account_id

    class _JobRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def list_for_day(self, **kwargs: Any) -> list[Any]:
            captured["list_for_day"] = kwargs
            return list(existing or [])

    class _Enqueue:
        def __init__(self, _repo: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:
            captured["enqueue"] = kwargs
            return SimpleNamespace(id=enqueued)

    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler, "SqlAlchemyAccountRepository", _AccountRepo)
    monkeypatch.setattr(scheduler, "SqlAlchemyAutoOpsJobRepository", _JobRepo)
    monkeypatch.setattr(scheduler, "EnqueueAutoOpsJob", _Enqueue)
    captured["factory"] = _Factory()
    return captured


@pytest.mark.asyncio
async def test_off_by_default_does_not_even_open_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(monkeypatch, settings=_settings())

    result = await scheduler.enqueue_daily_dia_d_as_run(captured["factory"])

    assert result is None
    assert captured["factory"].opened == 0
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_enabled_enqueues_the_previous_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch, settings=_settings(dia_d_as_run_scheduled=True)
    )

    result = await scheduler.enqueue_daily_dia_d_as_run(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result == "job-9"
    enqueued = captured["enqueue"]
    assert enqueued["kind"] == "dia_d_as_run"
    assert enqueued["day"] == "2026-09-29"
    assert enqueued["account_id"] == "acc-1"
    assert enqueued["payload"]["enqueuedBy"] == "scheduler"
    assert captured["factory"].sessions[0].committed is True


@pytest.mark.asyncio
async def test_completed_job_is_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch,
        settings=_settings(dia_d_as_run_scheduled=True),
        existing=[SimpleNamespace(status="completed")],
    )

    result = await scheduler.enqueue_daily_dia_d_as_run(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result is None
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_failed_attempts_are_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch,
        settings=_settings(dia_d_as_run_scheduled=True),
        existing=[SimpleNamespace(status="failed")] * scheduler._MAX_ATTEMPTS_PER_DAY,
    )

    result = await scheduler.enqueue_daily_dia_d_as_run(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result is None
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_without_account_nothing_is_enqueued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch,
        settings=_settings(dia_d_as_run_scheduled=True),
        account_id=None,
    )

    result = await scheduler.enqueue_daily_dia_d_as_run(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result is None
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_starter_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "get_settings", lambda: _settings())

    assert scheduler.start_dia_d_as_run_scheduler(_Factory()) is None
