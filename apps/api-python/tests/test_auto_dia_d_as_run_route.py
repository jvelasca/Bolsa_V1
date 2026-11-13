"""DÍA-D as-run — contratos HTTP (read-only, fail-closed por cuenta, sin PostgreSQL).

La lectura solo sirve JSON; el replay se ejecuta por cola/CLI, nunca por HTTP. Estos tests
monkeypatchean la resolución de cuenta y apuntan ``DIA_D_AS_RUN_DIR`` a ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d as route
from bolsa_api.main import create_app
from bolsa_application.dia_d_artifacts import as_run_artifact_path_in


def _artifact(day: str, account: str = "acc") -> dict:
    return {
        "engine": "dia-d-as-run-v1",
        "day": day,
        "account": account,
        "status": "measured",
        "measured": True,
        "costBps": 32.0,
        "startingState": {"legs": 1, "instruments": ["AAA"], "cashOnly": False},
        "arms": [
            {
                "arm": "as_run",
                "measured": True,
                "reason": None,
                "realizedR": 1.25,
                "pnlCurrency": 100.0,
                "maeR": -0.4,
                "mfeR": 2.0,
                "capture": 0.62,
                "exits": 1,
                "stops": 0,
                "targets": 1,
                "legs": 1,
                "reasonCodes": [],
            },
            {
                "arm": "candidate",
                "measured": False,
                "reason": "candidate_not_provided",
                "realizedR": None,
                "pnlCurrency": None,
                "maeR": None,
                "mfeR": None,
                "capture": None,
                "exits": 0,
                "stops": 0,
                "targets": 0,
                "legs": 0,
                "reasonCodes": [],
            },
        ],
        "gaps": [{"arm": "candidate", "reason": "candidate_not_provided"}],
        "hash": "abc",
        "meta": {"account": account, "bump": "v2.11.201", "stateSource": "sim_auto_positions"},
    }


@pytest.fixture
def app():
    return create_app()


def _write(tmp_path, day: str, account: str = "acc") -> None:
    path = as_run_artifact_path_in(tmp_path, day, account)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_artifact(day, account)), encoding="utf-8")


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.fixture
def scoped(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("DIA_D_AS_RUN_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    return tmp_path


@pytest.mark.asyncio
async def test_list_returns_available_days_descending(app, scoped) -> None:
    _write(scoped, "2026-09-29")
    _write(scoped, "2026-09-30")

    response = await _get(app, "/api/auto/dia-d-as-run")

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == ["2026-09-30", "2026-09-29"]
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_list_without_artifacts_declares_it(app, scoped) -> None:
    response = await _get(app, "/api/auto/dia-d-as-run")
    body = response.json()
    assert body["days"] == []
    assert body["notes"] == ["no_artifacts"]


@pytest.mark.asyncio
async def test_get_returns_arms_gaps_and_keeps_unmeasured_as_null(app, scoped) -> None:
    _write(scoped, "2026-09-30")

    response = await _get(app, "/api/auto/dia-d-as-run/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["readOnly"] is True
    assert body["day"] == "2026-09-30"
    assert body["costBps"] == 32.0
    assert body["hash"] == "abc"
    assert body["startingState"]["instruments"] == ["AAA"]
    assert body["gaps"] == [{"arm": "candidate", "reason": "candidate_not_provided"}]

    as_run = next(arm for arm in body["arms"] if arm["arm"] == "as_run")
    candidate = next(arm for arm in body["arms"] if arm["arm"] == "candidate")
    assert as_run["realizedR"] == 1.25
    # Un hueco NO se rellena con 0: el brazo no medido devuelve null con motivo.
    assert candidate["measured"] is False
    assert candidate["realizedR"] is None
    assert candidate["reason"] == "candidate_not_provided"


@pytest.mark.asyncio
async def test_get_missing_day_is_fail_closed(app, scoped) -> None:
    response = await _get(app, "/api/auto/dia-d-as-run/2026-09-30")
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]
    assert body["arms"] == []


@pytest.mark.asyncio
async def test_get_invalid_day_is_declared(app, scoped) -> None:
    response = await _get(app, "/api/auto/dia-d-as-run/30-09-2026")
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["invalid_day"]


@pytest.mark.asyncio
async def test_get_never_serves_another_accounts_artifact(app, scoped) -> None:
    _write(scoped, "2026-09-30", account="otra")
    response = await _get(app, "/api/auto/dia-d-as-run/2026-09-30")
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_get_without_account_scope_is_fail_closed(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DIA_D_AS_RUN_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30")

    async def _scope(_request, _account_id):
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-as-run/2026-09-30")
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_post_enqueues_the_as_run_job(app, scoped, monkeypatch) -> None:
    captured: dict = {}

    class _Outcome:
        created = True
        job = type(
            "Job",
            (),
            {"id": "job-9", "kind": "dia_d_as_run", "status": "queued", "day": "2026-09-30"},
        )()

    class _UseCase:
        def __init__(self, _repo) -> None:
            pass

        async def execute_with_outcome(self, **kwargs):
            captured.update(kwargs)
            return _Outcome()

    class _Session:
        async def commit(self) -> None:
            return None

    monkeypatch.setattr(route, "EnqueueAutoOpsJob", _UseCase)
    monkeypatch.setattr(route, "SqlAlchemyAutoOpsJobRepository", lambda _s: None)
    app.dependency_overrides[route.get_db_session] = lambda: _Session()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auto/dia-d-as-run",
            json={"day": "2026-09-30", "to": "2026-10-15", "costBps": 41},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": "job-9",
        "kind": "dia_d_as_run",
        "status": "queued",
        "day": "2026-09-30",
        "created": True,
    }
    assert captured["kind"] == "dia_d_as_run"
    assert captured["account_id"] == "acc"
    assert captured["day"] == "2026-09-30"
    assert captured["payload"] == {"to": "2026-10-15", "costBps": 41.0}
