"""V2.19 (P2-01/C3) — decisión del puente financiero del recovery (unit, sin PG).

Cubre la capa por-fases pura de `~recovery_apply`:
* la decisión de funding (`recovery_financial_decision`) es fail-closed: sin
  outcome fill, sin venue_order_id constatable o sin `fill_seq`/`fill_price`
  acreditados por el broker → NADA se materializa (fsm_only intacto, firewall
  H4/H6 — no se fabrica un precio de un fill).
* el candidato (`build_recovery_execution_candidate`) solo nace si el llenado es
  real (con secuencia+precio) y la identidad `execution_id` es estable.
* `recovery_idempotency_key` es estable y en rango 16..128 sin whitespace.

Toda materialización durable (CAPTURED→APPLYING→APPLIED/.../RETRY) se testea
además en `test_execution_event.py`; este fichero fija SOLO la decisión de qué
fill recuperado es candidato a salir de `fsm_only`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.live_order_query import BrokerOrderQueryResult
from bolsa_application.recovery_apply import (
    build_recovery_execution_candidate,
    recovery_financial_decision,
    recovery_idempotency_key,
)


def _order(**over) -> SimpleNamespace:
    """Stand-in con los campos del dominio LiveOrder que el recovery usa."""
    base = {
        "order_id": "lo-1",
        "venue": "LIVE",
        "account_id": "acc-1",
        "venue_order_id": "xtb-77",
        "instrument_id": "REPO",
        "side": "buy",
        "filled_quantity": "100",
    }
    base.update(over)
    return SimpleNamespace(**base)


def _filled(**over) -> BrokerOrderQueryResult:
    base = {
        "outcome": "filled",
        "venue_order_id": "xtb-77",
        "filled_quantity": "100",
        "remaining_quantity": "0",
        "fill_seq": 3,
        "fill_price": "12.50",
    }
    base.update(over)
    return BrokerOrderQueryResult(
        outcome=base["outcome"],
        venue_order_id=base["venue_order_id"],
        filled_quantity=base["filled_quantity"],
        remaining_quantity=base["remaining_quantity"],
        fill_seq=base["fill_seq"],
        fill_price=base["fill_price"],
    )


def test_filled_with_price_and_seq_decides_apply_candidate() -> None:
    order = _order()
    assert recovery_financial_decision(order, _filled()) == "apply_candidate"


@pytest.mark.parametrize(
    "outcome",
    ["working", "rejected", "cancelled", "unavailable"],
)
def test_non_fill_outcome_never_materializes(outcome: str) -> None:
    order = _order()
    assert recovery_financial_decision(order, _filled(outcome=outcome)) == "not_fill"


def test_fill_without_price_stays_fsm_only() -> None:
    """Llenado confirmado pero SIN precio acreditado → price_unknown (no money)."""
    order = _order()
    r = _filled(fill_price=None)
    assert recovery_financial_decision(order, r) == "price_unknown"
    assert build_recovery_execution_candidate(order, r) is None


def test_fill_without_sequence_stays_fsm_only() -> None:
    """Solo precio no basta: sin fill_seq no hay identity financiera → no money."""
    order = _order()
    r = _filled(fill_seq=None)
    assert recovery_financial_decision(order, r) == "price_unknown"


def test_fill_without_any_venue_id_is_not_recoverable_here() -> None:
    order = _order(venue_order_id=None)
    r = _filled(venue_order_id=None)
    assert recovery_financial_decision(order, r) == "not_recoverable_here"


def test_candidate_has_stable_execution_id_and_qty() -> None:
    """Candidato: execution_id = venue_order_id#fill_seq, qty del fill real."""
    order = _order(venue_order_id="xtb-77")
    r = _filled(fill_seq=3, fill_price="12.50", filled_quantity="100")
    ev = build_recovery_execution_candidate(order, r)
    assert ev is not None
    assert ev.execution_id == "xtb-77#3"
    assert ev.venue_order_id == "xtb-77"
    assert ev.fill_seq == 3
    assert str(ev.qty) == "100.000000"


def test_idempotency_key_is_stable_within_bounds() -> None:
    """La key financiera de ExecuteTrade es estable y cumple 16..128 sin ws."""
    a = recovery_idempotency_key("xtb-77#3")
    b = recovery_idempotency_key("xtb-77#3")
    assert a == b
    import re

    assert re.search(r"\s", a) is None
    assert 16 <= len(a) <= 128
