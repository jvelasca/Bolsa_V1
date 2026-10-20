"""Contrato HTTP de ``GET /auto/estudio-chain`` (hermético, sin PostgreSQL).

La ruta es read-only y reutiliza el lector durable. Estos tests fijan lo que NO puede
cambiar sin declararlo:

* un valor con ciclo completo publica las NUEVE etapas y la conciliación de P&L;
* una etapa sin traza viaja ``None`` (hueco) y **nunca** ``0``;
* un valor sin ciclos declara ``measured = false`` / ``cycles = []`` (no se fabrica);
* la identidad de estrategia del valor no se inventa (única o AMBIGUA declarada);
* fail-closed por cuenta: sin cuenta no se lee nada; el artefacto de otra cuenta no se ve;
* un fallo de lectura es un **error declarado**, nunca una lista vacía.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_estudio_chain as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.main import create_app


class _FakeSession:
    """Sesión mínima: la ruta no escribe y los lectores están doblados por los tests."""

    info: dict[str, Any] = {}

    async def commit(self) -> None:  # pragma: no cover — la ruta es read-only.
        return None

    async def rollback(self) -> None:  # pragma: no cover — la ruta es read-only.
        return None


def _app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    scope: str | None = "acc-1",
    estudio: dict[str, Any] | None = None,
    read: dict[str, Any] | None = None,
    boom: Exception | None = None,
):  # noqa: ANN202
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: _FakeSession()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    async def _resolve(_session: Any) -> dict[str, Any]:  # noqa: ANN202
        return dict(estudio or {"status": "ok", "instrumentIds": ["i-1", "i-2"]})

    async def _read(_session: Any, _account: str, **_kwargs: Any) -> dict[str, Any]:  # noqa: ANN202
        if boom is not None:
            raise boom
        return dict(read or {"cycles": [], "bestScored": None, "top3": None, "diaDByCycle": {}})

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)
    monkeypatch.setattr(route, "_resolve_estudio", _resolve)
    monkeypatch.setattr(route, "read_estudio_chain_evidence", _read)
    return app


async def _get(app, path: str):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(f"/api{path}")


def _complete_cycle() -> dict[str, Any]:
    """Ciclo con las nueve etapas REACHED y P&L conciliado al quantum del dinero."""
    steps = [
        {"id": step, "state": "reached", "facts": []}
        for step in (
            "SIGNAL",
            "TOP_N",
            "RISK",
            "RESERVATION",
            "ORDER",
            "FILL",
            "PROTECTION",
            "SETTLEMENT",
            "CYCLE_CLOSED",
        )
    ]
    for step in steps:
        if step["id"] == "TOP_N":
            step["facts"] = [
                {"key": "rank", "value": 1},
                {"key": "score", "value": 0.71},
            ]
        if step["id"] == "SETTLEMENT":
            step["facts"] = [{"key": "pnl", "value": "12.500000"}]
        if step["id"] == "CYCLE_CLOSED":
            step["facts"] = [{"key": "pnl", "value": "12.500000"}]
    return {
        "cycleId": "cyc-1",
        "instrumentId": "i-1",
        "direction": "long",
        "closed": True,
        "strategyPresetKey": "preset-alpha",
        "strategyVersion": "v7",
        "steps": steps,
    }


@pytest.mark.asyncio
async def test_complete_chain_is_projected_with_nine_steps(monkeypatch) -> None:
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [_complete_cycle()], "bestScored": None, "top3": None, "diaDByCycle": {}},
    )
    response = await _get(app, "/auto/estudio-chain")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["readOnly"] is True
    assert body["accountId"] == "acc-1"
    assert body["summary"]["values"] == 1
    assert body["summary"]["measured"] == 1
    assert body["summary"]["complete"] == 1
    assert body["summary"]["cyclesComplete"] == 1

    value = body["values"][0]
    assert value["instrumentId"] == "i-1"
    assert value["measured"] is True
    assert value["complete"] is True
    cycle = value["cycles"][0]
    assert cycle["chain"]["reached"] == [
        "SIGNAL",
        "TOP_N",
        "RISK",
        "RESERVATION",
        "ORDER",
        "FILL",
        "PROTECTION",
        "SETTLEMENT",
        "CYCLE_CLOSED",
    ]
    assert all(cycle["steps"][step] == 1 for step in cycle["chain"]["reached"])
    assert cycle["pnl"]["reconciled"] is True
    # Identidad EJECUTADA leída del hecho durable (no inferida del ranking).
    assert cycle["executed"]["strategyPresetKey"] == "preset-alpha"
    assert value["strategy"]["presetKey"] == "preset-alpha"


@pytest.mark.asyncio
async def test_missing_step_is_a_declared_gap_not_zero(monkeypatch) -> None:
    cycle = _complete_cycle()
    cycle["steps"] = [step for step in cycle["steps"] if step["id"] != "FILL"]
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [cycle], "bestScored": None, "top3": None, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    cycle_view = body["values"][0]["cycles"][0]
    assert cycle_view["steps"]["FILL"] is None
    assert cycle_view["chain"]["complete"] is False
    assert cycle_view["chain"]["notReached"]["FILL"] == "unknown"
    assert body["values"][0]["complete"] is False


@pytest.mark.asyncio
async def test_value_without_cycles_is_declared_unmeasured(monkeypatch) -> None:
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1", "i-2"]},
        read={"cycles": [_complete_cycle()], "bestScored": None, "top3": None, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    by_id = {value["instrumentId"]: value for value in body["values"]}
    assert by_id["i-1"]["measured"] is True
    assert by_id["i-2"]["measured"] is False
    assert by_id["i-2"]["cycles"] == []
    assert by_id["i-2"]["unmeasured"] == ["no_cycles_for_value"]
    assert body["summary"]["measured"] == 1
    assert body["summary"]["values"] == 2


@pytest.mark.asyncio
async def test_ambiguous_strategy_identity_is_declared(monkeypatch) -> None:
    first = _complete_cycle()
    second = _complete_cycle()
    second["cycleId"] = "cyc-2"
    second["strategyPresetKey"] = "preset-beta"
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [first, second], "bestScored": None, "top3": None, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    strategy = body["values"][0]["strategy"]
    # Dos ciclos con identidades distintas: NO se elige "ganadora" (hueco declarado).
    assert strategy["presetKey"] is None
    assert strategy["presetKeyAmbiguous"] is True


@pytest.mark.asyncio
async def test_no_account_scope_reads_nothing(monkeypatch) -> None:
    app = _app(monkeypatch, scope=None)
    response = await _get(app, "/auto/estudio-chain")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["no_account_scope"]
    assert body["values"] == []


@pytest.mark.asyncio
async def test_read_failure_is_declared_not_an_empty_list(monkeypatch) -> None:
    app = _app(monkeypatch, boom=RuntimeError("db caída"))
    response = await _get(app, "/auto/estudio-chain")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["notes"] == ["read_failed"]
    assert "db caída" in body["error"]
    # Un error de lectura NO se disfraza de medición vacía.
    assert body["summary"] is None
    assert body["values"] == []


@pytest.mark.asyncio
async def test_universe_unavailable_is_declared_with_evidence(monkeypatch) -> None:
    app = _app(
        monkeypatch,
        estudio={"status": "unavailable", "instrumentIds": []},
        read={"cycles": [], "bestScored": None, "top3": None, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    assert body["available"] is True
    assert body["estudio"]["status"] == "unavailable"
    assert body["values"] == []
    assert "estudio_unavailable" in body["notes"]


@pytest.mark.asyncio
async def test_best_scored_identity_is_published_and_contrasted(monkeypatch) -> None:
    """V2.88.153 — el DTO publica la identidad de la foto y su veredicto (true/false)."""
    cycle = _complete_cycle()
    best = {
        "assetId": "i-1",
        "rank": 1,
        "combined": 0.71,
        "strategyPresetKey": "preset-alpha",
        "strategyVersion": "v7",
    }
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [cycle], "bestScored": best, "top3": best, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    assert body["bestScored"]["bestScoredPresetKey"] == "preset-alpha"
    assert body["bestScored"]["bestScoredStrategyVersion"] == "v7"
    assert body["bestScored"]["strategyMeasurement"] == "COMPLETE"
    compare = body["values"][0]["cycles"][0]["executedVsBest"]
    assert compare["presetMatch"] is True
    assert compare["versionMatch"] is True
    assert compare["bestScoredPresetKey"] == "preset-alpha"

    divergent = dict(best)
    divergent["strategyPresetKey"] = "preset-beta"
    divergent["strategyVersion"] = "v9"
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [cycle], "bestScored": divergent, "top3": divergent, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()
    compare = body["values"][0]["cycles"][0]["executedVsBest"]
    assert compare["presetMatch"] is False
    assert compare["versionMatch"] is False


@pytest.mark.asyncio
async def test_best_scored_without_identity_is_a_declared_gap(monkeypatch) -> None:
    """Una foto histórica (sin preset/versión) no se convertía en coincidencia."""
    best = {"assetId": "i-1", "rank": 1, "combined": 0.71}
    app = _app(
        monkeypatch,
        estudio={"status": "ok", "instrumentIds": ["i-1"]},
        read={"cycles": [_complete_cycle()], "bestScored": best, "top3": best, "diaDByCycle": {}},
    )
    body = (await _get(app, "/auto/estudio-chain")).json()

    assert body["bestScored"]["bestScoredPresetKey"] is None
    assert body["bestScored"]["strategyMeasurement"] == "UNKNOWN"
    compare = body["values"][0]["cycles"][0]["executedVsBest"]
    assert compare["presetMatch"] is None
    assert compare["versionMatch"] is None


@pytest.mark.asyncio
async def test_limit_is_bounded(monkeypatch) -> None:
    app = _app(monkeypatch)
    assert (await _get(app, "/auto/estudio-chain?limit=0")).status_code == 422
    assert (await _get(app, "/auto/estudio-chain?limit=500")).status_code == 422
