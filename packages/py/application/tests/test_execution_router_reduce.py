"""V1.45 — Router reduce qty resolution + signal_kind."""

from __future__ import annotations

from bolsa_application.execution_router import (
    resolve_exit_sell_quantity,
    signal_kind_to_trade_type,
)


def test_signal_kind_reduce_is_sell() -> None:
    assert signal_kind_to_trade_type("reduce") == "sell"
    assert signal_kind_to_trade_type("exit") == "sell"


def test_exit_full_without_qty() -> None:
    qty, err = resolve_exit_sell_quantity(
        open_qty=100.0, signal_kind="exit", hit={"instrumentId": "x"}
    )
    assert err is None
    assert qty == 100.0


def test_exit_partial_with_hit_quantity() -> None:
    qty, err = resolve_exit_sell_quantity(
        open_qty=100.0,
        signal_kind="exit",
        hit={"quantity": 30.0},
    )
    assert err is None
    assert qty == 30.0


def test_reduce_requires_qty() -> None:
    qty, err = resolve_exit_sell_quantity(
        open_qty=100.0, signal_kind="reduce", hit={}
    )
    assert qty is None
    assert err == "reduce_qty_required"


def test_reduce_clamps_to_open() -> None:
    qty, err = resolve_exit_sell_quantity(
        open_qty=40.0,
        signal_kind="reduce",
        hit={"quantity": 100.0},
    )
    assert err is None
    assert qty == 40.0


def test_reduce_from_signal_nested_qty() -> None:
    qty, err = resolve_exit_sell_quantity(
        open_qty=50.0,
        signal_kind="reduce",
        hit={"signal": {"quantity": 15}},
    )
    assert err is None
    assert qty == 15.0
