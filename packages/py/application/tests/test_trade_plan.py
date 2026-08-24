"""TradePlan v0 — golden A/B/C/H (ADR-031) + Ciclo 4.0 stop/entry_ready."""

from types import SimpleNamespace

from bolsa_analytics.cognitive.trade_plan import (
    ATR_MULT,
    build_trade_plan,
    build_v0_trade_plan_dict,
    compute_risk_size,
    compute_structural_stop,
    entry_ready_from_ta,
)


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


def test_structural_stop_atr_long_and_short() -> None:
    assert compute_structural_stop(
        action="recommend_long", entry=100.0, atr=2.0
    ) == 100.0 - ATR_MULT * 2.0
    assert compute_structural_stop(
        action="recommend_short", entry=100.0, atr=2.0
    ) == 100.0 + ATR_MULT * 2.0


def test_structural_stop_invalid_atr_without_bars() -> None:
    assert compute_structural_stop(action="recommend_long", entry=100.0, atr=None) is None
    assert compute_structural_stop(action="recommend_long", entry=100.0, atr=0.0) is None


def test_structural_stop_swing_farther_wins_long() -> None:
    # 11 barras: las 10 cerradas tienen low=90; ATR stop = 97. El más lejano es 90.
    closed = [SimpleNamespace(low=90.0, high=101.0) for _ in range(10)]
    last = SimpleNamespace(low=99.0, high=101.0)
    stop = compute_structural_stop(
        action="recommend_long",
        entry=100.0,
        atr=2.0,
        bars=[*closed, last],
    )
    assert stop == 90.0


def test_entry_ready_from_ta_aligns_bias() -> None:
    assert entry_ready_from_ta(action="recommend_long", bias="bullish") is True
    assert entry_ready_from_ta(action="recommend_long", bias="bearish") is False
    assert entry_ready_from_ta(
        action="recommend_long", bias="bullish", exhaustion=True
    ) is False
    assert entry_ready_from_ta(action="recommend_short", bias="bearish") is True
    assert entry_ready_from_ta(action="wait", bias="bullish") is False


def test_v0_dict_golden_a_with_equity() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="A",
        instrument_id="MSFT",
        action="recommend_long",
        entry=100.0,
        opportunity_score=94.0,
        expires_at=None,
        atr=2.0,
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    stop = 100.0 - ATR_MULT * 2.0
    assert plan["status"] == "TRIGGERED"
    assert plan["structuralStop"] == stop
    assert plan["quantity"] == compute_risk_size(
        equity=100_000, risk_pct=0.5, entry=100.0, stop=stop
    )
    assert plan["executionAllowed"] is True


def test_v0_dict_bias_mismatch_watch_entry() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="B",
        instrument_id="NVDA",
        action="recommend_long",
        entry=100.0,
        opportunity_score=98.0,
        expires_at=None,
        atr=2.0,
        bias="bearish",
        equity=100_000,
        risk_pct=0.5,
    )
    assert plan["status"] == "WATCH"
    assert "entry" in plan["whyNot"]
    assert plan["executionAllowed"] is False


def test_v0_dict_defaults_watch_no_stop() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="X",
        instrument_id="SAP",
        action="recommend_long",
        entry=100.0,
        opportunity_score=None,
        expires_at=None,
    )
    assert plan["status"] == "WATCH"
    assert "no_stop" in plan["whyNot"]


def test_golden_d_farther_stop_reduces_size_not_stop() -> None:
    near = build_v0_trade_plan_dict(
        decision_id="D1",
        instrument_id="IBM",
        action="recommend_long",
        entry=100.0,
        opportunity_score=80.0,
        expires_at=None,
        atr=2.0,
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    closed = [SimpleNamespace(low=90.0, high=101.0) for _ in range(10)]
    last = SimpleNamespace(low=99.0, high=101.0)
    far = build_v0_trade_plan_dict(
        decision_id="D2",
        instrument_id="IBM",
        action="recommend_long",
        entry=100.0,
        opportunity_score=80.0,
        expires_at=None,
        atr=2.0,
        bars=[*closed, last],
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    assert far["structuralStop"] == 90.0
    assert far["structuralStop"] < near["structuralStop"]
    assert far["quantity"] < near["quantity"]
    assert far["status"] == "TRIGGERED"
