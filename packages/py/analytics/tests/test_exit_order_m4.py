"""M4: el remanente de una salida debe cumplir 0 <= remaining <= solicitado."""

from __future__ import annotations

from bolsa_analytics.cognitive.exit_order import build_exit_order


def _build(**kw: object):
    return build_exit_order(
        exit_order_id="x1", instrument_id="AAA", requested_qty=10.0, **kw
    )


def test_remaining_above_requested_is_rederived() -> None:
    order = _build(filled_qty=4.0, remaining_qty=99.0)
    assert order is not None
    assert order.remaining_qty == 6.0


def test_negative_remaining_is_rederived() -> None:
    order = _build(filled_qty=4.0, remaining_qty=-3.0)
    assert order is not None
    assert order.remaining_qty == 6.0


def test_consistent_remaining_is_kept() -> None:
    order = _build(filled_qty=4.0, remaining_qty=6.0)
    assert order is not None
    assert order.remaining_qty == 6.0
