"""P2.C — Belief Engine v0."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.hypothesis_belief import HypothesisBelief
from bolsa_domain.entities.research_evidence import ResearchEvidence

from bolsa_application.belief_engine import (
    MATH_VERSION_BELIEF_V0,
    PRIOR_BELIEF,
    apply_evidence_to_belief_state,
    ensure_prior_belief,
    evidence_support_sign,
    update_belief_from_evidence,
)


def _evidence(**overrides) -> ResearchEvidence:
    base = dict(
        id="ev-1",
        instrument_id="inst-1",
        level="C",
        source="holdout",
        evidence_weight=0.25,
        summary={"isScore": 1.2, "edgeBand": "uncertain"},
        created_at="2026-07-27T00:00:00+00:00",
        hypothesis_id="hyp-1",
        trial_id="trial-1",
    )
    base.update(overrides)
    return ResearchEvidence(**base)


def _belief(**overrides) -> HypothesisBelief:
    base = dict(
        id="b1",
        hypothesis_id="hyp-1",
        belief=PRIOR_BELIEF,
        belief_ci_low=0.15,
        belief_ci_high=0.55,
        n_experiments=0,
        evidence_weight=0.0,
        contexts_ok=[],
        contexts_fail=[],
        evidence_ids=[],
        trial_ids=[],
        math_version=MATH_VERSION_BELIEF_V0,
        last_reviewed_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    base.update(overrides)
    return HypothesisBelief(**base)


def test_support_sign_positive_for_good_oos():
    assert evidence_support_sign(_evidence(summary={"isScore": 2.0})) == 1.0


def test_support_sign_negative_for_high_pbo():
    assert (
        evidence_support_sign(
            _evidence(summary={"isScore": 0.1, "pbo": 0.7, "edgeBand": "luck"})
        )
        == -1.0
    )


def test_apply_evidence_raises_belief_on_support():
    state, delta = apply_evidence_to_belief_state(
        _belief(),
        _evidence(level="B", evidence_weight=0.7, summary={"isScore": 1.5}),
        hypothesis_id="hyp-1",
    )
    assert state["belief"] > PRIOR_BELIEF
    assert state["n_experiments"] == 1
    assert state["evidence_ids"] == ["ev-1"]
    assert delta["sign"] == 1.0
    assert state["math_version"] == MATH_VERSION_BELIEF_V0


def test_apply_evidence_idempotent():
    current = _belief(evidence_ids=["ev-1"], n_experiments=1, belief=0.4)
    state, delta = apply_evidence_to_belief_state(
        current, _evidence(), hypothesis_id="hyp-1"
    )
    assert delta.get("skipped") is True
    assert state["belief"] == 0.4
    assert state["n_experiments"] == 1


def test_level_d_does_not_increment_n():
    state, _ = apply_evidence_to_belief_state(
        _belief(),
        _evidence(level="D", evidence_weight=0.0, source="narrative", summary={}),
        hypothesis_id="hyp-1",
    )
    assert state["n_experiments"] == 0
    assert state["belief"] == PRIOR_BELIEF


@pytest.mark.asyncio
async def test_ensure_prior_seeds_once():
    repo = MagicMock()
    repo.get_by_hypothesis_id = AsyncMock(return_value=None)
    saved = _belief()
    repo.upsert_state = AsyncMock(return_value=saved)
    repo.append_history = AsyncMock()
    out = await ensure_prior_belief(repo, "hyp-1")
    assert out is saved
    repo.upsert_state.assert_awaited_once()
    repo.append_history.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_belief_from_evidence_persists():
    current = _belief()
    repo = MagicMock()
    repo.get_by_hypothesis_id = AsyncMock(return_value=current)
    updated = _belief(belief=0.4, n_experiments=1, evidence_ids=["ev-1"])
    repo.upsert_state = AsyncMock(return_value=updated)
    repo.append_history = AsyncMock()
    out = await update_belief_from_evidence(repo, _evidence())
    assert out is updated
    repo.upsert_state.assert_awaited_once()
    assert repo.append_history.await_args.kwargs["trigger_evidence_id"] == "ev-1"


@pytest.mark.asyncio
async def test_update_noop_without_hypothesis():
    repo = MagicMock()
    out = await update_belief_from_evidence(repo, _evidence(hypothesis_id=None))
    assert out is None
    repo.get_by_hypothesis_id.assert_not_called()


@pytest.mark.asyncio
async def test_emit_evidence_updates_belief():
    from bolsa_domain.entities.research_trial import ResearchTrial

    from bolsa_application.research_evidence import emit_evidence_for_trial

    trial = ResearchTrial(
        id="trial-1",
        instrument_id="inst-1",
        params={},
        is_metrics={"sharpeRatio": 1.0},
        proposed_by="human",
        k_contribution=1,
        created_at="t0",
        hypothesis_id="hyp-1",
        blocks={"oosMetrics": {"score": 2.0}},
    )
    evidence_repo = MagicMock()
    evidence_repo.insert_evidence = AsyncMock(
        return_value=_evidence(level="C", source="holdout")
    )
    belief_repo = MagicMock()
    belief_repo.get_by_hypothesis_id = AsyncMock(return_value=_belief())
    belief_repo.upsert_state = AsyncMock(return_value=_belief(belief=0.37, n_experiments=1))
    belief_repo.append_history = AsyncMock()

    out = await emit_evidence_for_trial(
        evidence_repo, trial, belief_repo=belief_repo
    )
    assert out is not None
    belief_repo.upsert_state.assert_awaited_once()
