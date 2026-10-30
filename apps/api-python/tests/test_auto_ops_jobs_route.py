"""Contrato HTTP de la cola ``auto_ops_jobs`` (hermético, sin PostgreSQL).

Cubre: encolar idempotente por día, ``kind``/fecha inválidos (400), fail-closed sin
cuenta (404 ``no_account_scope``), job de otra cuenta indistinguible de inexistente
(404) y listado acotado a la cuenta activa.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_ops_jobs as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app
from bolsa_application.auto_ops_jobs import EnqueueOutcome
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_QUEUED,
    AutoOpsJob,
)


class _FakeSession:
    info: dict[str, Any] = {}

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _FakeJobRepo:
    """Repositorio en memoria con la MISMA idempotencia que el índice parcial."""

    jobs: list[AutoOpsJob] = []
    _seq = 0

    def __init__(self, _session: Any = None) -> None:
        pass

    async def get(self, job_id: str) -> AutoOpsJob | None:
        return next((job for job in self.jobs if job.id == job_id), None)

    async def find_active(
        self, *, kind: str, day: str, account_id: str | None
    ) -> AutoOpsJob | None:
        for job in self.jobs:
            if (
                job.kind == kind
                and job.day == day
                and job.account_id == account_id
                and job.status in (JOB_STATUS_QUEUED, "running")
            ):
                return job
        return None

    async def enqueue(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AutoOpsJob:
        outcome = await self.enqueue_with_outcome(
            kind=kind, day=day, account_id=account_id, payload=payload
        )
        return outcome.job

    async def enqueue_with_outcome(
        self,
        *,
        kind: str,
        day: str,
        account_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        existing = await self.find_active(kind=kind, day=day, account_id=account_id)
        if existing is not None:
            return EnqueueOutcome(job=existing, created=False)
        type(self)._seq += 1
        job = AutoOpsJob(
            id=f"job-{type(self)._seq}",
            kind=kind,
            status=JOB_STATUS_QUEUED,
            day=day,
            account_id=account_id,
            payload=dict(payload or {}),
            created_at="2026-10-18T20:00:00+00:00",
        )
        self.jobs.append(job)
        return EnqueueOutcome(job=job, created=True)

    async def list_for_account(
        self, *, account_id: str | None, kind: str | None = None, limit: int = 20
    ) -> list[AutoOpsJob]:
        rows = [j for j in self.jobs if j.account_id == account_id]
        if kind is not None:
            rows = [j for j in rows if j.kind == kind]
        return rows[:limit]

    async def list_for_day(
        self, *, kind: str, day: str, account_id: str | None, limit: int = 20
    ) -> list[AutoOpsJob]:
        rows = [
            j
            for j in self.jobs
            if j.kind == kind and j.day == day and j.account_id == account_id
        ]
        return rows[:limit]


def _app(scope: str | None, monkeypatch: pytest.MonkeyPatch, *, reset: bool = True):  # noqa: ANN202
    if reset:
        _FakeJobRepo.jobs = []
        _FakeJobRepo._seq = 0
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    monkeypatch.setattr(route, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    return app


async def _request(app, method: str, path: str, **kwargs: Any):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, f"/api{path}", **kwargs)


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_per_day(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app("acc-1", monkeypatch)
    body = {"kind": JOB_KIND_ESTUDIO_DAILY, "day": "2026-10-18"}

    first = await _request(app, "POST", "/auto/ops-jobs", json=body)
    second = await _request(app, "POST", "/auto/ops-jobs", json=body)

    assert first.status_code == 200
    assert first.json()["status"] == JOB_STATUS_QUEUED
    assert first.json()["accountId"] == "acc-1"
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_completed_job_frees_the_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app("acc-1", monkeypatch)
    body = {"kind": JOB_KIND_ESTUDIO_DAILY, "day": "2026-10-18"}
    created = (await _request(app, "POST", "/auto/ops-jobs", json=body)).json()

    _FakeJobRepo.jobs[0] = AutoOpsJob(
        id=created["id"],
        kind=JOB_KIND_ESTUDIO_DAILY,
        status=JOB_STATUS_COMPLETED,
        day="2026-10-18",
        account_id="acc-1",
    )
    again = await _request(app, "POST", "/auto/ops-jobs", json=body)

    assert again.status_code == 200
    assert again.json()["id"] != created["id"]


@pytest.mark.asyncio
async def test_without_scope_enqueue_and_read_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(None, monkeypatch)

    created = await _request(
        app,
        "POST",
        "/auto/ops-jobs",
        json={"kind": JOB_KIND_ESTUDIO_DAILY, "day": "2026-10-18"},
    )
    read = await _request(app, "GET", "/auto/ops-jobs/job-1")

    assert created.status_code == 404
    assert "no_account_scope" in created.json()["detail"]
    assert read.status_code == 404


@pytest.mark.asyncio
async def test_invalid_kind_and_future_replay_are_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app("acc-1", monkeypatch)

    bad_kind = await _request(
        app, "POST", "/auto/ops-jobs", json={"kind": "nope", "day": "2026-10-18"}
    )
    future = await _request(
        app,
        "POST",
        "/auto/ops-jobs",
        json={"kind": "dia_d_replay", "day": "2999-01-01"},
    )

    assert bad_kind.status_code == 400
    assert "kind inválido" in bad_kind.json()["detail"]
    assert future.status_code == 400
    assert "fecha futura" in future.json()["detail"]


@pytest.mark.asyncio
async def test_other_account_job_is_indistinguishable_from_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app("acc-1", monkeypatch)
    created = (
        await _request(
            app,
            "POST",
            "/auto/ops-jobs",
            json={"kind": JOB_KIND_ESTUDIO_DAILY, "day": "2026-10-18"},
        )
    ).json()

    own = await _request(app, "GET", f"/auto/ops-jobs/{created['id']}")
    assert own.status_code == 200

    other = _app("acc-2", monkeypatch, reset=False)
    stolen = await _request(other, "GET", f"/auto/ops-jobs/{created['id']}")
    missing = await _request(other, "GET", "/auto/ops-jobs/does-not-exist")

    assert stolen.status_code == 404
    assert missing.status_code == 404
    assert stolen.json()["detail"] == missing.json()["detail"] == "job_not_found"


@pytest.mark.asyncio
async def test_listing_is_scoped_to_the_active_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app("acc-1", monkeypatch)
    await _request(
        app,
        "POST",
        "/auto/ops-jobs",
        json={"kind": JOB_KIND_ESTUDIO_DAILY, "day": "2026-10-18"},
    )

    own = await _request(app, "GET", "/auto/ops-jobs")
    other = await _request(
        _app("acc-2", monkeypatch, reset=False), "GET", "/auto/ops-jobs"
    )

    assert len(own.json()["jobs"]) == 1
    assert other.json()["jobs"] == []


@pytest.mark.asyncio
async def test_slot_declares_server_truth_for_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El hueco `(kind, cuenta, día)` lo declara el SERVIDOR: la UI no infiere por payload."""
    app = _app("acc-1", monkeypatch)
    kind = "dia_d_value_replay"
    day = "2026-10-16"

    mine = (
        await _request(
            app,
            "POST",
            "/auto/ops-jobs",
            json={"kind": kind, "day": day, "payload": {"symbol": "AAA"}},
        )
    ).json()
    # D-4 — el hueco estaba LIBRE: el servidor encoló de verdad y lo declara.
    assert mine["slot"]["state"] == "free"
    assert mine["slot"]["matchesRequest"] is True
    assert mine["slot"]["activeSymbol"] == "AAA"
    assert "quedó encolado para AAA" in mine["slot"]["message"]
    # Encolado ≠ iniciado: el mensaje no puede afirmar que ya empezó.
    assert "iniciada" not in mine["slot"]["message"]

    # El MISMO valor: el servidor ya no encola nada y devuelve el job activo.
    same = (
        await _request(
            app,
            "POST",
            "/auto/ops-jobs",
            json={"kind": kind, "day": day, "payload": {"symbol": "AAA"}},
        )
    ).json()
    assert same["id"] == mine["id"]
    assert same["slot"]["state"] == "active_same_request"
    assert same["slot"]["matchesRequest"] is True
    assert "aún no iniciada" in same["slot"]["message"]

    # Otro valor del MISMO día: el servidor devuelve el job activo y declara el choque.
    other = (
        await _request(
            app,
            "POST",
            "/auto/ops-jobs",
            json={"kind": kind, "day": day, "payload": {"symbol": "BBB"}},
        )
    ).json()
    assert other["id"] == mine["id"]
    slot = other["slot"]
    assert slot["state"] == "active_other_symbol"
    assert slot["matchesRequest"] is False
    assert slot["activeSymbol"] == "AAA"
    assert slot["requestedSymbol"] == "BBB"
    assert slot["activeJobId"] == mine["id"]
    # El símbolo pedido NO quedó pendiente: la petición se descartó.
    assert "NO se ha encolado" in slot["message"]
    assert "queda pendiente" not in slot["message"]
