"""Planificador de verificación periódica (ADR-050) — gates y ventanas de época.

Hermético: se sustituyen repositorios y caso de uso; no hay PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.strategy_verification_scheduler as scheduler


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
        strategy_verification_enabled=False,
        strategy_verification_every_days=30,
        strategy_verification_rolling_enabled=True,
        strategy_verification_rolling_lookback_days=1,
        strategy_verification_interval_seconds=3600.0,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: SimpleNamespace,
    account_id: str | None = "acc-1",
    runs: list[Any] | None = None,
    universe: tuple[str, ...] = ("AAA",),
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class _AccountRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def resolve_default_account_for_owner(self) -> str | None:
            return account_id

    class _VerificationRepo:
        def __init__(self, _session: Any) -> None:
            pass

        async def list_runs(self, **kwargs: Any) -> tuple[Any, ...]:
            captured["list_runs"] = kwargs
            return tuple(runs or [])

    async def _universe(_session: Any, *, account_id: str, day: str) -> tuple[str, ...]:
        captured["universe"] = {"accountId": account_id, "day": day}
        return universe

    class _JobRepo:
        def __init__(self, _session: Any) -> None:
            pass

    class _Enqueue:
        def __init__(self, _repo: Any) -> None:
            pass

        async def execute(self, **kwargs: Any) -> Any:
            captured["enqueue"] = kwargs
            return SimpleNamespace(id="job-v1")

    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler, "SqlAlchemyAccountRepository", _AccountRepo)
    monkeypatch.setattr(scheduler, "SqlAlchemyStrategyVerificationRepository", _VerificationRepo)
    monkeypatch.setattr(scheduler, "SqlAlchemyAutoOpsJobRepository", _JobRepo)
    monkeypatch.setattr(scheduler, "EnqueueAutoOpsJob", _Enqueue)
    monkeypatch.setattr(scheduler, "resolve_declared_universe", _universe)
    captured["factory"] = _Factory()
    return captured


def test_window_without_previous_runs_measures_the_last_complete_epoch() -> None:
    window = scheduler._next_epoch_window(
        last_to=None, today=date(2026, 9, 30), every_days=30
    )
    assert window == (date(2026, 8, 31), date(2026, 9, 30))


def test_window_waits_until_the_epoch_closes() -> None:
    assert (
        scheduler._next_epoch_window(
            last_to=date(2026, 9, 20), today=date(2026, 10, 1), every_days=30
        )
        is None
    )


def test_next_window_starts_where_the_last_one_ended() -> None:
    assert scheduler._next_epoch_window(
        last_to=date(2026, 8, 31), today=date(2026, 10, 15), every_days=30
    ) == (date(2026, 8, 31), date(2026, 9, 30))


@pytest.mark.asyncio
async def test_off_by_default_does_not_open_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(monkeypatch, settings=_settings())

    result = await scheduler.enqueue_due_verification_epochs(captured["factory"])

    assert result == []
    assert captured["factory"].opened == 0
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_enabled_enqueues_the_epoch_with_declared_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch, settings=_settings(strategy_verification_enabled=True)
    )

    result = await scheduler.enqueue_due_verification_epochs(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result == ["job-v1"]
    enqueued = captured["enqueue"]
    assert enqueued["kind"] == "dia_d_as_run"
    assert enqueued["day"] == "2026-08-31"
    assert enqueued["payload"]["to"] == "2026-09-30"
    assert enqueued["payload"]["universeInstruments"] == ["AAA"]
    assert enqueued["payload"]["verifyBars"] is True
    assert enqueued["payload"]["verificationKind"] == "epoch"
    assert captured["universe"]["day"] == "2026-08-31"
    assert captured["factory"].sessions[0].committed is True


@pytest.mark.asyncio
async def test_recent_epoch_does_not_enqueue_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch,
        settings=_settings(strategy_verification_enabled=True),
        runs=[SimpleNamespace(to_day="2026-09-20")],
    )

    result = await scheduler.enqueue_due_verification_epochs(
        captured["factory"], now=datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )

    assert result == []
    assert "enqueue" not in captured


@pytest.mark.asyncio
async def test_without_account_nothing_is_enqueued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install(
        monkeypatch,
        settings=_settings(strategy_verification_enabled=True),
        account_id=None,
    )

    result = await scheduler.enqueue_due_verification_epochs(captured["factory"])

    assert result == []
    assert "enqueue" not in captured


def test_starter_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "get_settings", lambda: _settings())

    assert scheduler.start_strategy_verification_scheduler(_Factory()) is None
