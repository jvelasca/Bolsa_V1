"""`P2` (sello 2) — contrato HTTP de la auditoría por valor de ESTUDIO.

Hermético (sin PostgreSQL): el artefacto de feedback y el reporte financiero OOS se escriben
en un directorio temporal (``DIA_D_AUTO_DIR``). Cubre: composición por valor (estrategia +
señal + R + dinero), unión por la clave EXACTA ``presetKey``, fail-closed sin cuenta, ventana
inexistente y ventana inválida.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_estudio_audit as route
from bolsa_api.main import create_app


def _feedback_artifact(account: str) -> dict[str, Any]:
    return {
        "schemaVersion": "v2",
        "kind": "DIA_D_AUTO_FEEDBACK",
        "readOnly": True,
        "window": {"from": "2026-04-01", "to": "2026-04-02", "days": ["2026-04-01", "2026-04-02"]},
        "values": [
            {
                "symbol": "ACS",
                "verdict": "MIXED",
                "verdictReason": "preliminary_sample",
                "evidenceQuality": "SUPPORTED",
                "expectancyR": 0.4,
                "hitRate": 0.55,
                "measuredCycles": 8,
                "daysCovered": 2,
                "realizedRTotal": 3.2,
            }
        ],
        "cycles": [
            {
                "cycleId": "cyc-1",
                "symbol": "ACS",
                "entryDay": "2026-04-01",
                "exitDay": "2026-04-02",
                "strategyVersion": "ver-1",
                "strategyPresetKey": "sma_crossover",
                "realizedR": 0.5,
            }
        ],
        "matrix": [],
        "errors": [],
        "gate": {},
        "meta": {"account": account},
        "limits": [],
    }


def _finance_artifact() -> dict[str, Any]:
    return {
        "groups": [
            {
                "strategyVersion": "ver-1",
                "symbol": "ACS",
                "strategyPresetKey": "sma_crossover",
                "trades": 12,
                "committedCapital": 1000.0,
                "netReturnPct": 2.5,
                "netReturnPctAtStress": 1.8,
                "maxDrawdownPct": 3.0,
                "hitRate": 0.6,
            }
        ]
    }


def _seed(tmp_path: Path, account: str) -> None:
    (tmp_path / "feedback-2026-04-01_2026-04-02.json").write_text(
        json.dumps(_feedback_artifact(account)), encoding="utf-8"
    )
    (tmp_path / "finance-2026-04-01_2026-04-02.json").write_text(
        json.dumps(_finance_artifact()), encoding="utf-8"
    )


def _app(scope: str | None):  # noqa: ANN202 — helper de test
    app = create_app()

    async def _scope(_request: Any, _account_id: Any) -> str | None:  # noqa: ANN202
        return scope

    route.resolve_account_scope_or_default = _scope  # type: ignore[assignment]
    return app


async def _get(app, path: str):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_latest_window_composes_value_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _seed(tmp_path, "acc-1")
    response = await _get(_app("acc-1"), "/api/auto/estudio-audit")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["window"] == "2026-04-01_2026-04-02"
    assert body["audit"]["pointCitable"] is False
    value = body["audit"]["values"][0]
    assert value["symbol"] == "ACS"
    assert value["strategy"]["presetKey"] == "sma_crossover"
    assert value["cycles"] == [
        {
            "cycleId": "cyc-1",
            "entryDay": "2026-04-01",
            "exitDay": "2026-04-02",
            "strategyPresetKey": "sma_crossover",
            "strategyVersion": "ver-1",
            "signalId": None,
            "planId": None,
            "realizedR": 0.5,
        }
    ]
    assert value["resultR"]["measured"] is True
    assert value["money"]["netReturnPct"] == 2.5
    assert value["measured"] is True
    assert body["audit"]["summary"]["measured"] == 1


@pytest.mark.asyncio
async def test_specific_window_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _seed(tmp_path, "acc-1")
    response = await _get(_app("acc-1"), "/api/auto/estudio-audit/2026-04-01_2026-04-02")
    assert response.status_code == 200
    assert response.json()["available"] is True


@pytest.mark.asyncio
async def test_without_finance_artifact_money_is_declared_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    (tmp_path / "feedback-2026-04-01_2026-04-02.json").write_text(
        json.dumps(_feedback_artifact("acc-1")), encoding="utf-8"
    )
    response = await _get(_app("acc-1"), "/api/auto/estudio-audit")
    value = response.json()["audit"]["values"][0]
    assert value["money"]["measured"] is False
    assert value["money"]["netReturnPct"] is None
    assert value["measured"] is False
    assert any("sin grupo financiero" in gap for gap in value["unmeasured"])


@pytest.mark.asyncio
async def test_other_account_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIA_D_AUTO_DIR", str(tmp_path))
    _seed(tmp_path, "acc-1")
    body = (await _get(_app("acc-2"), "/api/auto/estudio-audit")).json()
    assert body["available"] is False
    assert body["notes"] == ["no_artifacts"]


@pytest.mark.asyncio
async def test_without_scope_is_fail_closed() -> None:
    body = (await _get(_app(None), "/api/auto/estudio-audit")).json()
    assert body["available"] is False
    assert body["notes"] == ["no_account_scope"]


@pytest.mark.asyncio
async def test_invalid_window_is_declared() -> None:
    body = (await _get(_app("acc-1"), "/api/auto/estudio-audit/no-es-fecha")).json()
    assert body["available"] is False
    assert body["notes"] == ["invalid_window"]
