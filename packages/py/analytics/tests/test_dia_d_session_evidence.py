"""Tests Evidence sesión DÍA D."""

from __future__ import annotations

from bolsa_analytics.knowledge.dia_d_session_evidence import (
    build_dia_d_session_evidence,
    resolve_band,
)


def _payload(**overrides):
    base = {
        "mode": "semi",
        "symbol": "ACS",
        "strategyLabel": "SMA",
        "diaD": "2024-01-01",
        "endDate": "2024-12-31",
        "auto": {
            "totalReturnPct": 12.0,
            "maxDrawdownPct": 8.0,
            "tradeCount": 6,
            "finalEquity": 11200.0,
        },
        "gated": {
            "totalReturnPct": 10.0,
            "maxDrawdownPct": 7.0,
            "tradeCount": 4,
            "finalEquity": 11000.0,
        },
        "gate": {"accepted": 4, "rejected": 2},
    }
    base.update(overrides)
    return base


def test_incomplete_without_gate_decisions():
    p = _payload(gate={"accepted": 0, "rejected": 0})
    p["gated"] = {**p["gated"], "tradeCount": 0, "totalReturnPct": 0.0}
    assert resolve_band(p) == "incomplete"
    ev = build_dia_d_session_evidence(p)
    assert ev["band"] == "incomplete"
    assert ev["confidence"] == "LOW"
    assert len(ev["paragraphs"]) == 3


def test_favorable_beats_auto():
    p = _payload()
    p["gated"] = {
        "totalReturnPct": 14.0,
        "maxDrawdownPct": 6.0,
        "tradeCount": 4,
        "finalEquity": 11400.0,
    }
    ev = build_dia_d_session_evidence(p)
    assert ev["band"] == "favorable"
    assert ev["schemaVersion"] == "dia_d_session_evidence_v1"


def test_adverse_large_drawdown_return():
    p = _payload()
    p["gated"] = {
        "totalReturnPct": -12.0,
        "maxDrawdownPct": 22.0,
        "tradeCount": 2,
        "finalEquity": 8800.0,
    }
    ev = build_dia_d_session_evidence(p)
    assert ev["band"] == "adverse"
    assert any("DD" in w for w in ev["warnings"])
