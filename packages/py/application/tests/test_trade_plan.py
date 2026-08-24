"""TradePlan v0 — golden A/B/C/H (ADR-031)."""

from bolsa_analytics.cognitive.trade_plan import build_trade_plan, compute_risk_size


def test_compute_risk_size_basic() -> None:
    # 100k × 0.50% = 500; stop 5 → 100 shares
    assert compute_risk_size(equity=100_000, risk_pct=0.5, entry=100, stop=95) == 100.0


def test_golden_a_breakout_triggered() -> None:
    plan = build_trade_plan(
        decision_id="A",
        instrument_id="MSFT",
        action="recommend_long",
        entry_ready=True,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
        risk_pct=0.5,
        opportunity_score=94.0,
    )
    assert plan.status == "TRIGGERED"
    assert plan.quantity == 100.0
    assert plan.execution_allowed is True
    assert plan.why_not == ()


def test_golden_b_high_quality_bad_entry_watch() -> None:
    plan = build_trade_plan(
        decision_id="B",
        instrument_id="NVDA",
        action="recommend_long",
        entry_ready=False,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
        opportunity_score=98.0,
    )
    assert plan.status == "WATCH"
    assert plan.quantity == 0.0
    assert "entry" in plan.why_not
    assert plan.execution_allowed is False


def test_golden_c_portfolio_fit_blocked() -> None:
    plan = build_trade_plan(
        decision_id="C",
        instrument_id="AAPL",
        action="recommend_long",
        fit_ok=False,
        entry_ready=True,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
    )
    assert plan.status == "BLOCKED"
    assert "fit" in plan.why_not
    assert plan.execution_allowed is False


def test_golden_h_expired() -> None:
    plan = build_trade_plan(
        decision_id="H",
        instrument_id="SAP",
        action="recommend_long",
        expired=True,
        entry_ready=True,
        entry=100.0,
        structural_stop=95.0,
        expires_at="2026-08-01T00:00:00Z",
    )
    assert plan.status == "EXPIRED"
    assert "expired" in plan.why_not
    assert plan.execution_allowed is False
