"""PositionRevision OI-5 — historia auditada (ADR-034)."""

from dataclasses import replace

from bolsa_analytics.cognitive.position_revision import (
    build_position_revision,
    deterministic_revision_id,
    position_revision_from_dict,
    revision_origin_from_exit_reason,
    revisions_from_raw,
    stop_or_status_changed,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_position_mark,
    apply_position_reduce,
    build_position_state_from_fill,
    position_state_from_dict,
    seal_protection_transition,
)


def _open_long(*, stop: float = 95.0):
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": stop,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-26T00:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_build_revision_fields() -> None:
    rev = build_position_revision(
        at="2026-08-26T12:00:00Z",
        previous_stop=95.0,
        next_stop=98.0,
        previous_status="OPEN",
        next_status="OPEN",
        origin="protect",
        reason=None,
        revision_id="REV-1",
    )
    assert rev.to_dict() == {
        "revisionId": "REV-1",
        "at": "2026-08-26T12:00:00Z",
        "previousStop": 95.0,
        "nextStop": 98.0,
        "previousStatus": "OPEN",
        "nextStatus": "OPEN",
        "origin": "protect",
        "reason": None,
        "decisionId": None,
        "policyId": None,
    }


def test_stop_or_status_changed() -> None:
    assert stop_or_status_changed(
        previous_stop=95.0,
        next_stop=98.0,
        previous_status="OPEN",
        next_status="OPEN",
    )
    assert stop_or_status_changed(
        previous_stop=95.0,
        next_stop=95.0,
        previous_status="OPEN",
        next_status="PARTIAL",
    )
    assert not stop_or_status_changed(
        previous_stop=95.0,
        next_stop=95.0,
        previous_status="OPEN",
        next_status="OPEN",
    )


def test_from_fill_starts_with_empty_revisions() -> None:
    pos = _open_long()
    assert pos.revisions == ()
    assert pos.to_dict()["revisions"] == []


def test_apply_stop_appends_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(
        pos, 98.0, at="2026-08-26T01:00:00Z", origin="protect"
    )
    assert nxt is not None
    assert nxt.current_stop == 98.0
    assert len(nxt.revisions) == 1
    rev = nxt.revisions[0]
    assert rev.origin == "protect"
    assert rev.previous_stop == 95.0
    assert rev.next_stop == 98.0
    assert rev.previous_status == "OPEN"
    assert rev.next_status == "OPEN"
    assert rev.at == "2026-08-26T01:00:00Z"
    assert rev.decision_id == "dec-1"


def test_apply_stop_appends_trail_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(
        pos, 98.0, at="2026-08-26T01:00:00Z", origin="trail", reason="trail_confirm"
    )
    assert nxt is not None
    assert len(nxt.revisions) == 1
    assert nxt.revisions[0].origin == "trail"
    assert nxt.revisions[0].reason == "trail_confirm"


def test_same_stop_no_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(pos, 95.0, at="2026-08-26T01:00:00Z")
    assert nxt is not None
    assert nxt.revisions == ()


def test_be_stop_appends_status_change() -> None:
    pos = _open_long()
    be = apply_position_current_stop(pos, 100.0, at="t1", origin="stop")
    assert be is not None
    assert be.status == "PROTECTED"
    assert len(be.revisions) == 1
    assert be.revisions[0].previous_status == "OPEN"
    assert be.revisions[0].next_status == "PROTECTED"


def test_worsen_with_override_origin() -> None:
    pos = _open_long(stop=98.0)
    worse = apply_position_current_stop(
        pos, 94.0, at="t1", override={"reason": "gap_widen"}
    )
    assert worse is not None
    assert worse.revisions[0].origin == "override"
    assert worse.revisions[0].reason == "gap_widen"


def test_reduce_appends_status_revision() -> None:
    pos = _open_long()
    partial = apply_position_reduce(pos, 5.0, exit_price=105.0, at="t1")
    assert partial is not None
    assert partial.status == "PARTIAL"
    assert len(partial.revisions) == 1
    assert partial.revisions[0].origin == "reduce"
    assert partial.revisions[0].previous_status == "OPEN"
    assert partial.revisions[0].next_status == "PARTIAL"


def test_mark_does_not_append() -> None:
    pos = _open_long()
    marked = apply_position_mark(pos, 105.0, at="t1")
    assert marked is not None
    assert marked.revisions == ()


def test_round_trip_revisions_in_snapshot() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(pos, 98.0, at="t1", origin="protect")
    assert nxt is not None
    blob = nxt.to_dict()
    back = position_state_from_dict(blob)
    assert back is not None
    assert len(back.revisions) == 1
    assert back.revisions[0].origin == "protect"
    assert back.revisions[0].next_stop == 98.0


def test_revisions_from_raw_skips_invalid() -> None:
    assert revisions_from_raw(None) == ()
    assert revisions_from_raw([{"revisionId": "x"}]) == ()
    ok = position_revision_from_dict(
        {
            "revisionId": "REV-1",
            "at": "t",
            "previousStop": 1.0,
            "nextStop": 2.0,
            "previousStatus": "OPEN",
            "nextStatus": "OPEN",
            "origin": "protect",
            "reason": None,
        }
    )
    assert ok is not None
    assert ok.revision_id == "REV-1"
    assert ok.decision_id is None
    assert ok.policy_id is None


def test_revision_origin_from_exit_reason() -> None:
    assert revision_origin_from_exit_reason("TRAIL") == "trail"
    assert revision_origin_from_exit_reason("TARGET_1") == "protect"
    assert revision_origin_from_exit_reason("TRAILING") == "protect"
    assert revision_origin_from_exit_reason(None) == "protect"


# ── v2.88.28 — identidad determinista y sellado de transiciones de protección ──────


def test_deterministic_revision_id_is_stable_and_content_addressed() -> None:
    base = {
        "position_id": "pos-1",
        "origin": "protect",
        "previous_stop": 95.0,
        "next_stop": 98.0,
        "previous_status": "OPEN",
        "next_status": "OPEN",
        "ordinal": 0,
    }
    first = deterministic_revision_id(**base)
    second = deterministic_revision_id(**base)
    assert first == second
    assert first.startswith("REV-")
    # El MISMO cambio en otro ordinal (otra transición real) NO colisiona.
    assert deterministic_revision_id(**{**base, "ordinal": 1}) != first
    # Un ``discriminator`` distinto separa dos hechos sin cambio de estado.
    assert (
        deterministic_revision_id(**base, discriminator="PROTECT_APPLIED")
        != deterministic_revision_id(**base, discriminator="PROTECT_REQUESTED")
    )


def test_apply_stop_revision_id_is_deterministic() -> None:
    pos = _open_long()
    first = apply_position_current_stop(pos, 98.0, at="t1", origin="protect")
    second = apply_position_current_stop(pos, 98.0, at="t2", origin="protect")
    assert first is not None and second is not None
    # El mismo cambio recomputado (mismo estado de partida, otro instante) ⇒ misma clave.
    assert first.revisions[0].revision_id == second.revisions[0].revision_id


def test_apply_reduce_revision_id_is_deterministic() -> None:
    pos = _open_long()
    first = apply_position_reduce(pos, 5.0, exit_price=105.0, at="t1")
    second = apply_position_reduce(pos, 5.0, exit_price=105.0, at="t2")
    assert first is not None and second is not None
    assert first.revisions[0].revision_id == second.revisions[0].revision_id


def test_seal_protection_transition_reuses_the_step_revision() -> None:
    pos = _open_long()
    advanced = apply_position_current_stop(pos, 98.0, at="t1", origin="protect")
    assert advanced is not None
    sealed, revision_id = seal_protection_transition(
        pos, advanced, kind="PROTECT_APPLIED", origin="protect", at="t1"
    )
    # El paso ya añadió la revisión: se reutiliza, no se duplica.
    assert sealed.revisions == advanced.revisions
    assert revision_id == advanced.revisions[-1].revision_id


def test_seal_protection_transition_adds_lifecycle_revision() -> None:
    pos = _open_long()
    advanced = replace(pos, lifecycle_state="PROTECTED")
    sealed, revision_id = seal_protection_transition(
        pos, advanced, kind="PROTECT_APPLIED", origin="protect", at="t1", reason="plan"
    )
    assert len(sealed.revisions) == 1
    assert sealed.revisions[0].revision_id == revision_id
    assert sealed.revisions[0].origin == "protect"
    # La identidad se deriva del estado durable, no del intento de escritura.
    again, again_id = seal_protection_transition(
        pos, advanced, kind="PROTECT_APPLIED", origin="protect", at="t9", reason="plan"
    )
    assert again_id == revision_id


def test_seal_protection_transition_without_change_shares_content_id() -> None:
    pos = _open_long()
    sealed, revision_id = seal_protection_transition(
        pos, pos, kind="PROTECT_REQUESTED", origin="protect", at="t1"
    )
    # Sin cambio durable no se inventa revisión: sólo la identidad por contenido.
    assert sealed.revisions == ()
    same, same_id = seal_protection_transition(
        pos, pos, kind="PROTECT_REQUESTED", origin="protect", at="t2"
    )
    assert same_id == revision_id
    _, other_id = seal_protection_transition(
        pos, pos, kind="PROTECT_APPLIED", origin="protect", at="t1"
    )
    assert other_id != revision_id
