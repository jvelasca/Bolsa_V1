"""OpenOrder — órdenes pendientes como capital/riesgo/exposición (AUTO 2.0 · V2.40.4)."""

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_analytics.cognitive.open_order import (
    NON_TERMINAL_APPLY_STATUSES,
    OpenOrder,
    build_open_order,
    coerce_open_order,
    summarize_open_orders,
)

# ── build_open_order ─────────────────────────────────────────────────────────


def test_buy_reserves_notional() -> None:
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=100.0,
        price=120.0,
        sector="Technology",
        risk_amount=600.0,
        trade_plan_id="tp-1",
    )
    assert order.reserved_cash == 12_000.0
    assert order.risk_amount == 600.0
    assert order.market_value == 12_000.0
    assert order.is_buy is True
    assert order.is_quantified is True
    assert order.trade_plan_id == "tp-1"


def test_sell_never_adds_risk_or_reserves_cash() -> None:
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="AAA",
        side="SELL",
        quantity=30.0,
        price=100.0,
        sector="Tech",
    )
    assert order.side == "sell"
    assert order.reserved_cash == 0.0
    assert order.risk_amount == 0.0
    assert order.is_quantified is True


def test_buy_without_risk_is_not_quantified() -> None:
    """El riesgo de una compra en vuelo NO se inventa: queda desconocido."""
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=100.0,
        price=120.0,
        sector="Technology",
    )
    assert order.reserved_cash == 12_000.0
    assert order.risk_amount is None
    assert order.is_quantified is False


def test_missing_quantity_or_price_yields_unknown_amounts() -> None:
    no_qty = build_open_order(
        execution_id="exec-1", instrument_id="NVDA", side="buy", price=120.0
    )
    assert no_qty.reserved_cash is None
    assert no_qty.market_value is None
    no_price = build_open_order(
        execution_id="exec-2", instrument_id="NVDA", side="buy", quantity=10.0
    )
    assert no_price.reserved_cash is None
    # Ni cantidad ni precio positivos (0 no es un precio).
    zero = build_open_order(
        execution_id="exec-3", instrument_id="NVDA", side="buy", quantity=10.0, price=0.0
    )
    assert zero.reserved_cash is None


def test_unknown_side_is_not_quantified() -> None:
    order = build_open_order(
        execution_id="exec-1", instrument_id="NVDA", side="mirando", quantity=10.0, price=1.0
    )
    assert order.side == ""
    assert order.reserved_cash is None
    assert order.risk_amount is None
    assert order.is_quantified is False


def test_explicit_amounts_win_over_derivation() -> None:
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=100.0,
        price=120.0,
        sector="Tech",
        reserved_cash=9_999.0,
        risk_amount=1_234.0,
    )
    assert order.reserved_cash == 9_999.0
    assert order.risk_amount == 1_234.0


def test_missing_sector_is_not_quantified() -> None:
    """Sin sector resoluble la exposición pendiente no se puede afirmar por sector."""
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=10.0,
        price=100.0,
        risk_amount=50.0,
    )
    assert order.is_quantified is False


def test_status_normalization_and_defaults() -> None:
    assert build_open_order(execution_id="e", status="applying").status == "APPLYING"
    assert build_open_order(execution_id="e", status="RETRY").status == "RETRY"
    # Un estado desconocido (o ``APPLIED``, que ya no está pendiente) cae al más
    # conservador: capturado y pendiente de resolver.
    assert build_open_order(execution_id="e", status="APPLIED").status == "CAPTURED"
    assert build_open_order(execution_id="e").status == "CAPTURED"
    assert NON_TERMINAL_APPLY_STATUSES == ("CAPTURED", "APPLYING", "RETRY", "FAILED")


def test_is_bool_safe_and_finite() -> None:
    order = build_open_order(
        execution_id="exec-1",
        instrument_id="NVDA",
        side="buy",
        quantity=True,  # bool no es una cantidad
        price="no-numero",
    )
    assert order.remaining_qty is None
    assert order.reserved_cash is None


# ── summarize_open_orders ────────────────────────────────────────────────────


def test_summary_empty_book_is_complete() -> None:
    summary = summarize_open_orders((), equity=100_000.0)
    assert summary.count == 0
    assert summary.measurement == MEASUREMENT_COMPLETE
    assert summary.reserved_cash == 0.0
    assert summary.pending_risk == 0.0
    assert summary.pending_exposure_pct == 0.0


def test_summary_without_equity_has_no_exposure_pct() -> None:
    order = build_open_order(
        execution_id="e",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        price=100.0,
        sector="Tech",
        risk_amount=50.0,
    )
    summary = summarize_open_orders((order,), equity=None)
    assert summary.pending_exposure_pct is None
    assert summary.is_complete is True


def test_summary_aggregates_cash_risk_and_exposure() -> None:
    buy = build_open_order(
        execution_id="e1",
        instrument_id="AAA",
        side="buy",
        quantity=100.0,
        price=100.0,
        sector="Tech",
        risk_amount=500.0,
    )
    sell = build_open_order(
        execution_id="e2",
        instrument_id="BBB",
        side="sell",
        quantity=40.0,
        price=50.0,
        sector="Energy",
    )
    summary = summarize_open_orders((buy, sell), equity=100_000.0)
    assert summary.reserved_cash == 10_000.0
    assert summary.pending_risk == 500.0
    assert summary.pending_exposure_pct == 10.0
    assert summary.pending_exposure_by_sector == {"Tech": 10.0}
    assert summary.pending_sell_qty == {"BBB": 40.0}
    assert summary.measurement == MEASUREMENT_COMPLETE


def test_summary_partial_when_one_order_unquantified() -> None:
    ok = build_open_order(
        execution_id="e1",
        instrument_id="AAA",
        side="buy",
        quantity=100.0,
        price=100.0,
        sector="Tech",
        risk_amount=500.0,
    )
    opaque = build_open_order(execution_id="e2", instrument_id="BBB", side="buy")
    summary = summarize_open_orders((ok, opaque), equity=100_000.0)
    assert summary.measurement == MEASUREMENT_PARTIAL
    # Los importes son suelos: suman solo lo cuantificable.
    assert summary.reserved_cash == 10_000.0
    assert summary.pending_risk == 500.0


def test_summary_unknown_when_nothing_quantified() -> None:
    opaque = build_open_order(execution_id="e1", instrument_id="AAA", side="buy")
    summary = summarize_open_orders((opaque,), equity=100_000.0)
    assert summary.measurement == MEASUREMENT_UNKNOWN


def test_summary_sector_exposure_groups_by_sector() -> None:
    a = build_open_order(
        execution_id="e1",
        instrument_id="AAA",
        side="buy",
        quantity=100.0,
        price=100.0,
        sector="Tech",
        risk_amount=500.0,
    )
    b = build_open_order(
        execution_id="e2",
        instrument_id="BBB",
        side="buy",
        quantity=100.0,
        price=100.0,
        sector="Tech",
        risk_amount=500.0,
    )
    summary = summarize_open_orders((a, b), equity=100_000.0)
    assert summary.pending_exposure_by_sector == {"Tech": 20.0}


# ── coerce_open_order ────────────────────────────────────────────────────────


def test_coerce_is_idempotent_for_dataclass() -> None:
    order = build_open_order(
        execution_id="e1", instrument_id="AAA", side="buy", quantity=10.0, price=10.0
    )
    assert coerce_open_order(order) is order


def test_coerce_mapping_and_attributes() -> None:
    from_mapping = coerce_open_order(
        {
            "executionId": "e1",
            "instrumentId": "AAA",
            "side": "SELL",
            "remainingQty": 5,
            "price": 10,
            "sector": "Tech",
            "status": "RETRY",
        }
    )
    assert from_mapping is not None
    assert from_mapping.side == "sell"
    assert from_mapping.status == "RETRY"
    assert from_mapping.reserved_cash == 0.0

    class Row:
        execution_id = "e2"
        instrument_id = "BBB"
        side = "buy"
        requested_qty = 7.0
        remaining_qty = 7.0
        price = 3.0
        risk_amount = 21.0
        sector = "Energy"

    from_attrs = coerce_open_order(Row())
    assert from_attrs is not None
    assert from_attrs.instrument_id == "BBB"
    assert from_attrs.reserved_cash == 21.0


def test_coerce_discards_rows_without_identity() -> None:
    """Sin ``execution_id`` no hay identidad de fill: la fila se descarta (fail-closed)."""
    assert coerce_open_order({}) is None
    assert coerce_open_order({"executionId": "  "}) is None
    assert coerce_open_order(object()) is None


def test_to_dict_shape() -> None:
    order = build_open_order(
        execution_id="e1",
        order_id="o1",
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        price=10.0,
        sector="Tech",
        risk_amount=5.0,
    )
    d = order.to_dict()
    assert d["executionId"] == "e1"
    assert d["reservedCash"] == 100.0
    assert d["riskAmount"] == 5.0
    assert d["status"] == "CAPTURED"
    assert isinstance(order, OpenOrder)
