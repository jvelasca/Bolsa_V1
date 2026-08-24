"""TradePlan v0 — golden A/B/C/D/G/H (ADR-031) + Ciclo 4.0–4.2."""

from types import SimpleNamespace

from bolsa_analytics.cognitive.trade_plan import (
    ATR_MULT,
    BREAKOUT_LOOKBACK,
    build_trade_plan,
    build_v0_trade_plan_dict,
    classify_entry_setup,
    compute_risk_size,
    compute_structural_stop,
    entry_ready_from_ta,
    no_new_longs_blocks,
)


def _bar(*, close: float, high: float | None = None, low: float | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        close=close,
        high=close if high is None else high,
        low=close if low is None else low,
    )


def _breakout_long_bars(entry: float = 100.0) -> list[SimpleNamespace]:
    """20 cerradas bajo entry + last close por encima del max high."""
    closed = [_bar(close=entry - 2, high=entry - 1, low=entry - 3) for _ in range(BREAKOUT_LOOKBACK)]
    last = _bar(close=entry + 1, high=entry + 1, low=entry - 1)
    return [*closed, last]


def test_compute_risk_size_basic() -> None:
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
        entry_setup="breakout",
    )
    assert plan.status == "TRIGGERED"
    assert plan.quantity == 100.0
    assert plan.execution_allowed is True
    assert plan.why_not == ()
    assert plan.entry_setup == "breakout"


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
        entry_setup="none",
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
        entry_setup="breakout",
    )
    assert plan.status == "BLOCKED"
    assert "fit" in plan.why_not
    assert plan.execution_allowed is False


def test_golden_g_no_new_longs_risk_off() -> None:
    plan = build_trade_plan(
        decision_id="G",
        instrument_id="SPY",
        action="recommend_long",
        entry_ready=True,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
        risk_pct=0.5,
        market_regime="risk_off",
        entry_setup="breakout",
    )
    assert plan.status == "BLOCKED"
    assert "regime" in plan.why_not
    assert plan.quantity == 0.0
    assert plan.execution_allowed is False


def test_golden_g_crisis_blocks_long_accumulates_fit() -> None:
    plan = build_trade_plan(
        decision_id="G2",
        instrument_id="QQQ",
        action="recommend_long",
        fit_ok=False,
        entry_ready=True,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
        market_regime="crisis",
        entry_setup="breakout",
    )
    assert plan.status == "BLOCKED"
    assert plan.why_not == ("regime", "fit")


def test_golden_g_short_allowed_in_risk_off() -> None:
    plan = build_trade_plan(
        decision_id="G3",
        instrument_id="IWM",
        action="recommend_short",
        entry_ready=True,
        entry=100.0,
        structural_stop=105.0,
        equity=100_000,
        risk_pct=0.5,
        market_regime="risk_off",
        entry_setup="breakout",
    )
    assert plan.status == "TRIGGERED"
    assert "regime" not in plan.why_not
    assert plan.quantity > 0


def test_golden_g_neutral_and_missing_regime_do_not_block() -> None:
    assert no_new_longs_blocks(action="recommend_long", market_regime=None) is False
    assert no_new_longs_blocks(action="recommend_long", market_regime="neutral") is False
    assert no_new_longs_blocks(action="recommend_long", market_regime="uncertain") is False
    plan = build_v0_trade_plan_dict(
        decision_id="G4",
        instrument_id="MSFT",
        action="recommend_long",
        entry=100.0,
        opportunity_score=90.0,
        expires_at=None,
        atr=2.0,
        bars=_breakout_long_bars(100.0),
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
        market_regime=None,
    )
    assert plan["status"] == "TRIGGERED"
    assert plan["entrySetup"] == "breakout"


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
        entry_setup="breakout",
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
    assert (
        entry_ready_from_ta(
            action="recommend_long", bias="bullish", entry_setup="breakout"
        )
        is True
    )
    assert (
        entry_ready_from_ta(
            action="recommend_long", bias="bearish", entry_setup="breakout"
        )
        is False
    )
    assert (
        entry_ready_from_ta(
            action="recommend_long",
            bias="bullish",
            exhaustion=True,
            entry_setup="breakout",
        )
        is False
    )
    assert (
        entry_ready_from_ta(
            action="recommend_long", bias="bullish", entry_setup="none"
        )
        is False
    )
    assert (
        entry_ready_from_ta(
            action="recommend_short", bias="bearish", entry_setup="pullback"
        )
        is True
    )
    assert entry_ready_from_ta(action="wait", bias="bullish", entry_setup="breakout") is False


def test_classify_breakout_and_none() -> None:
    assert (
        classify_entry_setup(action="recommend_long", bars=_breakout_long_bars())
        == "breakout"
    )
    assert classify_entry_setup(action="recommend_long", bars=None) == "none"
    flat = [_bar(close=100.0, high=100.5, low=99.5) for _ in range(21)]
    assert classify_entry_setup(action="recommend_long", bars=flat, atr=2.0) != "breakout"


def test_v0_dict_golden_a_with_equity() -> None:
    bars = _breakout_long_bars(100.0)
    plan = build_v0_trade_plan_dict(
        decision_id="A",
        instrument_id="MSFT",
        action="recommend_long",
        entry=100.0,
        opportunity_score=94.0,
        expires_at=None,
        atr=2.0,
        bars=bars,
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    stop = plan["structuralStop"]
    assert plan["status"] == "TRIGGERED"
    assert plan["entrySetup"] == "breakout"
    assert isinstance(stop, float)
    assert plan["quantity"] == compute_risk_size(
        equity=100_000, risk_pct=0.5, entry=100.0, stop=stop
    )
    assert plan["executionAllowed"] is True


def test_v0_dict_bias_ok_without_setup_watch_entry() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="B",
        instrument_id="NVDA",
        action="recommend_long",
        entry=100.0,
        opportunity_score=98.0,
        expires_at=None,
        atr=2.0,
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    assert plan["status"] == "WATCH"
    assert plan["entrySetup"] == "none"
    assert "entry" in plan["whyNot"]
    assert plan["executionAllowed"] is False


def test_v0_dict_bias_mismatch_watch_entry() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="B2",
        instrument_id="NVDA",
        action="recommend_long",
        entry=100.0,
        opportunity_score=98.0,
        expires_at=None,
        atr=2.0,
        bars=_breakout_long_bars(100.0),
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
    assert plan["entrySetup"] == "none"


def test_golden_d_farther_stop_reduces_size_not_stop() -> None:
    near_bars = _breakout_long_bars(100.0)
    near = build_v0_trade_plan_dict(
        decision_id="D1",
        instrument_id="IBM",
        action="recommend_long",
        entry=100.0,
        opportunity_score=80.0,
        expires_at=None,
        atr=2.0,
        bars=near_bars,
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    # Breakout window (highs < 100) + swing lows at 90 + last breakout close.
    closed = [
        _bar(close=98.0, high=99.0, low=90.0) for _ in range(BREAKOUT_LOOKBACK)
    ]
    last = _bar(close=101.0, high=101.0, low=99.0)
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
    assert far["entrySetup"] == "breakout"
