"""Mappers domain ↔ analytics para persistencia cognitiva."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    StatisticalSuiteResult,
    build_edge_report,
    build_memory_entry,
)
from bolsa_application.cognitive_persistence import (
    edge_report_to_record,
    memory_entry_to_record,
    record_to_edge_report,
    record_to_memory_entry,
)


def test_memory_roundtrip():
    entry = build_memory_entry(
        decision_id="DEC-1",
        instrument_id="AAPL",
        outcome="rejected",
        reasons=["EarningsBlackout"],
        policy_rule_ids=["EarningsBlackout"],
        reevaluate_when=["earnings_window_closed"],
    )
    rec = memory_entry_to_record(entry, account_id="acc-1")
    assert rec.account_id == "acc-1"
    assert rec.outcome == "rejected"
    back = record_to_memory_entry(rec)
    assert back.decision_id == entry.decision_id
    assert back.reevaluate_when == ("earnings_window_closed",)


def test_edge_report_roundtrip():
    suite = StatisticalSuiteResult(
        trials_n=8,
        walk_forward_efficiency=0.9,
        monte_carlo_p_value=0.01,
        dsr=0.9,
        stress_survival_rate=0.9,
        bootstrap_alpha_ci_lower=0.01,
        bootstrap_alpha_ci_upper=0.1,
    )
    report = build_edge_report("sig-x", suite)
    rec = edge_report_to_record(report, account_id="acc-2")
    assert rec.suite["trialsN"] == 8
    back = record_to_edge_report(rec)
    assert back.edge_report_id == report.edge_report_id
    assert back.suite.trials_n == 8
    assert back.band == report.band
