"""TradePlan v0 — golden A/B/C/D/G/H (ADR-031) + Ciclo 4.0–4.5."""

from types import SimpleNamespace

from bolsa_analytics.cognitive.trade_plan import (
    ARMED_ACTIONABILITY,
    ATR_MULT,
    BREAKOUT_LOOKBACK,
    WYCKOFF_PRIOR,
    WYCKOFF_RECLAIM_ATR_K,
    WYCKOFF_SPRING,
    _detect_wyckoff_lps,
    _wyckoff_phase_evidence,
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
    closed = [
        _bar(close=entry - 2, high=entry - 1, low=entry - 3) for _ in range(BREAKOUT_LOOKBACK)
    ]
    last = _bar(close=entry + 1, high=entry + 1, low=entry - 1)
    return [*closed, last]


def _wyckoff_spring_base() -> tuple[list[SimpleNamespace], list[SimpleNamespace]]:
    """Prior 10 (lows 90) + spring 5 (lows 85, highs 88) — spring true long."""
    prior = [_bar(close=92, high=95, low=90) for _ in range(WYCKOFF_PRIOR)]
    spring = [_bar(close=86, high=88, low=85) for _ in range(WYCKOFF_SPRING)]
    return prior, spring


def _wyckoff_weak_reclaim_bars() -> list[SimpleNamespace]:
    """Stub 4.2: close > spring_low pero sin k×ATR ni fuera del rango spring."""
    prior, spring = _wyckoff_spring_base()
    # spring_low=85; con atr=2, umbral=85.5 — close=85.2 falla formal
    last = _bar(close=85.2, high=85.3, low=85.0)
    return [*prior, *spring, last]


def _wyckoff_formal_reclaim_bars() -> list[SimpleNamespace]:
    """Spring + reclaim formal: close > max(high) del spring; low > ice → LPS."""
    prior, spring = _wyckoff_spring_base()
    last = _bar(close=89.0, high=89.0, low=86.0)
    return [*prior, *spring, last]


def _wyckoff_reclaim_without_lps_bars() -> list[SimpleNamespace]:
    """Reclaim formal (close fuera rango) pero wick bajo spring_low → LPS false."""
    prior, spring = _wyckoff_spring_base()
    last = _bar(close=89.0, high=89.0, low=84.0)  # ice=85
    return [*prior, *spring, last]


def _wyckoff_and_breakout_bars() -> list[SimpleNamespace]:
    """Ambos matchean → prioridad breakout."""
    pad = [_bar(close=92, high=94, low=90) for _ in range(5)]
    prior, spring = _wyckoff_spring_base()
    last = _bar(close=96.0, high=96.0, low=90.0)
    return [*pad, *prior, *spring, last]


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
    assert (
        compute_structural_stop(action="recommend_long", entry=100.0, atr=2.0)
        == 100.0 - ATR_MULT * 2.0
    )
    assert (
        compute_structural_stop(action="recommend_short", entry=100.0, atr=2.0)
        == 100.0 + ATR_MULT * 2.0
    )


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
        entry_ready_from_ta(action="recommend_long", bias="bullish", entry_setup="breakout") is True
    )
    assert (
        entry_ready_from_ta(action="recommend_long", bias="bearish", entry_setup="breakout")
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
    assert entry_ready_from_ta(action="recommend_long", bias="bullish", entry_setup="none") is False
    assert (
        entry_ready_from_ta(action="recommend_short", bias="bearish", entry_setup="pullback")
        is True
    )
    assert entry_ready_from_ta(action="wait", bias="bullish", entry_setup="breakout") is False


def test_classify_breakout_and_none() -> None:
    assert classify_entry_setup(action="recommend_long", bars=_breakout_long_bars()) == "breakout"
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


def test_v0_dict_bias_mismatch_armed() -> None:
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
    assert plan["status"] == "ARMED"
    assert plan["entrySetup"] == "breakout"
    assert "entry" in plan["whyNot"]
    assert plan["quantity"] == 0.0
    assert plan["executionAllowed"] is False
    assert plan["actionability"] == ARMED_ACTIONABILITY


def test_armed_stop_breakout_without_bias() -> None:
    """Ciclo 4.3: stop + setup ≠ none + !ready → ARMED."""
    plan = build_v0_trade_plan_dict(
        decision_id="ARMED1",
        instrument_id="MSFT",
        action="recommend_long",
        entry=100.0,
        opportunity_score=90.0,
        expires_at=None,
        atr=2.0,
        bars=_breakout_long_bars(100.0),
        bias=None,
        equity=100_000,
        risk_pct=0.5,
    )
    assert plan["status"] == "ARMED"
    assert plan["entrySetup"] == "breakout"
    assert plan["quantity"] == 0.0
    assert plan["executionAllowed"] is False
    assert "entry" in plan["whyNot"]
    assert plan["actionability"] == ARMED_ACTIONABILITY


def test_armed_exhaustion_with_breakout() -> None:
    plan = build_trade_plan(
        decision_id="ARMED2",
        instrument_id="AMD",
        action="recommend_long",
        entry_ready=False,
        entry=100.0,
        structural_stop=95.0,
        equity=100_000,
        entry_setup="breakout",
    )
    assert plan.status == "ARMED"
    assert plan.quantity == 0.0
    assert plan.execution_allowed is False
    assert "entry" in plan.why_not
    assert plan.actionability == ARMED_ACTIONABILITY


def test_confirm_rebuild_without_bars_not_armed() -> None:
    """D5: sin barras → setup none; no inventa ARMED (WATCH/no_stop)."""
    plan = build_v0_trade_plan_dict(
        decision_id="CONFIRM",
        instrument_id="SAP",
        action="recommend_long",
        entry=100.0,
        opportunity_score=None,
        expires_at=None,
    )
    assert plan["status"] == "WATCH"
    assert plan["entrySetup"] == "none"
    assert plan["status"] != "ARMED"
    assert "no_stop" in plan["whyNot"]


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
    closed = [_bar(close=98.0, high=99.0, low=90.0) for _ in range(BREAKOUT_LOOKBACK)]
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


def test_wyckoff_weak_reclaim_is_none() -> None:
    """Ciclo 4.4: stub 4.2 (close ≈ spring_low) ya no clasifica wyckoff."""
    atr = 2.0
    bars = _wyckoff_weak_reclaim_bars()
    assert classify_entry_setup(action="recommend_long", bars=bars, atr=atr) == "none"
    # Umbral ATR no alcanzado
    spring_low = 85.0
    assert 85.2 < spring_low + WYCKOFF_RECLAIM_ATR_K * atr


def test_wyckoff_formal_reclaim_triggered() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="W1",
        instrument_id="XOM",
        action="recommend_long",
        entry=89.0,
        opportunity_score=80.0,
        expires_at=None,
        atr=2.0,
        bars=_wyckoff_formal_reclaim_bars(),
        bias="bullish",
        equity=100_000,
        risk_pct=0.5,
    )
    assert plan["entrySetup"] == "wyckoff"
    assert plan["status"] == "TRIGGERED"
    assert plan["quantity"] > 0
    assert plan["executionAllowed"] is True


def test_wyckoff_formal_without_bias_armed() -> None:
    plan = build_v0_trade_plan_dict(
        decision_id="W2",
        instrument_id="XOM",
        action="recommend_long",
        entry=89.0,
        opportunity_score=80.0,
        expires_at=None,
        atr=2.0,
        bars=_wyckoff_formal_reclaim_bars(),
        bias=None,
        equity=100_000,
        risk_pct=0.5,
    )
    assert plan["entrySetup"] == "wyckoff"
    assert plan["status"] == "ARMED"
    assert plan["quantity"] == 0.0
    assert "entry" in plan["whyNot"]


def test_breakout_priority_over_wyckoff() -> None:
    bars = _wyckoff_and_breakout_bars()
    assert classify_entry_setup(action="recommend_long", bars=bars, atr=2.0) == "breakout"


def test_wyckoff_reclaim_without_lps_still_wyckoff() -> None:
    """Ciclo 4.5 D2: LPS no es gate — reclaim sin LPS sigue wyckoff."""
    atr = 2.0
    bars = _wyckoff_reclaim_without_lps_bars()
    assert classify_entry_setup(action="recommend_long", bars=bars, atr=atr) == "wyckoff"
    assert _detect_wyckoff_lps(direction="long", bars=bars, atr=atr) is False
    assert _wyckoff_phase_evidence(direction="long", bars=bars, atr=atr) == "reclaim"


def test_wyckoff_lps_true_with_reclaim() -> None:
    """Spring + reclaim + low sobre hielo → LPS etiqueta; setup sigue wyckoff."""
    atr = 2.0
    bars = _wyckoff_formal_reclaim_bars()
    assert classify_entry_setup(action="recommend_long", bars=bars, atr=atr) == "wyckoff"
    assert _detect_wyckoff_lps(direction="long", bars=bars, atr=atr) is True
    assert _wyckoff_phase_evidence(direction="long", bars=bars, atr=atr) == "lps"


def test_wyckoff_lps_false_without_reclaim() -> None:
    """Sin reclaim formal → LPS false; setup none."""
    atr = 2.0
    bars = _wyckoff_weak_reclaim_bars()
    assert classify_entry_setup(action="recommend_long", bars=bars, atr=atr) == "none"
    assert _detect_wyckoff_lps(direction="long", bars=bars, atr=atr) is False
    assert _wyckoff_phase_evidence(direction="long", bars=bars, atr=atr) == "spring"


def test_wyckoff_phase_evidence_none_without_bars() -> None:
    assert _wyckoff_phase_evidence(direction="long", bars=[], atr=2.0) == "none"
