"""Validación del payload de adaptación (ADR-049): enum cerrado y claves estrictas."""

from __future__ import annotations

from bolsa_ai.schemas import ADAPTATION_MUTATIONS, validate_adaptation_proposal_payload


def _proposal(**overrides):
    proposal = {
        "mutation": "tighten_stop_atr",
        "rationale": "Expectativa negativa medida.",
        "expectedEffect": "Menos R perdido por ciclo.",
        "evidenceRefs": ["evidence:abc:expectancyR"],
        "boundsRespected": True,
        "riskNote": "Puede recortar recorrido favorable.",
    }
    proposal.update(overrides)
    return proposal


def test_valid_payload_has_no_errors() -> None:
    payload = {"proposals": [_proposal()]}

    assert validate_adaptation_proposal_payload(payload) == []


def test_every_enum_value_is_accepted() -> None:
    payload = {"proposals": [_proposal(mutation=mutation) for mutation in ADAPTATION_MUTATIONS]}

    assert validate_adaptation_proposal_payload(payload) == []


def test_unknown_mutation_is_rejected() -> None:
    errors = validate_adaptation_proposal_payload({"proposals": [_proposal(mutation="edit_code")]})

    assert any("mutation inválida" in error for error in errors)


def test_extra_key_is_rejected() -> None:
    errors = validate_adaptation_proposal_payload({"proposals": [_proposal(weight=0.5)]})

    assert any("claves no permitidas" in error for error in errors)


def test_extra_root_key_is_rejected() -> None:
    errors = validate_adaptation_proposal_payload(
        {"proposals": [_proposal()], "activate": True}
    )

    assert any("claves no permitidas en la raíz" in error for error in errors)


def test_bounds_respected_must_be_strict_boolean() -> None:
    errors = validate_adaptation_proposal_payload(
        {"proposals": [_proposal(boundsRespected="true")]}
    )

    assert any("boundsRespected" in error for error in errors)


def test_empty_or_missing_proposals_are_rejected() -> None:
    assert validate_adaptation_proposal_payload({"proposals": []})
    assert validate_adaptation_proposal_payload({})
    assert validate_adaptation_proposal_payload("not-json")


def test_empty_evidence_refs_are_rejected() -> None:
    errors = validate_adaptation_proposal_payload({"proposals": [_proposal(evidenceRefs=[])]})

    assert any("evidenceRefs" in error for error in errors)


def test_blank_text_fields_are_rejected() -> None:
    errors = validate_adaptation_proposal_payload({"proposals": [_proposal(rationale="   ")]})

    assert any("rationale" in error for error in errors)
