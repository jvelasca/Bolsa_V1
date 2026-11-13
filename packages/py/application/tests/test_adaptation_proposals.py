"""Propuestas de adaptación (ADR-049): enum cerrado, fallback honesto y determinismo."""

from __future__ import annotations

import pytest

from bolsa_application.adaptation_proposals import (
    ADAPTATION_MUTATIONS,
    AdaptationProposalV1,
    build_candidate_request,
    materialize_candidates,
    preregistration_hash,
    propose_adaptations,
)


def _measured_evidence() -> dict:
    return {
        "version": "AdaptationEvidenceV1",
        "regime": "TREND",
        "family": "breakout",
        "instrument": "AAA",
        "cycles": 20,
        "closedCycles": 20,
        "expectancyR": -0.204,
        "hitRate": 0.417,
        "avgMaeR": -0.95,
        "avgMfeR": 0.8,
        "capture": 0.31,
        "failedGates": ["maxDrawdownPct", "minPositiveWindowPct"],
        "lossDrivers": [{"driver": "family:breakout", "cycles": 8, "realizedR": -3.2}],
        "artifactRefs": ["docs/engineering/dia-d-evidencia-politica-2026-11-05.md"],
        "measured": True,
        "gaps": [],
        "hash": "abc123",
    }


def _valid_proposal(**overrides) -> dict:
    proposal = {
        "mutation": "tighten_stop_atr",
        "rationale": "Expectativa negativa medida en la cohorte.",
        "expectedEffect": "Menos R perdido por ciclo.",
        "evidenceRefs": ["evidence:abc123:expectancyR"],
        "boundsRespected": True,
        "riskNote": "Puede recortar recorrido favorable.",
    }
    proposal.update(overrides)
    return proposal


def test_unmeasured_evidence_returns_empty_with_reason() -> None:
    batch = propose_adaptations({"version": "AdaptationEvidenceV1", "measured": False})

    assert batch.source == "no_evidence"
    assert batch.proposals == ()
    assert "evidence_not_measured" in batch.reason_codes


def test_without_proxy_uses_declared_heuristic_fallback() -> None:
    batch = propose_adaptations(_measured_evidence())

    assert batch.source == "heuristic_fallback"
    assert "proxy_not_configured" in batch.reason_codes
    assert "heuristic_fallback" in batch.reason_codes
    assert batch.proposals
    assert all(proposal.mutation in ADAPTATION_MUTATIONS for proposal in batch.proposals)
    assert all(proposal.evidence_refs for proposal in batch.proposals)


def test_heuristic_is_deterministic_and_capped() -> None:
    first = propose_adaptations(_measured_evidence(), max_proposals=2)
    second = propose_adaptations(_measured_evidence(), max_proposals=2)

    assert [p.id for p in first.proposals] == [p.id for p in second.proposals]
    assert len(first.proposals) == 2
    assert first.to_dict()["hash"] == second.to_dict()["hash"]


def test_valid_proxy_payload_is_accepted_as_llm() -> None:
    batch = propose_adaptations(
        _measured_evidence(),
        proxy=lambda evidence, thresholds, constraints: {"proposals": [_valid_proposal()]},
        provider="ollama",
        model="qwen2.5-coder:14b",
    )

    assert batch.source == "llm"
    assert len(batch.proposals) == 1
    proposal = batch.proposals[0]
    assert proposal.mutation == "tighten_stop_atr"
    assert proposal.provider == "ollama"
    assert proposal.prompt_id == "prompt_adaptation_proposal_v1"
    assert proposal.id.startswith("adp_")


def test_mutation_outside_enum_invalidates_whole_payload() -> None:
    payload = {
        "proposals": [
            _valid_proposal(),
            _valid_proposal(mutation="edit_engine_source"),
        ]
    }
    batch = propose_adaptations(
        _measured_evidence(),
        proxy=lambda evidence, thresholds, constraints: payload,
    )

    assert batch.source == "heuristic_fallback"
    assert any(reason.startswith("schema_invalid:") for reason in batch.reason_codes)
    assert all(proposal.mutation in ADAPTATION_MUTATIONS for proposal in batch.proposals)


def test_extra_key_invalidates_payload() -> None:
    payload = {"proposals": [_valid_proposal(weight=0.9)]}
    batch = propose_adaptations(
        _measured_evidence(),
        proxy=lambda evidence, thresholds, constraints: payload,
    )

    assert batch.source == "heuristic_fallback"
    assert any("claves no permitidas" in reason for reason in batch.reason_codes)


def test_ai_cannot_smuggle_thresholds_into_the_contract() -> None:
    """La IA no mueve los umbrales: una clave extra en la raíz invalida el payload entero."""
    payload = {
        "thresholds": {"maxDrawdownPct": 50.0},
        "proposals": [_valid_proposal()],
    }
    batch = propose_adaptations(
        _measured_evidence(),
        proxy=lambda evidence, thresholds, constraints: payload,
    )

    assert batch.source == "heuristic_fallback"
    assert any("thresholds" in reason for reason in batch.reason_codes)
    assert all(proposal.mutation in ADAPTATION_MUTATIONS for proposal in batch.proposals)


def test_proxy_error_falls_back_and_declares_type() -> None:
    def broken(evidence, thresholds, constraints):
        raise TimeoutError("ollama timeout")

    batch = propose_adaptations(_measured_evidence(), proxy=broken)

    assert batch.source == "heuristic_fallback"
    assert "proxy_error:TimeoutError" in batch.reason_codes


def test_custom_validator_is_honoured() -> None:
    seen: list[object] = []

    def validator(payload):
        seen.append(payload)
        return []

    batch = propose_adaptations(
        _measured_evidence(),
        proxy=lambda evidence, thresholds, constraints: {"proposals": [_valid_proposal()]},
        validator=validator,
    )

    assert seen
    assert batch.source == "llm"


def test_preregistration_hash_is_stable_and_threshold_sensitive() -> None:
    assert preregistration_hash() == preregistration_hash({})
    assert preregistration_hash({"minNetReturnPct": 0.0}) != preregistration_hash(
        {"minNetReturnPct": 1.0}
    )


def test_build_candidate_request_rejects_unknown_mutation() -> None:
    proposal = AdaptationProposalV1(
        id="adp_1",
        mutation="edit_engine_source",
        rationale="x",
        expected_effect="y",
        evidence_refs=("ref",),
        bounds_respected=True,
        risk_note="z",
    )
    with pytest.raises(ValueError):
        build_candidate_request(proposal, instrument_id="AAA")


def test_materialize_candidates_declares_errors_instead_of_swallowing() -> None:
    request = build_candidate_request(
        AdaptationProposalV1(
            id="adp_1",
            mutation="tighten_stop_atr",
            rationale="x",
            expected_effect="y",
            evidence_refs=("ref",),
            bounds_respected=True,
            risk_note="z",
        ),
        instrument_id="AAA",
    )

    def boom(**kwargs):
        raise RuntimeError("registry missing")

    failed = materialize_candidates([request], discover=boom)
    assert failed[0].candidate_ids == ()
    assert failed[0].error == "discovery_error:RuntimeError"

    def empty(**kwargs):
        return []

    no_ids = materialize_candidates([request], discover=empty)
    assert no_ids[0].error == "no_candidates"

    def found(**kwargs):
        return [{"id": "cand-1"}, {"id": "cand-2"}]

    ok = materialize_candidates([request], discover=found)
    assert ok[0].candidate_ids == ("cand-1", "cand-2")
    assert ok[0].error is None
