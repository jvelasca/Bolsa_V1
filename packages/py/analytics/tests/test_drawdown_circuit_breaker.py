"""F4 — circuit breaker drawdown en Policy Gate."""

from __future__ import annotations

from bolsa_analytics.cognitive import MODERATE_POLICY, evaluate_policy_gate


def _base_kwargs(**overrides):
    kw = dict(
        symbol="AAPL",
        asset_class="equities",
        market_cap_usd=3e12,
        average_daily_volume_usd=5e9,
        risk_pct_of_account=0.5,
        reward_to_risk_ratio=2.0,
        leverage=1.0,
        has_stop_loss=True,
        open_positions_count=0,
        portfolio_concentration_pct=5.0,
    )
    kw.update(overrides)
    return kw


def test_max_drawdown_veto():
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **_base_kwargs(account_max_drawdown_pct=20.0),
    )
    assert gate.passed is False
    assert any(r.rule == "HardMaxDrawdown" and r.status == "FAILED" for r in gate.evaluated_rules)


def test_max_drawdown_pass_under_limit():
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **_base_kwargs(account_max_drawdown_pct=5.0),
    )
    assert any(r.rule == "HardMaxDrawdown" and r.status == "PASSED" for r in gate.evaluated_rules)
    assert all(r.rule != "HardMaxDrawdown" or r.status != "FAILED" for r in gate.evaluated_rules)


def test_drawdown_skipped_without_telemetry():
    gate = evaluate_policy_gate(MODERATE_POLICY, **_base_kwargs())
    assert any(r.rule == "HardMaxDrawdown" and r.status == "SKIPPED" for r in gate.evaluated_rules)
    assert any(r.rule == "HardDailyDrawdown" and r.status == "SKIPPED" for r in gate.evaluated_rules)


def test_weekly_drawdown_veto():
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **_base_kwargs(account_weekly_drawdown_pct=10.0),
    )
    assert any(r.rule == "HardWeeklyDrawdown" and r.status == "FAILED" for r in gate.evaluated_rules)
