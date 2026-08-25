"""P2.D — Knowledge Consolidation stub."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.hypothesis_belief import HypothesisBelief
from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_evidence import ResearchEvidence

from bolsa_application.knowledge_consolidation import (
    MATH_VERSION_CONSOLIDATION_V0,
    ConsolidateHypothesis,
    evaluate_consolidation_eligibility,
    initial_knowledge_confidence,
)


def _hyp(**overrides) -> Hypothesis:
    base = dict(
        id="hyp-1",
        kind="hypothesis",
        statement="SMA edge persists OOS",
        falsifiers=[{"id": "f", "description": "PBO>=0.5", "kind": "metric_threshold"}],
        status="open",
        created_at="t0",
        updated_at="t0",
        domain="IBEX35",
    )
    base.update(overrides)
    return Hypothesis(**base)


def _belief(**overrides) -> HypothesisBelief:
    base = dict(
        id="b1",
        hypothesis_id="hyp-1",
        belief=0.62,
        belief_ci_low=0.45,
        belief_ci_high=0.75,
        n_experiments=4,
        evidence_weight=1.5,
        contexts_ok=["cpcv"],
        contexts_fail=[],
        evidence_ids=["ev-b", "ev-c"],
        trial_ids=["t1"],
        math_version="belief_lab_v0",
        last_reviewed_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    base.update(overrides)
    return HypothesisBelief(**base)


def _ev(level: str = "B", eid: str = "ev-b") -> ResearchEvidence:
    return ResearchEvidence(
        id=eid,
        instrument_id="inst-1",
        level=level,  # type: ignore[arg-type]
        source="cpcv",
        evidence_weight=0.7,
        summary={},
        created_at="t0",
        hypothesis_id="hyp-1",
    )


def test_eligibility_fails_without_belief():
    report = evaluate_consolidation_eligibility(
        hypothesis=_hyp(),
        belief=None,
        evidences=[],
        active_nodes=[],
        acknowledge_landscape_gap=True,
    )
    assert report["eligible"] is False
    assert "belief_exists" in report["failReasons"]


def test_eligibility_fails_on_level_c_only():
    report = evaluate_consolidation_eligibility(
        hypothesis=_hyp(),
        belief=_belief(),
        evidences=[_ev(level="C", eid="ev-c")],
        active_nodes=[],
        acknowledge_landscape_gap=True,
    )
    assert report["eligible"] is False
    assert "evidence_level_b" in report["failReasons"]


def test_eligibility_requires_landscape_ack():
    report = evaluate_consolidation_eligibility(
        hypothesis=_hyp(),
        belief=_belief(),
        evidences=[_ev()],
        active_nodes=[],
        acknowledge_landscape_gap=False,
    )
    assert report["eligible"] is False
    assert "landscape_not_peak" in report["failReasons"]


def test_eligibility_passes_with_gates():
    report = evaluate_consolidation_eligibility(
        hypothesis=_hyp(),
        belief=_belief(),
        evidences=[_ev()],
        active_nodes=[],
        acknowledge_landscape_gap=True,
    )
    assert report["eligible"] is True
    assert report["proposedStage"] == "EMERGING"
    assert report["mathVersion"] == MATH_VERSION_CONSOLIDATION_V0
    assert "landscape_gap_acknowledged" in report["warnings"]


def test_eligibility_blocks_if_active_node_exists():
    node = KnowledgeNode(
        id="k1",
        hypothesis_id="hyp-1",
        stage="EMERGING",
        statement="s",
        knowledge_confidence=0.5,
        validity_context={},
        evidence_ids=[],
        belief_snapshot={},
        consolidation_report={},
        math_version=MATH_VERSION_CONSOLIDATION_V0,
        consolidated_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    report = evaluate_consolidation_eligibility(
        hypothesis=_hyp(),
        belief=_belief(),
        evidences=[_ev()],
        active_nodes=[node],
        acknowledge_landscape_gap=True,
    )
    assert "no_active_knowledge" in report["failReasons"]


def test_initial_knowledge_confidence_bounded():
    conf = initial_knowledge_confidence(_belief())
    assert 0.40 <= conf <= 0.85


@pytest.mark.asyncio
async def test_consolidate_dry_run_does_not_insert():
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(return_value=_hyp())
    hyp_repo.update = AsyncMock()
    belief_repo = MagicMock()
    belief_repo.get_by_hypothesis_id = AsyncMock(return_value=_belief())
    evidence_repo = MagicMock()
    evidence_repo.list_evidence = AsyncMock(return_value=([_ev()], 1))
    knowledge_repo = MagicMock()
    knowledge_repo.list_active_for_hypothesis = AsyncMock(return_value=[])
    knowledge_repo.insert = AsyncMock()

    use_case = ConsolidateHypothesis(
        hyp_repo, belief_repo, evidence_repo, knowledge_repo
    )
    result = await use_case.execute(
        "hyp-1", acknowledge_landscape_gap=True, dry_run=True
    )
    assert result["created"] is False
    knowledge_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_consolidate_creates_emerging_node():
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(return_value=_hyp())
    hyp_repo.update = AsyncMock(return_value=_hyp(status="consolidated"))
    belief_repo = MagicMock()
    belief_repo.get_by_hypothesis_id = AsyncMock(return_value=_belief())
    evidence_repo = MagicMock()
    evidence_repo.list_evidence = AsyncMock(return_value=([_ev()], 1))
    created = KnowledgeNode(
        id="k-new",
        hypothesis_id="hyp-1",
        stage="EMERGING",
        statement="SMA edge persists OOS",
        knowledge_confidence=0.55,
        validity_context={"domain": "IBEX35"},
        evidence_ids=["ev-b", "ev-c"],
        belief_snapshot={"belief": 0.62},
        consolidation_report={},
        math_version=MATH_VERSION_CONSOLIDATION_V0,
        consolidated_at="t1",
        created_at="t1",
        updated_at="t1",
    )
    knowledge_repo = MagicMock()
    knowledge_repo.list_active_for_hypothesis = AsyncMock(return_value=[])
    knowledge_repo.insert = AsyncMock(return_value=created)

    use_case = ConsolidateHypothesis(
        hyp_repo, belief_repo, evidence_repo, knowledge_repo
    )
    result = await use_case.execute(
        "hyp-1", acknowledge_landscape_gap=True, notes="lab review"
    )
    assert result["created"] is True
    assert result["node"].stage == "EMERGING"
    knowledge_repo.insert.assert_awaited_once()
    assert knowledge_repo.insert.await_args.kwargs["stage"] == "EMERGING"
    hyp_repo.update.assert_awaited_once_with("hyp-1", status="consolidated")


@pytest.mark.asyncio
async def test_consolidate_not_eligible_does_not_create():
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(return_value=_hyp())
    belief_repo = MagicMock()
    belief_repo.get_by_hypothesis_id = AsyncMock(
        return_value=_belief(n_experiments=1, belief=0.4)
    )
    evidence_repo = MagicMock()
    evidence_repo.list_evidence = AsyncMock(return_value=([_ev(level="C")], 1))
    knowledge_repo = MagicMock()
    knowledge_repo.list_active_for_hypothesis = AsyncMock(return_value=[])
    knowledge_repo.insert = AsyncMock()

    use_case = ConsolidateHypothesis(
        hyp_repo, belief_repo, evidence_repo, knowledge_repo
    )
    result = await use_case.execute("hyp-1", acknowledge_landscape_gap=True)
    assert result["created"] is False
    knowledge_repo.insert.assert_not_called()
