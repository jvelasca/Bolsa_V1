"""Bucle de adaptación (ADR-049) — contratos HTTP y paridad del enum cerrado.

La IA propone, el gate decide y un humano aprueba: ninguna ruta devuelve
``activationAllowed=true``. Los registros se aíslan en ``tmp_path``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.ai_governance as route
from bolsa_ai.schemas import ADAPTATION_MUTATIONS as AI_MUTATIONS
from bolsa_api.main import create_app
from bolsa_application.adaptation_proposals import ADAPTATION_MUTATIONS as APP_MUTATIONS
from bolsa_application.dia_d_as_run import (
    AsRunExecutionModel,
    AsRunFill,
    AsRunLeg,
    build_as_run_artifact,
)
from bolsa_domain.entities.ohlcv_bar import OhlcvBar


def _evidence(measured: bool = True) -> dict:
    return {
        "version": "AdaptationEvidenceV1",
        "regime": "TREND",
        "family": "breakout",
        "instrument": "AAA",
        "cycles": 20,
        "closedCycles": 20,
        "expectancyR": -0.204,
        "hitRate": 0.417,
        "avgMaeR": -0.95,
        "avgMfeR": 0.8,
        "capture": 0.31,
        "failedGates": ["maxDrawdownPct"],
        "lossDrivers": [{"driver": "family:breakout", "cycles": 8, "realizedR": -3.2}],
        "artifactRefs": ["docs/engineering/dia-d-evidencia-politica-2026-11-05.md"],
        "measured": measured,
        "gaps": [],
        "hash": "abc123",
    }


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def scoped(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(route, "_adaptation_dir", lambda: tmp_path)
    return tmp_path


def _certifiable_artifact(day: str) -> dict:
    """Artefacto as-run con sobre de auditoría completo: el único que puede certificarse."""
    entry_day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    exit_day = (date.fromisoformat(day) + timedelta(days=2)).isoformat()
    leg = AsRunLeg(
        instrument_id="AAA",
        direction="long",
        quantity=10.0,
        entry=100.0,
        structural_stop=95.0,
        target1=110.0,
    )
    candidate = AsRunLeg(
        instrument_id="AAA",
        direction="long",
        quantity=10.0,
        entry=100.0,
        structural_stop=97.5,
        target1=110.0,
    )
    bars = {
        "AAA": [
            OhlcvBar(timestamp=entry_day, open=100.0, high=105.0, low=99.0, close=104.0, volume=1_000),
            OhlcvBar(timestamp=exit_day, open=104.0, high=111.0, low=103.0, close=110.0, volume=1_000),
        ]
    }
    fills = [
        AsRunFill(timestamp=entry_day, instrument_id="AAA", side="buy", quantity=10.0, price=100.0),
        AsRunFill(timestamp=exit_day, instrument_id="AAA", side="sell", quantity=10.0, price=110.0),
    ]
    execution = AsRunExecutionModel(
        commission_bps=5.0,
        slippage_bps=3.0,
        spread_bps=2.0,
        max_participation_pct=0.1,
    )
    return build_as_run_artifact(
        day=day,
        account_id="acc-1",
        legs=[leg],
        fills=fills,
        bars_by_instrument=bars,
        execution=execution,
        candidate_legs=[candidate],
        candidate_as_of=day,
        to_day=exit_day,
        state_source="sim_auto_positions",
        bars_source="postgres:ohlcv_bars",
        bars_timeframe="1d",
        params={
            "engineStopMultiplier": None,
            "engineTargetMultiplier": None,
            "universe": "watch",
            "execution": execution.to_dict(),
        },
        universe_instruments=["AAA"],
        bump="test-bump",
    )


async def _post(app, path: str, payload: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=payload)


async def _get(app, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_closed_enum_matches_between_application_and_ai() -> None:
    assert APP_MUTATIONS == AI_MUTATIONS


@pytest.mark.asyncio
async def test_propose_unmeasured_evidence_stores_nothing(app, scoped) -> None:
    response = await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(measured=False), "useProxy": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["batch"]["source"] == "no_evidence"
    assert data["batch"]["proposals"] == []
    assert data["stored"] == []
    assert data["governance"]["activationAllowed"] is False
    assert list(scoped.glob("*.json")) == []


@pytest.mark.asyncio
async def test_propose_without_proxy_declares_heuristic_fallback(app, scoped) -> None:
    response = await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(), "useProxy": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["batch"]["source"] == "heuristic_fallback"
    assert data["batch"]["proposals"]
    assert len(data["stored"]) == len(data["batch"]["proposals"])
    assert all(proposal["id"].startswith("adp_") for proposal in data["batch"]["proposals"])
    assert len(list(scoped.glob("*.json"))) == len(data["stored"])


@pytest.mark.asyncio
async def test_list_returns_persisted_proposals(app, scoped) -> None:
    await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(), "useProxy": False},
    )

    response = await _get(app, "/api/ai/adaptation")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] > 0
    assert data["count"] == len(data["items"])
    assert data["items"][0]["status"] == "proposed"


@pytest.mark.asyncio
async def test_validate_unknown_proposal_is_404(app, scoped) -> None:
    response = await _post(app, "/api/ai/adaptation/adp_missing/validate", {"lab": {}})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_validate_unmeasured_lab_rejects_and_never_activates(app, scoped) -> None:
    proposed = await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(), "useProxy": False},
    )
    proposal_id = proposed.json()["data"]["stored"][0]

    response = await _post(
        app,
        f"/api/ai/adaptation/{proposal_id}/validate",
        {"lab": {"measured": False}, "candidateId": "cand-1"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["verdict"]["verdict"] == "rejected"
    assert data["verdict"]["measured"] is False
    assert data["governance"]["activationAllowed"] is False
    assert data["governance"]["note"].startswith("Requiere aprobación humana")


@pytest.mark.asyncio
async def test_validate_green_lab_still_requires_human(app, scoped) -> None:
    proposed = await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(), "useProxy": False},
    )
    proposal_id = proposed.json()["data"]["stored"][0]
    artifacts = [_certifiable_artifact(f"2026-01-{index + 1:02d}") for index in range(12)]

    response = await _post(
        app,
        f"/api/ai/adaptation/{proposal_id}/validate",
        {
            "lab": {
                "measured": True,
                "netReturnPct": 12.0,
                "maxDrawdownPct": 9.0,
                "positiveWindowPct": 66.0,
                "excessVsBuyHoldPct": 3.0,
                "roundTripCostBps": 24.0,
                "samples": 40,
                "multipleTestingCorrected": True,
            },
            "asRunArtifacts": artifacts,
            "candidateId": "cand-1",
        },
    )

    data = response.json()["data"]
    assert data["verdict"]["verdict"] == "requires_human_approval"
    assert data["governance"]["activationAllowed"] is False
    assert data["governance"]["humanApprovalRequired"] is True
    assert "human_approval_required" in data["verdict"]["reasons"]
    assert data["verdict"]["lab"]["status"] == "PASS"
    assert data["verdict"]["asRun"]["status"] == "PASS"
    assert data["verdict"]["certification"]["verdict"] == "certified"


@pytest.mark.asyncio
async def test_validate_green_lab_without_certification_rejects(app, scoped) -> None:
    """Sin certificación del DÍA-D, un LAB perfecto no habilita nada."""
    proposed = await _post(
        app,
        "/api/ai/adaptation/propose",
        {"evidence": _evidence(), "useProxy": False},
    )
    proposal_id = proposed.json()["data"]["stored"][0]
    artifacts = [
        {
            "day": f"2026-01-{index + 1:02d}",
            "arms": [
                {"arm": "as_run", "measured": True, "realizedR": 0.1},
                {"arm": "candidate", "measured": True, "realizedR": 0.4},
                {"arm": "cash", "measured": True, "realizedR": 0.0},
                {"arm": "market_bh", "measured": True, "realizedR": None},
            ],
        }
        for index in range(12)
    ]

    response = await _post(
        app,
        f"/api/ai/adaptation/{proposal_id}/validate",
        {
            "lab": {
                "measured": True,
                "netReturnPct": 12.0,
                "maxDrawdownPct": 9.0,
                "positiveWindowPct": 66.0,
                "excessVsBuyHoldPct": 3.0,
                "roundTripCostBps": 24.0,
                "samples": 40,
                "multipleTestingCorrected": True,
            },
            "asRunArtifacts": artifacts,
            "candidateId": "cand-1",
        },
    )

    data = response.json()["data"]
    assert data["verdict"]["verdict"] == "rejected"
    assert data["verdict"]["lab"]["status"] == "PASS"
    certification_gate = next(
        gate for gate in data["verdict"]["gates"] if gate["name"] == "as_run_certification"
    )
    assert certification_gate["status"] == "FAIL"
    assert data["governance"]["activationAllowed"] is False
