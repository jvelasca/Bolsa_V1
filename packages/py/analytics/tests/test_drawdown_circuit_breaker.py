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


def test_drawdown_without_telemetry_is_not_verified():
    """P2 (auditoría .183) — sin telemetría la regla NO se salta en silencio.

    El contrato anterior (SKIPPED, sin motivo) dejaba el circuit breaker muerto: la
    política exigía un máximo de drawdown y el gate lo daba por bueno sin medirlo.
    Ahora diario y semanal VETAN con `<Regla>_unmeasured`. ``HardMaxDrawdown`` sigue
    declarado opcional por la plantilla porque depende de ``initial_deposit``
    (hallazgo P3, se corrige aparte), pero su ``SKIPPED`` lleva motivo propio.
    """
    gate = evaluate_policy_gate(MODERATE_POLICY, **_base_kwargs())
    assert gate.passed is False
    by_rule = {r.rule: r for r in gate.evaluated_rules}
    assert by_rule["HardDailyDrawdown"].status == "FAILED"
    assert by_rule["HardDailyDrawdown"].message == "HardDailyDrawdown_unmeasured"
    assert by_rule["HardWeeklyDrawdown"].status == "FAILED"
    assert by_rule["HardWeeklyDrawdown"].message == "HardWeeklyDrawdown_unmeasured"
    assert by_rule["HardMaxDrawdown"].status == "SKIPPED"
    assert by_rule["HardMaxDrawdown"].message == "HardMaxDrawdown_unmeasured_declared"


def test_weekly_drawdown_veto():
    gate = evaluate_policy_gate(
        MODERATE_POLICY,
        **_base_kwargs(account_weekly_drawdown_pct=10.0),
    )
    assert any(r.rule == "HardWeeklyDrawdown" and r.status == "FAILED" for r in gate.evaluated_rules)
