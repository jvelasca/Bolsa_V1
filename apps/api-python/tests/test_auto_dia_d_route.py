"""DÍA-D AUTO — contratos HTTP de la ruta read-only (fail-closed, sin PG).

La ruta solo LEE artefactos JSON; el motor AUTO se ejercita por CLI, nunca por HTTP. Por eso
estos tests no necesitan PostgreSQL: monkeypatchean la resolución de cuenta (aislamiento) y
apuntan el directorio de artefactos a un ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d as route
from bolsa_api.main import create_app


def _artifact(day: str, account: str = "acc") -> dict:
    return {
        "schemaVersion": "dia-d-auto-v1",
        "kind": "DIA_D_AUTO",
        "readOnly": True,
        "day": day,
        "meta": {"account": account, "versionA": "v1"},
        "comparison": [
            {
                "step": "SIGNAL",
                "declared": 1,
                "executed": 1,
                "verdict": "MATCH",
                "measurement": "COMPLETE",
            },
            {
                "step": "FILL",
                "declared": 2,
                "executed": None,
                "verdict": "NOT_MEASURED",
                "measurement": "UNKNOWN",
            },
        ],
        "summary": {"verdict": "PARTIAL", "match": 1, "divergent": 0, "notMeasured": 1, "steps": 2},
        "oos": {
            "closedCount": 1,
            "openCount": 0,
            "realizedRTotal": 1.5,
            "unmeasuredCount": 0,
            "realized": [],
            "open": [],
        },
        "limits": ["sandbox read-only"],
        "executedDetail": {"day": day, "fills": 1},
    }


@pytest.fixture
def app():
    return create_app()


def _write(tmp_path, day: str, account: str = "acc") -> None:
    (tmp_path / f"dia-d-auto-{day}.json").write_text(
        json.dumps(_artifact(day, account)), encoding="utf-8"
    )


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_list_returns_available_days_descending(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-29")
    _write(tmp_path, "2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay")

    assert response.status_code == 200
    body = response.json()
    assert body["readOnly"] is True
    assert body["days"] == ["2026-09-30", "2026-09-29"]


@pytest.mark.asyncio
async def test_get_returns_the_artifact_projection(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["day"] == "2026-09-30"
    assert body["summary"]["verdict"] == "PARTIAL"
    assert [row["step"] for row in body["steps"]] == ["SIGNAL", "FILL"]
    assert body["oos"]["realizedRTotal"] == 1.5
    assert body["notes"] == []


@pytest.mark.asyncio
async def test_get_missing_artifact_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["artifact_not_found"]


@pytest.mark.asyncio
async def test_no_account_scope_is_fail_closed(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30")

    async def _no_scope(_request, _account_id):
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)
    detail = await _get(app, "/api/auto/dia-d-replay/2026-09-30")
    listing = await _get(app, "/api/auto/dia-d-replay")

    assert detail.status_code == 200
    assert detail.json()["available"] is False
    assert detail.json()["notes"] == ["no_account_scope"]
    assert listing.json()["days"] == []
    assert listing.json()["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_invalid_day_is_declared(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/not-a-day")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["invalid_day"]


@pytest.mark.asyncio
async def test_account_mismatch_is_declared_as_a_note(app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _write(tmp_path, "2026-09-30", account="otra-cuenta")

    async def _scope(_request, _account_id):
        return "acc"

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    response = await _get(app, "/api/auto/dia-d-replay/2026-09-30")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert "account_scope_mismatch" in body["notes"]
