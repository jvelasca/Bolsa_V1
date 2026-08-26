"""JP-1 — extract hot scalars from PositionState JSONB camelCase blob."""

from __future__ import annotations

from decimal import Decimal

from bolsa_infrastructure.database.repositories.position_state_repository import (
    hot_scalars_from_position_state,
)


def test_hot_scalars_from_position_state_maps_camel_case() -> None:
    blob = {
        "direction": "long",
        "currentStop": 95.5,
        "remainingQuantity": 7,
        "quantity": 10.0,
        "initialStop": 94,
        "actualEntry": 100.25,
        "status": "OPEN",
        "mfeMae": {"mfe": 1.0},
    }
    hot = hot_scalars_from_position_state(blob)
    assert hot["direction"] == "long"
    assert hot["current_stop"] == Decimal("95.5")
    assert hot["remaining_quantity"] == Decimal("7")
    assert hot["quantity"] == Decimal("10.0")
    assert hot["initial_stop"] == Decimal("94")
    assert hot["actual_entry"] == Decimal("100.25")


def test_hot_scalars_from_position_state_null_and_blank() -> None:
    hot = hot_scalars_from_position_state(
        {
            "direction": "  ",
            "currentStop": None,
            "remainingQuantity": "",
            "quantity": "not-a-number",
        }
    )
    assert hot["direction"] is None
    assert hot["current_stop"] is None
    assert hot["remaining_quantity"] is None
    assert hot["quantity"] is None
    assert hot["initial_stop"] is None
    assert hot["actual_entry"] is None
