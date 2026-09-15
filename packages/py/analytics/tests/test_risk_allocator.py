"""RiskAllocator — sizing por riesgo + SL/TP por ATR (AUTO 2.0 · P1)."""

from bolsa_analytics.cognitive.risk_allocator import (
    CAP_POSITION_PCT,
    CAP_RISK_PCT,
    RiskAllocatorConfig,
    compute_allocation,
    compute_atr_stop,
    compute_stop_distance,
    compute_take_profit,
)


def test_stop_distance_geometry() -> None:
    assert compute_stop_distance(entry=100.0, stop=96.0, direction="long") == 4.0
    assert compute_stop_distance(entry=100.0, stop=104.0, direction="short") == 4.0
    # Stop del lado equivocado ⇒ inválido.
    assert compute_stop_distance(entry=100.0, stop=105.0, direction="long") is None
    assert compute_stop_distance(entry=100.0, stop=95.0, direction="short") is None


def test_atr_stop_long_and_short() -> None:
    assert compute_atr_stop(entry=100.0, atr=2.0, atr_multiplier=1.8, direction="long") == 96.4
    assert compute_atr_stop(entry=100.0, atr=2.0, atr_multiplier=1.8, direction="short") == 103.6


def test_atr_stop_invalid() -> None:
    # Stop por debajo de 0 en long (ATR enorme) ⇒ None.
    assert compute_atr_stop(entry=1.0, atr=10.0, direction="long") is None
    assert compute_atr_stop(entry=0.0, atr=2.0) is None
    assert compute_atr_stop(entry=100.0, atr=0.0) is None


def test_take_profit_r() -> None:
    assert compute_take_profit(entry=100.0, stop=96.0, r_multiple=1.0, direction="long") == 104.0
    assert compute_take_profit(entry=100.0, stop=96.0, r_multiple=2.0, direction="long") == 108.0
    assert compute_take_profit(entry=100.0, stop=104.0, r_multiple=1.0, direction="short") == 96.0


def test_allocation_core_formula() -> None:
    # risk_budget 300, stop_distance 4.5 ⇒ 66.66 shares.
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.5,
        direction="long",
        risk_budget=300.0,
    )
    assert result.approved is True
    assert round(result.quantity, 2) == 66.67
    assert result.risk_amount == 300.0
    assert result.stop_distance == 4.5


def test_allocation_capped_by_position_pct() -> None:
    # Sin cap: 300/4.5 ≈ 66.67 sh = 6667€. Con max_position_pct 5% ⇒ 5000€ ⇒ 50 sh.
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.5,
        direction="long",
        risk_budget=300.0,
        config=RiskAllocatorConfig(max_position_pct=5.0),
    )
    assert result.quantity == 50.0
    assert CAP_POSITION_PCT in result.capped_reasons


def test_allocation_capped_by_risk_pct() -> None:
    # equity 100k, max_risk_per_trade_pct 0.2% ⇒ 200€. budget 1000 ⇒ se cap a 200.
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.0,
        direction="long",
        risk_budget=1000.0,
        config=RiskAllocatorConfig(max_risk_per_trade_pct=0.2),
    )
    assert result.risk_amount == 200.0
    assert CAP_RISK_PCT in result.capped_reasons
    assert result.quantity == 40.0


def test_allocation_zero_buying_power() -> None:
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.0,
        risk_budget=300.0,
        buying_power=0.0,
    )
    assert result.approved is False
    assert result.quantity == 0.0


def test_allocation_fail_closed_invalid_geometry() -> None:
    result = compute_allocation(
        equity=100_000.0, entry=100.0, stop=105.0, direction="long", risk_budget=300.0
    )
    assert result.approved is False
    assert result.quantity == 0.0


def test_allocation_no_risk_source() -> None:
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.0,
        risk_budget=None,
        config=RiskAllocatorConfig(max_risk_per_trade_pct=None),
    )
    assert result.approved is False


def test_allocation_uses_equity_pct_when_no_budget() -> None:
    result = compute_allocation(
        equity=100_000.0,
        entry=100.0,
        stop=95.0,
        direction="long",
        risk_budget=None,
        config=RiskAllocatorConfig(max_risk_per_trade_pct=1.0),
    )
    assert result.risk_amount == 1000.0
    assert result.quantity == 200.0
