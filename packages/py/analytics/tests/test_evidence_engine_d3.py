"""RFC-008 D3 — PSR/DSR, TrialsLog, Evidence Suite, auto-live block."""

from __future__ import annotations

import numpy as np
import pytest

from bolsa_analytics.cognitive import (
    MODERATE_POLICY,
    EvidenceEngineInput,
    ProposedTradeContext,
    TrialsLog,
    check_auto_live,
    deflated_sharpe_ratio,
    gate_decision_package,
    probabilistic_sharpe_ratio,
    psr_dsr_from_returns,
    run_evidence_suite,
)
from bolsa_analytics.knowledge import TechnicalInputs, build_decision_package_ta


def test_psr_high_for_strong_edge():
    rng = np.random.default_rng(0)
    returns = rng.normal(0.02, 0.01, size=120)
    sr, psr, dsr = psr_dsr_from_returns(returns, trials_n=10)
    assert sr > 0
    assert 0.0 <= psr <= 1.0
    assert 0.0 <= dsr <= 1.0
    assert dsr <= psr + 1e-9  # DSR más estricto o igual


def test_dsr_requires_trials():
    with pytest.raises(ValueError, match="trials_n"):
        deflated_sharpe_ratio(1.0, n_obs=50, skew=0.0, kurtosis=3.0, trials_n=0)


def test_trials_log_and_suite_blocks_without_trials():
    log = TrialsLog(strategy_family_ref="SIG-TEST")
    result = run_evidence_suite(
        EvidenceEngineInput(
            strategy_or_signal_ref="SIG-TEST",
            trade_returns=[0.01, -0.005, 0.02, 0.01],
            trials_log=log,
            in_sample_sharpe=1.5,
            out_of_sample_sharpe=1.2,
        )
    )
    assert result.auto_live_eligible is False
    assert "missing_trials_log" in result.block_reasons
    assert result.edge_report.suite.trials_n == 0


def test_evidence_suite_with_trials():
    rng = np.random.default_rng(1)
    returns = list(rng.normal(0.015, 0.012, size=80))
    log = TrialsLog(strategy_family_ref="SIG-SPRING")
    for i in range(25):
        log.record(f"hyp-{i}", params_hash=f"h{i}", sharpe_is=0.1 * (i % 5))

    result = run_evidence_suite(
        EvidenceEngineInput(
            strategy_or_signal_ref="SIG-SPRING",
            trade_returns=returns,
            trials_log=log,
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.6,
            stress_survival_rate=0.85,
            bootstrap_alpha_ci_lower=0.01,
            bootstrap_alpha_ci_upper=0.04,
            monte_carlo_permutations=400,
        )
    )
    assert result.trials_n == 25
    assert result.edge_report.suite.dsr is not None
    assert result.edge_report.suite.psr is not None
    assert result.edge_report.suite.walk_forward_efficiency == pytest.approx(0.8)
    assert result.edge_report.suite.wfe_source == "sharpe"
    assert result.edge_report.artifact_type == "ART-EDGE-REPORT"


def test_evidence_suite_prefers_lab_wfe_over_sharpe():
    rng = np.random.default_rng(2)
    returns = list(rng.normal(0.01, 0.01, size=40))
    log = TrialsLog(strategy_family_ref="SIG-LAB")
    for i in range(8):
        log.record(f"lab-{i}", params_hash=f"l{i}", sharpe_is=0.2)

    result = run_evidence_suite(
        EvidenceEngineInput(
            strategy_or_signal_ref="SIG-LAB",
            trade_returns=returns,
            trials_log=log,
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.0,
            lab_walk_forward_efficiency=0.62,
            monte_carlo_permutations=200,
        )
    )
    assert result.edge_report.suite.walk_forward_efficiency == pytest.approx(0.62)
    assert result.edge_report.suite.wfe_source == "lab_score"
    assert any("optimize lab" in n.lower() for n in result.edge_report.notes)


def test_check_auto_live_blocks_weak_edge():
    log = TrialsLog(strategy_family_ref="WEAK")
    log.record("a", "h1", sharpe_is=0.1)
    # Near-zero returns → poor edge
    result = run_evidence_suite(
        EvidenceEngineInput(
            strategy_or_signal_ref="WEAK",
            trade_returns=list(np.random.default_rng(2).normal(0.0, 0.02, size=40)),
            trials_log=log,
            in_sample_sharpe=1.0,
            out_of_sample_sharpe=0.2,
            monte_carlo_permutations=300,
        )
    )
    al = check_auto_live(MODERATE_POLICY, evidence_result=result)
    assert al.allowed is False
    assert len(al.reasons) > 0


def test_gate_auto_live_veto_without_edge_report():
    inputs = TechnicalInputs(
        rsi=68,
        adx=32,
        plus_di=28,
        minus_di=15,
        obv_slope=1.0,
        price_slope=1.0,
        close=150,
        sma_20=145,
        sma_50=140,
    )
    package, _, _ = build_decision_package_ta("inst-aapl", inputs)
    gated = gate_decision_package(
        package,
        MODERATE_POLICY,
        ProposedTradeContext(
            symbol="AAPL",
            market_cap_usd=3e12,
            average_daily_volume_usd=1e9,
            risk_pct_of_account=0.5,
            reward_to_risk_ratio=2.2,
            has_stop_loss=True,
            hours_to_earnings=72,
            auto_live=True,
            edge_report=None,
        ),
    )
    assert gated.execution_allowed is False
    assert any(
        r.rule in {"EdgeReportRequired", "AutoLiveEvidence"}
        for r in (gated.gate.evaluated_rules if gated.gate else [])
    )


def test_gate_paper_auto_veto_without_edge_report_keeps_auto_live_false():
    inputs = TechnicalInputs(
        rsi=68,
        adx=32,
        plus_di=28,
        minus_di=15,
        obv_slope=1.0,
        price_slope=1.0,
        close=150,
        sma_20=145,
        sma_50=140,
    )
    package, _, _ = build_decision_package_ta("inst-aapl", inputs)
    ctx = ProposedTradeContext(
        symbol="AAPL",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.5,
        reward_to_risk_ratio=2.2,
        has_stop_loss=True,
        hours_to_earnings=72,
        auto_live=False,
        enforce_edge_thresholds=True,
        edge_report=None,
    )
    gated = gate_decision_package(package, MODERATE_POLICY, ctx)
    assert ctx.auto_live is False
    assert gated.execution_allowed is False


def test_psr_benchmark_zero():
    psr = probabilistic_sharpe_ratio(2.0, n_obs=100, skew=0.0, kurtosis=3.0, sr_benchmark=0.0)
    assert psr > 0.9
