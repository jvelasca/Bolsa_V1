"""Contrato HTTP de ``GET /auto/estudio-daily`` (hermético, sin PostgreSQL).

Read-only sobre la cola: el parte sale del ``result`` durable del job. Cubre:
sin job del día (``report = null``, no un cero), job completado con parte, job
fallido con motivo, y fail-closed por cuenta (sin cuenta ⇒ ``no_account_scope``).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_estudio_daily as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    AutoOpsJob,
)


class _FakeSession:
    info: dict[str, Any] = {}

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _FakeJobRepo:
    jobs: list[AutoOpsJob] = []

    def __init__(self, _session: Any = None) -> None:
        pass

    async def list_for_day(
        self, *, kind: str, day: str, account_id: str | None, limit: int = 20
    ) -> list[AutoOpsJob]:
        return [
            j
            for j in self.jobs
            if j.kind == kind and j.day == day and j.account_id == account_id
        ][:limit]

    async def list_for_account(
        self, *, account_id: str | None, kind: str | None = None, limit: int = 20
    ) -> list[AutoOpsJob]:
        rows = [j for j in self.jobs if j.account_id == account_id]
        if kind is not None:
            rows = [j for j in rows if j.kind == kind]
        return rows[:limit]


def _app(scope: str | None, monkeypatch: pytest.MonkeyPatch, jobs: list[AutoOpsJob]):  # noqa: ANN202
    _FakeJobRepo.jobs = list(jobs)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    monkeypatch.setattr(route, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    return app


async def _get(app, path: str):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(f"/api{path}")


def _job(**overrides: Any) -> AutoOpsJob:
    base: dict[str, Any] = {
        "id": "job-1",
        "kind": JOB_KIND_ESTUDIO_DAILY,
        "status": JOB_STATUS_COMPLETED,
        "day": "2026-10-18",
        "account_id": "acc-1",
    }
    base.update(overrides)
    return AutoOpsJob(**base)


@pytest.mark.asyncio
async def test_without_job_the_report_is_null_not_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app("acc-1", monkeypatch, [])
    body = (await _get(app, "/auto/estudio-daily?asOf=2026-10-18")).json()

    assert body["asOf"] == "2026-10-18"
    assert body["report"] is None
    assert body["job"] is None
    assert "no_job_for_day" in body["notes"]


@pytest.mark.asyncio
async def test_completed_job_exposes_the_durable_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {
        "asOf": "2026-10-18",
        "accountId": "acc-1",
        "status": "ok",
        "scannedCount": 1,
        "counts": {"ok": 1, "no_signal": 0, "no_plan": 0, "error": 0},
        "values": [{"instrumentId": "inst-1", "status": "ok", "plan": {"entry": 100.0}}],
        "notes": [],
        "countsConsistent": True,
    }
    app = _app(
        "acc-1",
        monkeypatch,
        [_job(result=report, progress={"phase": "done", "percent": 100})],
    )
    body = (await _get(app, "/auto/estudio-daily?asOf=2026-10-18")).json()

    assert body["report"] == report
    assert body["job"]["status"] == JOB_STATUS_COMPLETED
    assert body["job"]["progress"]["percent"] == 100
    assert body["latestJob"]["id"] == "job-1"


@pytest.mark.asyncio
async def test_failed_job_declares_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(
        "acc-1",
        monkeypatch,
        [
            _job(
                status=JOB_STATUS_FAILED,
                error="Universo ESTUDIO no disponible",
                result={"status": "unavailable", "notes": ["universo no disponible"]},
            )
        ],
    )
    body = (await _get(app, "/auto/estudio-daily?asOf=2026-10-18")).json()

    assert body["job"]["status"] == JOB_STATUS_FAILED
    assert any("job_failed" in note for note in body["notes"])
    assert body["report"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_other_account_does_not_see_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app("acc-2", monkeypatch, [_job()])
    body = (await _get(app, "/auto/estudio-daily?asOf=2026-10-18")).json()

    assert body["report"] is None
    assert body["job"] is None
    assert body["latestJob"] is None


@pytest.mark.asyncio
async def test_without_scope_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(None, monkeypatch, [_job()])
    body = (await _get(app, "/auto/estudio-daily?asOf=2026-10-18")).json()

    assert body["accountId"] is None
    assert body["report"] is None
    assert body["notes"] == ["no_account_scope"]
