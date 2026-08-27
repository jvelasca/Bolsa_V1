"""RFC-008 D1 (Profile/Policy Gate) + D3 skeleton (Evidence/Edge)."""

from __future__ import annotations

import numpy as np

from bolsa_analytics.cognitive import (
    AGGRESSIVE_SWING_POLICY,
    CONSERVATIVE_POLICY,
    MODERATE_POLICY,
    POLICY_TEMPLATES,
    StatisticalSuiteResult,
    build_edge_report,
    compute_credibility,
    evaluate_policy_gate,
    get_policy_template,
    monte_carlo_permutation_p_value,
    suggest_policy_template_from_declared,
    walk_forward_efficiency,
)
from bolsa_analytics.cognitive.investor_profile import (
    DeclaredInvestorProfile,
    InvestorProfile,
    ObservedInvestorProfile,
)
from bolsa_domain.account_settings import settings_from_dict, settings_to_dict


def test_suggest_policy_from_declared():
    assert (
        suggest_policy_template_from_declared(
            risk_tolerance="low", horizon="swing"
        )
        == "conservative"
    )
    assert (
        suggest_policy_template_from_declared(
            risk_tolerance="high", horizon="swing"
        )
        == "aggressive_swing"
    )
    assert (
        suggest_policy_template_from_declared(
            risk_tolerance="moderate", horizon="swing"
        )
        == "moderate"
    )


def test_account_settings_strips_legacy_investor_profile():
    """settings_json ya no transporta investorProfile (catálogo ART-PROFILE)."""
    raw = {
        "commission": {
            "presetId": "none",
            "label": "Sin comisiones",
            "stockCommissionPct": 0,
            "stockCommissionMin": 0,
            "stockCommissionMax": None,
            "vatOnCommissionPct": 0,
            "fxConversionPct": 0,
            "custodyAnnualPct": None,
        },
        "tax": {
            "jurisdiction": "ES",
            "costBasisMethod": "fifo",
            "stampDutyBuyPct": 0.2,
            "dividendWithholdingPct": 19,
            "capitalGainsTaxPct": None,
            "fiscalYearStartMonth": 1,
        },
        "notes": None,
        "investorProfile": {
            "profileId": "PROF-legacy",
            "version": "1.0.0",
            "declared": {
                "horizon": "swing",
                "objectives": ["growth"],
                "riskTolerance": "moderate",
                "experience": "intermediate",
            },
            "suggestedPolicyTemplateId": "moderate",
            "selectedPolicyTemplateId": "moderate",
            "updatedAt": "2026-07-22T00:00:00Z",
            "createdAt": "2026-07-22T00:00:00Z",
        },
    }
    settings = settings_from_dict(raw)
    assert not hasattr(settings, "investor_profile")
    back = settings_to_dict(settings)
    assert "investorProfile" not in back
    assert back["commission"]["presetId"] == "none"


def test_three_policy_templates_exist():
    assert set(POLICY_TEMPLATES) == {"conservative", "moderate", "aggressive_swing"}
    assert CONSERVATIVE_POLICY.risk.max_risk_per_trade_pct < MODERATE_POLICY.risk.max_risk_per_trade_pct
    assert MODERATE_POLICY.risk.max_risk_per_trade_pct < AGGRESSIVE_SWING_POLICY.risk.max_risk_per_trade_pct
    clone = get_policy_template("moderate")
    assert clone.policy_id == MODERATE_POLICY.policy_id
    assert clone is not MODERATE_POLICY


def test_investor_profile_declared_observed_separated():
    profile = InvestorProfile(
        profile_id="PROF-1",
        version="1.0.0",
        name="Demo",
        declared=DeclaredInvestorProfile(
            horizon="swing",
            objectives=("growth",),
            risk_tolerance="moderate",
            experience="intermediate",
        ),
        observed=ObservedInvestorProfile(
            sample_trade_count=20,
            diverges_from_declared=True,
            diverges_from_policy=True,
            impulsivity_score=0.8,
            notes=("overtrading vs moderate policy",),
        ),
        updated_by="hybrid",
        updated_at="2026-07-22T00:00:00Z",
        created_at="2026-07-22T00:00:00Z",
        suggested_policy_template_id="moderate",
    )
    payload = profile.to_dict()
    assert payload["artifactType"] == "ART-PROFILE"
    assert payload["declared"]["riskTolerance"] == "moderate"
    assert payload["observed"]["divergesFromPolicy"] is True
    # Observed never silently becomes declared
    assert payload["declared"]["riskTolerance"] != "high"


def test_policy_gate_passes_clean_moderate_trade():
    result = evaluate_policy_gate(
        MODERATE_POLICY,
        symbol="AAPL",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.8,
        reward_to_risk_ratio=2.2,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=3,
        portfolio_concentration_pct=5.0,
        hours_to_earnings=72,
        auto_live=False,
    )
    assert result.passed is True
    assert result.veto_reasons == ()


def test_policy_gate_veto_pre_earnings_keeps_opportunity_concept():
    """Opportunity can remain excellent; permission fails separately."""
    result = evaluate_policy_gate(
        CONSERVATIVE_POLICY,
        symbol="AAPL",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.3,
        reward_to_risk_ratio=3.0,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=2,
        portfolio_concentration_pct=4.0,
        hours_to_earnings=12,  # within 48h blackout
        auto_live=False,
    )
    assert result.passed is False
    assert any("earnings" in r.lower() or "PreEarnings" in r for r in result.veto_reasons)
    assert any(r.rule == "PreEarningsBlackout" and r.status == "FAILED" for r in result.evaluated_rules)


def test_policy_gate_blocks_auto_live_without_edge():
    result = evaluate_policy_gate(
        MODERATE_POLICY,
        symbol="MSFT",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.5,
        reward_to_risk_ratio=2.5,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=1,
        portfolio_concentration_pct=3.0,
        auto_live=True,
        edge_report_present=False,
        credibility=90,
    )
    assert result.passed is False
    assert any(r.rule == "EdgeReportRequired" for r in result.evaluated_rules)


def test_policy_gate_blocks_paper_auto_edge_thresholds_without_live_flag():
    result = evaluate_policy_gate(
        MODERATE_POLICY,
        symbol="MSFT",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=1e9,
        risk_pct_of_account=0.5,
        reward_to_risk_ratio=2.5,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=1,
        portfolio_concentration_pct=3.0,
        auto_live=False,
        enforce_edge_thresholds=True,
        edge_report_present=False,
        credibility=90,
    )
    assert result.passed is False
    assert any(r.rule == "EdgeReportRequired" for r in result.evaluated_rules)


def test_wfe_and_monte_carlo_skeleton():
    assert walk_forward_efficiency(2.0, 1.5) == 0.75
    assert walk_forward_efficiency(0.0, 1.0) == 0.0

    rng = np.random.default_rng(0)
    # Strong positive drift → low p-value more often than noise
    strong = rng.normal(0.02, 0.01, size=80)
    p_strong = monte_carlo_permutation_p_value(strong, permutations=500, seed=1)
    noise = rng.normal(0.0, 0.02, size=80)
    p_noise = monte_carlo_permutation_p_value(noise, permutations=500, seed=2)
    assert 0.0 < p_strong <= 1.0
    assert 0.0 < p_noise <= 1.0


def test_credibility_and_edge_report():
    suite = StatisticalSuiteResult(
        trials_n=120,
        walk_forward_efficiency=0.92,
        monte_carlo_p_value=0.01,
        dsr=0.87,
        psr=0.91,
        bootstrap_alpha_ci_lower=0.01,
        bootstrap_alpha_ci_upper=0.05,
        stress_survival_rate=0.9,
        historical_win_rate=0.74,
        sample_trades_count=382,
    )
    cred, edge, band = compute_credibility(suite)
    assert cred == edge
    assert cred >= 65
    report = build_edge_report("SIG-SPRING-WYCKOFF", suite)
    assert report.artifact_type == "ART-EDGE-REPORT"
    assert report.band in {"skill", "uncertain", "luck"}
    assert report.to_dict()["suite"]["trialsN"] == 120

    no_trials = StatisticalSuiteResult(trials_n=0, dsr=0.99, walk_forward_efficiency=0.9)
    report2 = build_edge_report("SIG-X", no_trials)
    assert any("trialsN" in n for n in report2.notes)
