"""Tests Evidence cola CORE-R."""

from __future__ import annotations

from bolsa_analytics.knowledge.core_r_review_evidence import (
    build_core_r_review_evidence,
    resolve_band,
)


def test_empty_band():
    assert resolve_band([]) == "empty"
    ev = build_core_r_review_evidence({"listId": "L", "timeframe": "1d", "rows": []})
    assert ev["band"] == "empty"
    assert ev["schemaVersion"] == "core_r_review_evidence_v1"
    assert len(ev["paragraphs"]) == 3


def test_attention_review_lab():
    rows = [
        {
            "instrumentId": "i1",
            "symbol": "TEF",
            "verdict": "review_lab",
            "reason": "PnL -6%",
        }
    ]
    assert resolve_band(rows) == "attention"
    ev = build_core_r_review_evidence({"listId": "ibex", "rows": rows})
    assert ev["band"] == "attention"
    assert ev["metrics"]["reviewLab"] == 1


def test_urgent_consider_replace():
    rows = [
        {
            "instrumentId": "i2",
            "symbol": "SAN",
            "verdict": "consider_replace",
            "reason": "PBO alto",
        }
    ]
    assert resolve_band(rows) == "urgent"
    ev = build_core_r_review_evidence({"listId": "ibex", "rows": rows})
    assert ev["band"] == "urgent"
    assert any("Valorar cambio" in w or "cambio" in w.lower() for w in ev["warnings"])
