"""PositionLedger — la posición es Σ fills APLICADOS (AUTO 2.0 · AUTO-1A · P0)."""

from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE, MEASUREMENT_PARTIAL
from bolsa_analytics.cognitive.position_ledger import (
    AppliedFillFact,
    build_position_ledger,
    coerce_applied_fill_fact,
    ledger_quantities,
)


def _buy(execution_id: str, qty: float, price: float, at: str | None = None) -> AppliedFillFact:
    return AppliedFillFact(
        execution_id=execution_id,
        instrument_id="AAA",
        side="buy",
        quantity=qty,
        price=price,
        applied_at=at,
    )


def _sell(
    execution_id: str, qty: float, price: float, at: str | None = None
) -> AppliedFillFact:
    return AppliedFillFact(
        execution_id=execution_id,
        instrument_id="AAA",
        side="sell",
        quantity=qty,
        price=price,
        applied_at=at,
    )


def test_empty_ledger_is_complete_and_flat() -> None:
    ledger = build_position_ledger(())
    assert ledger.measurement == MEASUREMENT_COMPLETE
    assert ledger.positions == ()
    assert ledger.quantities() == {}
    assert ledger.is_complete is True


def test_partial_entry_materializes_only_applied_fills() -> None:
    """Caso auditoría: BUY 100 con fills 50 + 23,5 ⇒ posición 73,5 (no 100)."""
    ledger = build_position_ledger([_buy("e1", 50.0, 100.0), _buy("e2", 23.5, 100.0)])
    position = ledger.position("AAA")
    assert position is not None
    assert position.quantity == 73.5
    assert position.remaining_qty == 73.5
    assert position.realized_qty == 0.0
    assert position.average_entry == 100.0
    assert position.is_open is True
    assert ledger.quantities() == {"AAA": 73.5}
    assert ledger.facts_applied == 2
    assert ledger.violations == ()


def test_weighted_average_entry() -> None:
    ledger = build_position_ledger([_buy("e1", 50.0, 100.0), _buy("e2", 50.0, 102.0)])
    position = ledger.position("AAA")
    assert position is not None
    assert position.average_entry == 101.0
    assert position.cost_basis == round(100.0 * 101.0, 4)


def test_partial_exit_realizes_pnl_and_keeps_position_open() -> None:
    ledger = build_position_ledger(
        [_buy("e1", 50.0, 100.0), _buy("e2", 50.0, 102.0), _sell("e3", 40.0, 110.0)]
    )
    position = ledger.position("AAA")
    assert position is not None
    assert position.quantity == 100.0
    assert position.realized_qty == 40.0
    assert position.remaining_qty == 60.0
    assert position.average_entry == 101.0
    # 40 × (110 − 101) = 360
    assert position.realized_pnl == 360.0
    assert position.is_open is True
    assert ledger.measurement == MEASUREMENT_COMPLETE


def test_full_exit_flattens_and_is_not_published_as_open() -> None:
    ledger = build_position_ledger([_buy("e1", 73.5, 100.0), _sell("e2", 73.5, 104.0)])
    position = ledger.position("AAA")
    assert position is not None
    assert position.remaining_qty == 0.0
    assert position.is_flat is True
    assert position.realized_pnl == round(73.5 * 4.0, 4)
    # La posición cerrada NO aparece como cantidad viva (no reabre nada aguas abajo).
    assert ledger.quantities() == {}


def test_oversell_is_a_declared_violation_not_an_invented_short() -> None:
    """Vender más de lo materializado: violación explícita, nunca posición negativa."""
    ledger = build_position_ledger(
        [_buy("e1", 50.0, 100.0), _buy("e2", 23.5, 100.0), _sell("e3", 100.0, 110.0)]
    )
    position = ledger.position("AAA")
    assert position is not None
    assert position.remaining_qty == 0.0
    assert position.realized_qty == 100.0
    assert "oversell_above_position:e3" in position.violations
    assert ledger.violations == ("AAA:oversell_above_position:e3",)
    # El P&L solo se realiza sobre lo que existía: 73,5 × (110 − 100).
    assert position.realized_pnl == 735.0


def test_sell_without_any_buy_is_a_violation() -> None:
    ledger = build_position_ledger([_sell("e1", 10.0, 100.0)])
    position = ledger.position("AAA")
    assert position is not None
    assert position.remaining_qty == 0.0
    assert position.realized_pnl == 0.0
    assert position.violations == ("oversell_without_position:e1",)


def test_fold_is_deterministic_regardless_of_input_order() -> None:
    facts = [_buy("e1", 50.0, 100.0), _sell("e2", 10.0, 120.0), _buy("e3", 23.5, 102.0)]
    forward = build_position_ledger(facts)
    backward = build_position_ledger(reversed(facts))
    assert forward.to_dict() == backward.to_dict()
    position = forward.position("AAA")
    assert position is not None
    assert position.remaining_qty == 63.5


def test_rejected_facts_lower_measurement_instead_of_disappearing() -> None:
    ledger = build_position_ledger([_buy("e1", 50.0, 100.0)], rejected=2)
    assert ledger.measurement == MEASUREMENT_PARTIAL
    assert ledger.is_complete is False
    assert ledger.facts_rejected == 2


def test_coerce_rejects_uninterpretable_rows() -> None:
    assert (
        coerce_applied_fill_fact(
            execution_id="e1",
            instrument_id="AAA",
            side="buy",
            quantity=50.0,
            price=100.0,
        )
        is not None
    )
    for bad in (
        {"side": "hold"},
        {"quantity": 0.0},
        {"price": -1.0},
        {"instrument_id": ""},
        {"execution_id": " "},
    ):
        kwargs: dict[str, object] = {
            "execution_id": "e1",
            "instrument_id": "AAA",
            "side": "buy",
            "quantity": 50.0,
            "price": 100.0,
        }
        kwargs.update(bad)
        assert coerce_applied_fill_fact(**kwargs) is None, bad


def test_ledger_quantities_accepts_serialized_form() -> None:
    ledger = build_position_ledger([_buy("e1", 73.5, 100.0)])
    assert ledger_quantities(ledger) == {"AAA": 73.5}
    assert ledger_quantities(ledger.to_dict()) == {"AAA": 73.5}
    assert ledger_quantities(None) == {}


def test_multiple_instruments_are_grouped_and_sorted() -> None:
    ledger = build_position_ledger(
        [
            AppliedFillFact(
                execution_id="z1", instrument_id="ZZZ", side="buy", quantity=1.0, price=10.0
            ),
            AppliedFillFact(
                execution_id="a1", instrument_id="AAA", side="buy", quantity=2.0, price=20.0
            ),
        ]
    )
    assert [p.instrument_id for p in ledger.positions] == ["AAA", "ZZZ"]
    assert ledger.quantities() == {"AAA": 2.0, "ZZZ": 1.0}
