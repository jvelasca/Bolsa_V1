"""XL-3 LiveOrder domain tests — UNKNOWN / PARTIAL / no re-POST."""

from __future__ import annotations

import pytest
from bolsa_application.live_order_query import (
    BrokerOrderQueryResult,
    MockLiveOrderQuery,
)

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    LiveOrderTransitionError,
    build_live_order,
    can_transition_live_order,
    forbid_execute_trade_for_partial,
    forbid_repost_from_unknown,
    transition_live_order,
)


def test_unknown_cannot_transition_to_submitting() -> None:
    assert can_transition_live_order("UNKNOWN", "SUBMITTING") is False
    order = build_live_order(
        order_id="lo-1",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        status="UNKNOWN",
    )
    with pytest.raises(LiveOrderTransitionError, match="UNKNOWN → SUBMITTING"):
        transition_live_order(order, "SUBMITTING")


def test_timeout_path_submitting_to_unknown() -> None:
    order = build_live_order(
        order_id="lo-2",
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
    )
    submitting = transition_live_order(order, "SUBMITTING")
    unknown = transition_live_order(submitting, "UNKNOWN")
    assert unknown.status == "UNKNOWN"
    with pytest.raises(LiveOrderTransitionError, match="re-POST"):
        forbid_repost_from_unknown(unknown)


def test_partial_qty_honesty_and_execute_trade_veto() -> None:
    order = build_live_order(
        order_id="lo-3",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
    )
    working = transition_live_order(
        transition_live_order(
            transition_live_order(order, "SUBMITTING"),
            "SUBMITTED",
            venue_order_id="xtb-1",
        ),
        "WORKING",
    )
    partial = transition_live_order(
        working, "PARTIAL", filled_quantity=40.0
    )
    assert partial.filled_quantity == 40.0
    assert partial.remaining_quantity == 60.0
    with pytest.raises(LiveOrderTransitionError, match="PARTIAL"):
        forbid_execute_trade_for_partial(partial)


def test_duplicate_filled_single_financial_apply() -> None:
    from bolsa_analytics.cognitive.live_order import LiveOrder

    working = LiveOrder(
        order_id="lo-4",
        status="WORKING",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=5.0,
        filled_quantity=0.0,
        remaining_quantity=5.0,
        venue_order_id="xtb-1",
        intent_id=None,
        financial_apply_count=0,
    )
    first = transition_live_order(working, "FILLED", apply_financial=True)
    assert first.financial_apply_count == 1

    # Duplicate FILLED event path: already counted once → stays at the recorded
    # marker (idempotent; the count never collapses or decrements). We seed a
    # pre-existing marker of 2 (e.g. replayed/reloaded row) to prove the field
    # is monotonic: it must NOT be reset back to 1.
    working_again = LiveOrder(
        order_id="lo-4",
        status="WORKING",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=5.0,
        filled_quantity=0.0,
        remaining_quantity=5.0,
        venue_order_id="xtb-1",
        intent_id=None,
        financial_apply_count=2,
    )
    second = transition_live_order(working_again, "FILLED", apply_financial=True)
    assert second.financial_apply_count == 2  # nunca vuelve a 1 ni a 0


def test_apply_financial_count_increments_once() -> None:
    """apply_financial registra la primera aplicación; repetir es idempotente.

    El marker ``financial_apply_count`` debe comportarse como "primera vez" vs
    "repetida": tras aplicar una vez pasa a >=1 y NUNCA decrece ni resetea a 1.
    """
    from bolsa_analytics.cognitive.live_order import LiveOrder

    def _working(*, applied: int) -> LiveOrder:
        return LiveOrder(
            order_id="lo-a",
            status="WORKING",
            venue="LIVE",
            instrument_id="inst-1",
            side="buy",
            quantity=10.0,
            filled_quantity=0.0,
            remaining_quantity=10.0,
            venue_order_id="xtb-a",
            intent_id=None,
            financial_apply_count=applied,
        )

    # Primera vez: 0 → 1 y el llamador puede ver que acaba de aplicarse (==1).
    first = transition_live_order(_working(applied=0), "FILLED", apply_financial=True)
    assert first.status == "FILLED"
    assert first.financial_apply_count == 1

    # Dup / ya aplicado (marker pre-existente elevado) → se conserva, sin reset.
    already = transition_live_order(_working(applied=1), "FILLED", apply_financial=True)
    assert already.financial_apply_count == 1

    # Incluso con marker artificialmente >1 → se conserva (monotónico, nunca colapsa a 1).
    higher = transition_live_order(_working(applied=3), "FILLED", apply_financial=True)
    assert higher.financial_apply_count == 3

    # apply_financial sin llegar a FILLED está vetado (PARTIAL legal llega a la
    # rama financiera: filled en (0, qty) pasa los guards y aterriza en el veto).
    with pytest.raises(LiveOrderTransitionError, match="financial apply only"):
        transition_live_order(
            _working(applied=0), "PARTIAL", filled_quantity=5, apply_financial=True
        )


def test_duplicate_filled_single_financial_apply_no_terminal_reapply() -> None:
    """FILLED terminal no admite reaplicación financiera por segunda transición."""
    from bolsa_analytics.cognitive.live_order import LiveOrder

    filled = LiveOrder(
        order_id="lo-t",
        status="FILLED",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=5.0,
        filled_quantity=5.0,
        remaining_quantity=0.0,
        venue_order_id="xtb-1",
        intent_id=None,
        financial_apply_count=1,
    )
    # Estado terminal: jamás resucita ni se reaplica con otra transición.
    with pytest.raises(LiveOrderTransitionError):
        transition_live_order(filled, "FILLED", apply_financial=True)
    assert filled.financial_apply_count == 1


def _working_full(*, quantity: float = 100.0) -> LiveOrder:
    """WORKING legal vía el grafo (AUTHORIZED→SUBMITTING→SUBMITTED→WORKING)."""
    order = build_live_order(
        order_id="lo-f",
        instrument_id="inst-1",
        side="buy",
        quantity=quantity,
    )
    return transition_live_order(
        transition_live_order(
            transition_live_order(order, "SUBMITTING"),
            "SUBMITTED",
            venue_order_id="xtb-f",
        ),
        "WORKING",
    )


def test_filled_requires_full_filled_quantity_no_silent_normalize() -> None:
    """FILLED con filled < quantity es desacuerdo broker-truth → fail-closed.

    Nunca se persiste un FILLED terminal con remaining=0 y filled parcial; eso
    normalizaría silenciosamente una incoherencia (reconciliation required).
    """
    working = _working_full(quantity=100.0)
    with pytest.raises(LiveOrderTransitionError, match="reconciliation required"):
        transition_live_order(working, "FILLED", filled_quantity=80.0)

    # El detector no muta la orden origen (sigue WORKING, sin rastro de FILLED).
    assert working.status == "WORKING"
    assert working.filled_quantity == 0.0
    assert working.remaining_quantity == 100.0


def test_filled_without_filled_quantity_captures_full_order() -> None:
    """FILLED sin filled_quantity explícito → filled == quantity, remaining 0."""
    working = _working_full(quantity=50.0)
    filled_state = transition_live_order(working, "FILLED")
    assert filled_state.status == "FILLED"
    assert filled_state.filled_quantity == 50.0
    assert filled_state.remaining_quantity == 0.0


def test_filled_with_exact_quantity_is_kept_as_full() -> None:
    working = _working_full(quantity=200.0)
    filled_state = transition_live_order(working, "FILLED", filled_quantity=200.0)
    assert filled_state.status == "FILLED"
    assert filled_state.filled_quantity == 200.0
    assert filled_state.remaining_quantity == 0.0


@pytest.mark.asyncio
async def test_query_broker_resolves_unknown_without_repost() -> None:
    order = build_live_order(
        order_id="lo-5",
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
        status="UNKNOWN",
    )
    with pytest.raises(LiveOrderTransitionError, match="re-POST"):
        forbid_repost_from_unknown(order)
    mock = MockLiveOrderQuery(
        BrokerOrderQueryResult(
            outcome="filled",
            venue_order_id="xtb-q-1",
            filled_quantity=10.0,
            remaining_quantity=0.0,
        )
    )
    result = await mock.query_broker_order(venue_order_id="xtb-q-1")
    assert mock.calls == 1
    nxt = result.to_live_status()
    assert nxt == "FILLED"
    resolved = transition_live_order(
        order, nxt, filled_quantity=10.0, venue_order_id="xtb-q-1"
    )
    assert resolved.status == "FILLED"


# ---------------------------------------------------------------------------
# V2.12 honest cancel hardening (pure domain: the store's cancel is domain +
# persistence; these assert the machine refuses resurrection/double-terminal and
# allows cancel from in-flight / UNKNOWN).
# ---------------------------------------------------------------------------


def _submitted(*, order_id: str = "lo-c", venue_order_id: str = "xtb-c") -> LiveOrder:
    """SUBMITTED machine via legal graph transitions."""
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
    )
    return transition_live_order(
        transition_live_order(order, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id=venue_order_id,
    )


def test_cancel_from_submitted_and_unknown_are_legal() -> None:
    submitted = _submitted()
    assert can_transition_live_order(submitted.status, "CANCELLED")
    assert transition_live_order(submitted, "CANCELLED").status == "CANCELLED"

    unknown = transition_live_order(submitted, "UNKNOWN")
    # UNKNOWN → CANCELLED es legal (UNKNOWN se resuelve vía query/cancel, no re-POST).
    assert can_transition_live_order("UNKNOWN", "CANCELLED")
    assert transition_live_order(unknown, "CANCELLED").status == "CANCELLED"


def test_cancel_of_terminal_filled_rejected_is_refused() -> None:
    submitted = _submitted()
    rejected = transition_live_order(submitted, "REJECTED")
    filled = LiveOrder(
        order_id="lo-cf",
        status="FILLED",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        filled_quantity=100.0,
        remaining_quantity=0.0,
        venue_order_id="xtb-cf",
        intent_id=None,
        financial_apply_count=0,
    )
    for order in (filled, rejected):
        assert can_transition_live_order(order.status, "CANCELLED") is False
        with pytest.raises(LiveOrderTransitionError):
            transition_live_order(order, "CANCELLED")


def test_cancel_single_terminal_no_resurrection() -> None:
    working = _submitted(order_id="lo-c", venue_order_id="xtb-c")
    working = transition_live_order(working, "WORKING", venue_order_id="xtb-c")
    cancelled = transition_live_order(working, "CANCELLED")
    assert cancelled.status == "CANCELLED"

    # Ya cancelada (estado terminal único): no admite transición y una orden
    # terminada jamás resucita a FILLED/en curso.
    assert can_transition_live_order("CANCELLED", "CANCELLED") is False
    with pytest.raises(LiveOrderTransitionError):
        transition_live_order(cancelled, "CANCELLED")
    with pytest.raises(LiveOrderTransitionError):
        transition_live_order(cancelled, "FILLED", filled_quantity=100.0)


# ---------------------------------------------------------------------------
# V2.13 Reconcile (order-level, read-only) — broker-truth vs machine local.
# ---------------------------------------------------------------------------


def _working_qty(*, order_id: str = "lo-r", quantity: float = 100.0) -> LiveOrder:
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=quantity,
    )
    order = transition_live_order(order, "SUBMITTING")
    order = transition_live_order(order, "SUBMITTED", venue_order_id=f"xtb-{order_id}")
    return transition_live_order(order, "WORKING")


def test_reconcile_filled_partial_is_reconciliation_required() -> None:
    """Broker FILLED con filled < quantity NO es terminal coherente → recon."""
    from bolsa_analytics.cognitive.live_order import reconcile_live_order_vs_broker

    working = _working_qty(quantity=100.0)
    report = reconcile_live_order_vs_broker(
        order=working,
        broker_status="filled",
        broker_filled=60.0,
    )
    assert report.status == "reconciliation_required"


def test_reconcile_filled_full_is_consistent() -> None:
    from bolsa_analytics.cognitive.live_order import reconcile_live_order_vs_broker

    working = _working_qty(quantity=100.0)
    report = reconcile_live_order_vs_broker(
        order=working,
        broker_status="filled",
        broker_filled=100.0,
    )
    assert report.status == "consistent"


def test_reconcile_partial_out_of_bounds_is_required() -> None:
    from bolsa_analytics.cognitive.live_order import reconcile_live_order_vs_broker

    working = _working_qty(quantity=100.0)
    # partial completo (> qty) o negativo → no es partial coherente.
    bad = reconcile_live_order_vs_broker(
        order=working,
        broker_status="partial",
        broker_filled=120.0,
    )
    assert bad.status == "reconciliation_required"
    ok = reconcile_live_order_vs_broker(
        order=working,
        broker_status="partial",
        broker_filled=40.0,
    )
    assert ok.status == "consistent"


def test_reconcile_broker_working_vs_local_terminal_is_required() -> None:
    from bolsa_analytics.cognitive.live_order import (
        reconcile_live_order_vs_broker,
        transition_live_order,
    )

    cancelled = transition_live_order(_working_qty(), "CANCELLED")
    report = reconcile_live_order_vs_broker(
        order=cancelled,
        broker_status="working",
        broker_filled=None,
    )
    assert report.status == "reconciliation_required"

    # Broker corrobora CANCELLED → consistent.
    ok = reconcile_live_order_vs_broker(
        order=cancelled,
        broker_status="cancelled",
        broker_filled=None,
    )
    assert ok.status == "consistent"


def test_reconcile_broker_unavailable_is_not_conclusive() -> None:
    from bolsa_analytics.cognitive.live_order import reconcile_live_order_vs_broker

    report = reconcile_live_order_vs_broker(
        order=_working_qty(),
        broker_status="unavailable",
        broker_filled=None,
    )
    assert report.status == "unavailable"
    assert report.to_dict()["reconciliationRequired"] is False


def test_cancel_requested_is_intent_not_confirmed_result() -> None:
    """H5 · Decisión local de cancelar = CANCEL_REQUESTED (NO terminal, no CANCELLED)."""
    from bolsa_analytics.cognitive.live_order import (
        NON_TERMINAL_LIVE_STATUSES,
        _TERMINAL,
    )

    submitted = _working_qty()  # estado en-vuelo (WORKING)
    # Cualquier estado en-vuelo puede decidir cancelar → CANCEL_REQUESTED.
    requested = transition_live_order(submitted, "CANCEL_REQUESTED")
    assert requested.status == "CANCEL_REQUESTED"
    # NO es terminal: sigue in-flight/open, lista a resolverse por el broker.
    assert requested.status not in _TERMINAL
    assert requested.status in NON_TERMINAL_LIVE_STATUSES
    # No re-transiciona a sí misma (idempotente no-op).
    assert can_transition_live_order("CANCEL_REQUESTED", "CANCEL_REQUESTED") is False


def test_cancel_requested_reaches_cancelled_only_via_confirmation() -> None:
    """Tras decisión local, CANCELLED solo llega cuando el broker confirma."""
    from bolsa_analytics.cognitive.live_order import _TERMINAL

    requested = transition_live_order(_working_qty(), "CANCEL_REQUESTED")
    # El broker confirma → terminal CANCELLED (resultado real).
    confirmed = transition_live_order(requested, "CANCELLED")
    assert confirmed.status == "CANCELLED"
    assert confirmed.status in _TERMINAL


def test_cancel_requested_is_open_not_closed_for_reconcile() -> None:
    """Una CANCEL_REQUESTED pendiente NO se presenta como cancelled del vértice."""
    from bolsa_analytics.cognitive.live_order import reconcile_live_order_vs_broker

    requested = transition_live_order(_working_qty(), "CANCEL_REQUESTED")
    # Broker aun no confirma (working): local no debe inventar un CANCELLED.
    report = reconcile_live_order_vs_broker(
        order=requested,
        broker_status="working",
        broker_filled=None,
    )
    assert report.status == "consistent"  # local request no es contradicción con working

