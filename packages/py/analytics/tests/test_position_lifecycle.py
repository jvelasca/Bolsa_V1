"""AUTO-2 / V2.42 — FSM explícito del ciclo de vida de la posición.

Gate del roadmap: producto cartesiano de eventos con **transiciones inválidas rechazadas**,
rehidratación por estado intermedio, trailing en R que nunca empeora el stop y la garantía
de que **ninguna salida protectora se veta**.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from bolsa_analytics.cognitive.position_lifecycle import (
    ACTIVE_LIFECYCLE_STATES,
    ALLOWED_TRANSITIONS,
    DEGRADED_LIFECYCLE_STATES,
    LIFECYCLE_EVENTS,
    LIFECYCLE_RESOLUTION_MISSING,
    LIFECYCLE_STATE_KEY,
    LIFECYCLE_STATE_UNVERIFIED,
    LIFECYCLE_TRANSITION_REJECTED,
    PROTECTIVE_EXIT_ALLOWED_STATES,
    VERIFIED_LIFECYCLE_STATES,
    advance_lifecycle,
    apply_lifecycle_event,
    coerce_lifecycle_state,
    compute_trail_stop,
    derive_lifecycle_state,
    high_watermark_from_position,
    is_trail_armed,
    protection_state_name,
    trailing_is_active,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_position_mark,
    apply_position_reduce,
    build_position_state_from_fill,
    position_state_from_dict,
)

_ALL_STATES = tuple(sorted(VERIFIED_LIFECYCLE_STATES | DEGRADED_LIFECYCLE_STATES))
_ALL_EVENTS = tuple(LIFECYCLE_EVENTS)


def _plan(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decisionId": "dec-1",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    base.update(overrides)
    return base


def _open_long():
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


# --------------------------------------------------------------------------------------
# Tabla y transiciones
# --------------------------------------------------------------------------------------


def test_every_state_has_a_row() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(_ALL_STATES)


def test_unknown_state_degrades_never_advances() -> None:
    transition = apply_lifecycle_event("WATCHING", "T1_HIT")
    assert transition.accepted is True
    assert transition.to_state == "RECONCILIATION_REQUIRED"
    assert transition.reason == LIFECYCLE_STATE_UNVERIFIED
    assert apply_lifecycle_event(None, "T1_HIT").to_state == "RECONCILIATION_REQUIRED"


def test_unknown_event_is_rejected() -> None:
    transition = apply_lifecycle_event("OPEN", "MELT_UP")
    assert transition.accepted is False
    assert transition.to_state == "OPEN"
    assert transition.reason == LIFECYCLE_TRANSITION_REJECTED
    assert transition.event == "MELT_UP"


def test_invalid_transitions_are_rejected_without_advancing() -> None:
    invalid = [
        ("FLAT", "T1_HIT"),
        ("FLAT", "PROTECT_APPLIED"),
        ("ENTRY_PENDING", "PROTECT_APPLIED"),
        ("ENTRY_PENDING", "PARTIAL_FILL"),
        ("CLOSED", "ENTRY_FILLED"),
        ("CLOSED", "PROTECT_APPLIED"),
        ("CLOSED", "PARTIAL_FILL"),
        ("OPEN", "ENTRY_FILLED"),
        ("TRAILING", "ENTRY_CANCELLED"),
    ]
    for state, event in invalid:
        transition = apply_lifecycle_event(state, event)
        assert transition.accepted is False, (state, event)
        assert transition.to_state == state
        assert transition.reason == LIFECYCLE_TRANSITION_REJECTED


def test_cartesian_product_is_total_and_fail_closed() -> None:
    """Ninguna combinación (estado, evento) queda indefinida ni avanza en silencio."""
    for state in _ALL_STATES:
        for event in _ALL_EVENTS:
            transition = apply_lifecycle_event(state, event)
            if transition.accepted:
                assert transition.to_state in ALLOWED_TRANSITIONS[state]
                assert transition.reason is None
            else:
                assert transition.to_state == state
                assert transition.reason in (
                    LIFECYCLE_TRANSITION_REJECTED,
                    LIFECYCLE_RESOLUTION_MISSING,
                )


def test_protective_exit_is_never_vetoed() -> None:
    """Roadmap: ninguna salida protectora se veta por reconciliación ni medición."""
    for state in PROTECTIVE_EXIT_ALLOWED_STATES:
        to_closed = apply_lifecycle_event(state, "EXIT_FILLED")
        assert to_closed.accepted is True, state
        assert to_closed.to_state == "CLOSED"
        pending = apply_lifecycle_event(state, "EXIT_REQUESTED")
        assert pending.accepted is True, state
        assert pending.to_state == "EXIT_PENDING"


def test_degraded_states_can_recover_with_protection() -> None:
    for state in ("PROTECTION_MISSING", "RECONCILIATION_REQUIRED", "UNKNOWN"):
        transition = apply_lifecycle_event(state, "PROTECT_APPLIED")
        assert transition.accepted is True
        assert transition.to_state == "PROTECTED"


def test_reconciled_requires_verified_target() -> None:
    missing = apply_lifecycle_event("RECONCILIATION_REQUIRED", "RECONCILED")
    assert missing.accepted is False
    assert missing.to_state == "RECONCILIATION_REQUIRED"
    assert missing.reason == LIFECYCLE_RESOLUTION_MISSING

    degraded_target = apply_lifecycle_event(
        "RECONCILIATION_REQUIRED", "RECONCILED", resolved_state="UNKNOWN"
    )
    assert degraded_target.accepted is False

    # H-1 (§9 del pack): sin el HECHO de cantidad no se puede verificar la resolución.
    unverifiable = apply_lifecycle_event(
        "RECONCILIATION_REQUIRED", "RECONCILED", resolved_state="PROTECTED"
    )
    assert unverifiable.accepted is False
    assert unverifiable.reason == LIFECYCLE_RESOLUTION_MISSING

    restored = apply_lifecycle_event(
        "RECONCILIATION_REQUIRED",
        "RECONCILED",
        resolved_state="PROTECTED",
        remaining_quantity=10.0,
        quantity=10.0,
    )
    assert restored.accepted is True
    assert restored.to_state == "PROTECTED"


def test_reconciled_rejected_from_non_degraded_state() -> None:
    """H-1: ``RECONCILED`` sólo sale de una degradación; desde un estado vivo se rechaza."""
    for state in ("OPEN", "PROTECTED", "TRAILING", "EXIT_PENDING"):
        transition = apply_lifecycle_event(
            state,
            "RECONCILED",
            resolved_state="PROTECTED",
            remaining_quantity=10.0,
            quantity=10.0,
        )
        assert transition.accepted is False, state
        assert transition.to_state == state
        assert transition.reason == LIFECYCLE_RESOLUTION_MISSING


def test_reconciled_rejected_when_ledger_contradicts_target() -> None:
    """H-1: el ledger manda. ``CLOSED`` con posición viva no se "reconcilia" a ciegas."""
    transition = apply_lifecycle_event(
        "RECONCILIATION_REQUIRED",
        "RECONCILED",
        resolved_state="CLOSED",
        remaining_quantity=10.0,
        quantity=10.0,
    )
    assert transition.accepted is False
    assert transition.reason == LIFECYCLE_RESOLUTION_MISSING


def test_time_exit_and_thesis_exit_request_the_exit() -> None:
    """V2.42 slice 2b: las dos salidas nuevas piden salir desde cualquier estado vivo."""
    for state in PROTECTIVE_EXIT_ALLOWED_STATES:
        for event in ("TIME_EXIT", "THESIS_EXIT"):
            transition = apply_lifecycle_event(state, event)
            assert transition.accepted is True, (state, event)
            assert transition.to_state == "EXIT_PENDING"


def test_management_ladder_never_goes_backwards() -> None:
    """H-7 (§9 del pack): ninguna transición de gestión retrocede de estado.

    El caso que lo motivó: ``TRAILING`` + ``T1_HIT`` devolvía a ``T1_REACHED`` y
    ``PARTIAL_EXIT`` + ``PROTECT_APPLIED`` perdía la parcial.
    """
    ladder = (
        "OPEN",
        "PROTECTED",
        "T1_REACHED",
        "PARTIAL_EXIT",
        "TRAILING",
        "EXIT_PENDING",
    )
    rank = {state: i for i, state in enumerate(ladder)}
    for state in ladder:
        for event in _ALL_EVENTS:
            transition = apply_lifecycle_event(state, event)
            if not transition.accepted:
                continue
            target = transition.to_state
            if target not in rank:
                continue
            assert rank[target] >= rank[state], (state, event, target)


def test_coerce_lifecycle_state_normalizes() -> None:
    assert coerce_lifecycle_state(" open ") == "OPEN"
    assert coerce_lifecycle_state("TRAILING") == "TRAILING"
    assert coerce_lifecycle_state("nope") is None
    assert coerce_lifecycle_state(None) is None


# --------------------------------------------------------------------------------------
# Persistencia / rehidratación
# --------------------------------------------------------------------------------------


def test_lifecycle_state_survives_roundtrip() -> None:
    pos, transition = advance_lifecycle(
        replace(_open_long(), lifecycle_state="FLAT"), "ENTRY_SUBMITTED"
    )
    assert transition.accepted is True
    assert pos.lifecycle_state == "ENTRY_PENDING"
    pos, _ = advance_lifecycle(pos, "ENTRY_FILLED")
    assert pos.lifecycle_state == "OPEN"
    pos, _ = advance_lifecycle(pos, "T1_HIT")
    pos, _ = advance_lifecycle(pos, "TRAIL_ARMED", mark_trailing=True, trail_distance_r=1.0)
    assert pos.lifecycle_state == "TRAILING"

    restored = position_state_from_dict(dict(pos.to_dict()))
    assert restored is not None
    assert restored.lifecycle_state == "TRAILING"
    assert trailing_status(restored) == "active"
    assert restored.to_dict() == pos.to_dict()


def test_lifecycle_state_absent_is_not_degraded() -> None:
    """Un blob de un tag anterior no se degrada: se proyecta desde los campos legacy."""
    blob = dict(_open_long().to_dict())
    blob.pop(LIFECYCLE_STATE_KEY, None)
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.lifecycle_state is None
    assert derive_lifecycle_state(restored) == "OPEN"


def test_lifecycle_state_unknown_value_degrades_to_reconciliation_required() -> None:
    blob = dict(_open_long().to_dict())
    blob[LIFECYCLE_STATE_KEY] = "SOMETHING_NEW"
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.lifecycle_state == "RECONCILIATION_REQUIRED"
    assert protection_state_name(restored) == "RECONCILIATION_REQUIRED"


def test_lifecycle_state_roundtrip_for_every_state() -> None:
    """Reinicio por cada estado intermedio: el FSM no se pierde ni se reinterpreta."""
    for state in _ALL_STATES:
        blob = dict(_open_long().to_dict())
        blob[LIFECYCLE_STATE_KEY] = state
        if state in ("CLOSED", "FLAT"):
            # Consistencia contra el hecho de cantidad: sin posición viva.
            blob["remainingQuantity"] = 0.0
            blob["quantity"] = 10.0
        restored = position_state_from_dict(blob)
        assert restored is not None
        assert restored.lifecycle_state == state
        assert dict(restored.to_dict())[LIFECYCLE_STATE_KEY] == state


def test_inconsistent_lifecycle_degrades_on_rehydration() -> None:
    """``CLOSED`` con posición viva no es verificable ⇒ degrada, no se confía."""
    blob = dict(_open_long().to_dict())
    blob[LIFECYCLE_STATE_KEY] = "CLOSED"
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.lifecycle_state == "RECONCILIATION_REQUIRED"
    assert protection_state_name(restored) == "RECONCILIATION_REQUIRED"

    blob["remainingQuantity"] = 0.0
    blob["quantity"] = 10.0
    assert position_state_from_dict(blob).lifecycle_state == "CLOSED"  # type: ignore[union-attr]


# --------------------------------------------------------------------------------------
# Proyección legacy
# --------------------------------------------------------------------------------------


def test_derive_lifecycle_from_legacy_facts() -> None:
    assert derive_lifecycle_state(None) == "FLAT"
    assert derive_lifecycle_state(_open_long()) == "OPEN"


def test_derive_lifecycle_t1_and_partial() -> None:
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    assert derive_lifecycle_state(pos) == "T1_REACHED"

    pos, _ = advance_lifecycle(pos, "PARTIAL_FILL")
    assert derive_lifecycle_state(pos) == "PARTIAL_EXIT"


def test_derive_lifecycle_protection_name_wins() -> None:
    pos = _open_long()
    degraded = replace(pos, protection_state={"state": "PROTECTION_MISSING"})
    assert derive_lifecycle_state(degraded) == "PROTECTION_MISSING"


def test_persisted_lifecycle_wins_over_projection() -> None:
    pos = replace(_open_long(), lifecycle_state="EXIT_PENDING")
    assert derive_lifecycle_state(pos) == "EXIT_PENDING"


# --------------------------------------------------------------------------------------
# Trailing en R
# --------------------------------------------------------------------------------------


def test_trailing_status_of_birth_stub_is_inactive() -> None:
    pos = _open_long()
    assert pos.trailing == {"status": "none"}
    assert trailing_status(pos) == "inactive"
    assert trailing_is_active(pos) is False
    assert is_trail_armed(pos) is False


def test_high_watermark_tracks_the_favourable_extreme() -> None:
    pos = _open_long()
    assert high_watermark_from_position(pos) is None
    up = _mark(pos, 106.0)
    assert high_watermark_from_position(up) == 106.0
    down = _mark(up, 98.0)
    assert high_watermark_from_position(down) == 106.0
    higher = _mark(down, 109.0)
    assert high_watermark_from_position(higher) == 109.0


def test_high_watermark_of_short_takes_the_low() -> None:
    short = build_position_state_from_fill(
        _plan(direction="short", entry=100.0, structuralStop=105.0),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="s-1",
    )
    assert short is not None
    marked = _mark(_mark(short, 99.0), 104.0)
    assert high_watermark_from_position(marked) == 99.0


def test_trail_stop_not_armed_before_t1() -> None:
    pos = _mark(_open_long(), 106.0)
    assert is_trail_armed(pos) is False
    assert compute_trail_stop(pos, trail_width="medium") is None


def test_trail_stop_in_r_after_t1() -> None:
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    pos = _mark(pos, 106.0)
    assert is_trail_armed(pos) is True
    # risk = 5.0 (entry 100 − stop 95); medium = 1.0 R ⇒ 106 − 5 = 101
    assert compute_trail_stop(pos, trail_width="medium") == 101.0
    assert compute_trail_stop(pos, trail_width="tight") == 102.25
    assert compute_trail_stop(pos, trail_width="wide") == 99.75


def test_trail_stop_never_worsens() -> None:
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    pos = _mark(pos, 108.0)
    # El stop vigente (107) ya es mejor que el trailing propuesto (108 − 5 = 103).
    protected = _apply_stop(pos, 107.0)
    assert compute_trail_stop(protected, trail_width="medium") == 107.0


def test_trail_stop_needs_real_risk() -> None:
    """Sin ``initial_risk`` no hay trailing: no se sustituye por un % del precio."""
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    without_risk = replace(pos, initial_risk=None)
    assert compute_trail_stop(without_risk, trail_width="medium") is None


def test_trail_stop_needs_a_watermark() -> None:
    """H-4 (§9 del pack): sin pico observado NO hay trailing.

    Antes se caía a ``actual_entry`` y el motor fingía un trailing anclado en la entrada
    (break-even "gratis"): con ``highWatermark`` ausente el stop propuesto era la entrada
    menos 1R, que no es un pico de nadie.
    """
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    assert high_watermark_from_position(pos) is None
    assert compute_trail_stop(pos, trail_width="medium") is None
    # El pico inyectado a mano tampoco se inventa desde la entrada.
    assert compute_trail_stop(pos, trail_width="medium", high_watermark=None) is None


def test_non_finite_watermark_and_stop_are_rejected() -> None:
    """H-5 (§9 del pack): ``inf`` no es un número utilizable (antes pasaba el filtro NaN)."""
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    assert compute_trail_stop(pos, trail_width="medium", high_watermark=float("inf")) is None
    assert compute_trail_stop(pos, trail_width="tight", high_watermark=float("nan")) is None
    assert apply_position_mark(pos, float("inf")) is None
    assert apply_position_mark(pos, float("nan")) is None
    assert apply_position_current_stop(pos, float("inf")) is None


def test_partial_exit_alone_does_not_arm_trailing() -> None:
    """H-3 (§9 del pack): una reducción SÓLO de T2 no arma el trailing.

    Antes ``is_trail_armed`` incluía ``PARTIAL_EXIT``, de modo que reducir por T2 (sin T1)
    habilitaba trailing sobre una posición que nunca alcanzó su primer objetivo.
    """
    pos = _open_long()
    reduced = apply_position_reduce(
        pos,
        3.0,
        exit_price=110.0,
        at="2026-08-25T16:00:00Z",
        mark_target2_achieved=True,
    )
    assert reduced is not None
    partial, _ = advance_lifecycle(reduced, "PARTIAL_FILL", at="2026-08-25T16:00:00Z")
    assert partial.lifecycle_state == "PARTIAL_EXIT"
    assert is_trail_armed(partial) is False
    assert compute_trail_stop(partial, trail_width="medium") is None


def test_rehydration_degrades_explicit_null_lifecycle() -> None:
    """H-6 (§9 del pack): ``lifecycleState: null`` PRESENTE no es "no persistido"."""
    blob = dict(_open_long().to_dict())
    blob[LIFECYCLE_STATE_KEY] = None
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.lifecycle_state == "RECONCILIATION_REQUIRED"
    assert protection_state_name(restored) == "RECONCILIATION_REQUIRED"


def test_rehydration_validates_legacy_status_against_quantity() -> None:
    """H-6: sin FSM persistido, un ``status`` que desmiente la cantidad degrada."""
    blob = dict(_open_long().to_dict())
    blob.pop(LIFECYCLE_STATE_KEY, None)
    blob["status"] = "CLOSED"
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.lifecycle_state == "RECONCILIATION_REQUIRED"
    assert derive_lifecycle_state(restored) == "RECONCILIATION_REQUIRED"

    live_without_qty = dict(_open_long().to_dict())
    live_without_qty.pop(LIFECYCLE_STATE_KEY, None)
    live_without_qty["remainingQuantity"] = 0.0
    restored_live = position_state_from_dict(live_without_qty)
    assert restored_live is not None
    assert restored_live.lifecycle_state == "RECONCILIATION_REQUIRED"


# --------------------------------------------------------------------------------------
# advance_lifecycle
# --------------------------------------------------------------------------------------


def test_advance_lifecycle_recomputes_status() -> None:
    pos, transition = advance_lifecycle(_open_long(), "PROTECT_APPLIED")
    assert transition.accepted is True
    assert pos.lifecycle_state == "PROTECTED"
    assert pos.status == "PROTECTED"


def test_advance_lifecycle_rejected_leaves_position_untouched() -> None:
    pos = _open_long()
    # ``FLAT`` no admite T1: la posición se devuelve intacta y el motivo se journaliza.
    flat = replace(pos, lifecycle_state="FLAT")
    unchanged, rejected = advance_lifecycle(flat, "T1_HIT")
    assert rejected.accepted is False
    assert unchanged is flat
    assert rejected.to_state == "FLAT"


def test_advance_lifecycle_marks_trailing_armed_then_active() -> None:
    pos, _ = advance_lifecycle(_open_long(), "T1_HIT")
    armed_pos, _ = advance_lifecycle(pos, "PROTECT_APPLIED", mark_trailing=True)
    assert trailing_status(armed_pos) == "armed"
    active_pos, _ = advance_lifecycle(armed_pos, "TRAIL_ARMED", mark_trailing=True)
    assert trailing_status(active_pos) == "active"
    assert trailing_is_active(active_pos) is True


def test_active_lifecycle_states_are_the_open_family() -> None:
    assert ACTIVE_LIFECYCLE_STATES <= VERIFIED_LIFECYCLE_STATES
    assert ACTIVE_LIFECYCLE_STATES.isdisjoint(DEGRADED_LIFECYCLE_STATES)


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _mark(position, price: float):
    marked = apply_position_mark(position, price, at="2026-08-25T16:00:00Z")
    assert marked is not None
    return marked


def _apply_stop(position, stop: float):
    updated = apply_position_current_stop(position, stop, at="2026-08-25T16:00:00Z")
    assert updated is not None
    return updated


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
