"""Fase 2 assembly — Evidence → Belief → Consolidation → Tree → MKL (pure pipeline)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.hypothesis_belief import HypothesisBelief
from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_evidence import ResearchEvidence
from bolsa_domain.entities.research_tree import MklSyncEvent, ResearchTreeEdge
from bolsa_domain.entities.research_trial import ResearchTrial

from bolsa_application.belief_engine import (
    PRIOR_BELIEF,
    apply_evidence_to_belief_state,
    update_belief_from_evidence,
)
from bolsa_application.knowledge_consolidation import (
    ConsolidateHypothesis,
    evaluate_consolidation_eligibility,
)
from bolsa_application.mkl_sync import SyncKnowledgeToMkl, build_mkl_fact_payload
from bolsa_application.research_evidence import (
    build_evidence_draft_from_trial,
    classify_evidence_from_blocks,
)
from bolsa_application.research_tree import consolidation_tree_edge_specs


def test_piece_chain_levels_and_draft():
    level, source = classify_evidence_from_blocks(
        {"cpcv": {"meanOosScore": 1.0}}, has_is_metrics=True
    )
    assert (level, source) == ("B", "cpcv")
    trial = ResearchTrial(
        id="t1",
        instrument_id="i1",
        params={},
        is_metrics={"sharpeRatio": 1.2},
        proposed_by="grid",
        k_contribution=1,
        created_at="t0",
        hypothesis_id="h1",
        blocks={"cpcv": {"meanOosScore": 1.0, "walkForwardEfficiency": 0.7}},
    )
    draft = build_evidence_draft_from_trial(trial)
    assert draft is not None
    assert draft["level"] == "B"
    assert draft["hypothesis_id"] == "h1"


def test_belief_moves_then_consolidation_eligible():
    evidence = ResearchEvidence(
        id="ev-b",
        instrument_id="i1",
        level="B",
        source="cpcv",
        evidence_weight=0.7,
        summary={"isScore": 1.5, "walkForwardEfficiency": 0.7},
        created_at="t0",
        hypothesis_id="h1",
        trial_id="t1",
    )
    state, delta = apply_evidence_to_belief_state(None, evidence, hypothesis_id="h1")
    assert state["belief"] > PRIOR_BELIEF
    assert delta["sign"] == 1.0

    # Simulate enough supportive updates for gates.
    belief = HypothesisBelief(
        id="b1",
        hypothesis_id="h1",
        belief=0.62,
        belief_ci_low=0.45,
        belief_ci_high=0.75,
        n_experiments=4,
        evidence_weight=2.0,
        contexts_ok=["cpcv"],
        contexts_fail=[],
        evidence_ids=["ev-b", "ev-2", "ev-3", "ev-4"],
        trial_ids=["t1"],
        math_version="belief_lab_v0",
        last_reviewed_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    hyp = Hypothesis(
        id="h1",
        kind="hypothesis",
        statement="edge persists",
        falsifiers=[{"id": "f", "description": "PBO>=0.5", "kind": "metric_threshold"}],
        status="open",
        created_at="t0",
        updated_at="t0",
        domain="IBEX35",
    )
    report = evaluate_consolidation_eligibility(
        hypothesis=hyp,
        belief=belief,
        evidences=[evidence],
        active_nodes=[],
        acknowledge_landscape_gap=True,
    )
    assert report["eligible"] is True


@pytest.mark.asyncio
async def test_assembly_consolidate_tree_mkl():
    hyp = Hypothesis(
        id="h1",
        kind="hypothesis",
        statement="edge persists",
        falsifiers=[{"id": "f", "description": "x", "kind": "narrative"}],
        status="open",
        created_at="t0",
        updated_at="t0",
        domain="IBEX35",
    )
    belief = HypothesisBelief(
        id="b1",
        hypothesis_id="h1",
        belief=0.62,
        belief_ci_low=0.45,
        belief_ci_high=0.75,
        n_experiments=4,
        evidence_weight=2.0,
        contexts_ok=["cpcv"],
        contexts_fail=[],
        evidence_ids=["ev-b"],
        trial_ids=["t1"],
        math_version="belief_lab_v0",
        last_reviewed_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    evidence = ResearchEvidence(
        id="ev-b",
        instrument_id="i1",
        level="B",
        source="cpcv",
        evidence_weight=0.7,
        summary={"isScore": 1.2},
        created_at="t0",
        hypothesis_id="h1",
    )
    node = KnowledgeNode(
        id="k1",
        hypothesis_id="h1",
        stage="EMERGING",
        statement=hyp.statement,
        knowledge_confidence=0.55,
        validity_context={"domain": "IBEX35"},
        evidence_ids=["ev-b"],
        belief_snapshot={"belief": 0.62, "nExperiments": 4},
        consolidation_report={},
        math_version="consolidation_lab_v0",
        consolidated_at="t1",
        created_at="t1",
        updated_at="t1",
    )

    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(return_value=hyp)
    hyp_repo.update = AsyncMock(return_value=hyp)
    belief_repo = MagicMock()
    belief_repo.get_by_hypothesis_id = AsyncMock(return_value=belief)
    evidence_repo = MagicMock()
    evidence_repo.list_evidence = AsyncMock(return_value=([evidence], 1))
    knowledge_repo = MagicMock()
    knowledge_repo.list_active_for_hypothesis = AsyncMock(return_value=[])
    knowledge_repo.insert = AsyncMock(return_value=node)
    knowledge_repo.get_by_id = AsyncMock(return_value=node)
    knowledge_repo.update_stage = AsyncMock(
        return_value=KnowledgeNode(
            id=node.id,
            hypothesis_id=node.hypothesis_id,
            stage="ACCEPTED",
            statement=node.statement,
            knowledge_confidence=node.knowledge_confidence,
            validity_context=node.validity_context,
            evidence_ids=node.evidence_ids,
            belief_snapshot=node.belief_snapshot,
            consolidation_report=node.consolidation_report,
            math_version=node.math_version,
            consolidated_at=node.consolidated_at,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )
    )

    tree_repo = MagicMock()
    tree_repo.insert = AsyncMock(
        side_effect=lambda **kwargs: ResearchTreeEdge(
            id="edge",
            from_ref_type=kwargs["from_ref_type"],
            from_ref_id=kwargs["from_ref_id"],
            to_ref_type=kwargs["to_ref_type"],
            to_ref_id=kwargs["to_ref_id"],
            edge_type=kwargs["edge_type"],
            created_at="t1",
            notes=kwargs.get("notes"),
            payload=kwargs.get("payload"),
        )
    )

    cons = ConsolidateHypothesis(
        hyp_repo, belief_repo, evidence_repo, knowledge_repo, tree_repo
    )
    result = await cons.execute("h1", acknowledge_landscape_gap=True)
    assert result["created"] is True
    assert len(result["treeEdges"]) == 2  # 1 evidence SUPPORTS + 1 GENERALIZES
    specs = consolidation_tree_edge_specs(hypothesis_id="h1", knowledge_node=node)
    assert len(specs) == 2

    mkl = MagicMock()
    mkl.append = AsyncMock(
        return_value=MklSyncEvent(
            id="m1",
            knowledge_node_id="k1",
            status="stub_recorded",
            fact_payload=build_mkl_fact_payload(node),
            math_version="mkl_sync_lab_v0",
            created_at="t2",
            notes=[],
        )
    )
    sync = await SyncKnowledgeToMkl(knowledge_repo, mkl).execute("k1")
    assert sync["synced"] is True
    assert sync["node"].stage == "ACCEPTED"
    assert "not_auto_live" in sync["factPayload"]["notes"]


@pytest.mark.asyncio
async def test_belief_update_idempotent_in_chain():
    evidence = ResearchEvidence(
        id="ev-1",
        instrument_id="i1",
        level="C",
        source="holdout",
        evidence_weight=0.25,
        summary={"isScore": 1.0},
        created_at="t0",
        hypothesis_id="h1",
    )
    current = HypothesisBelief(
        id="b1",
        hypothesis_id="h1",
        belief=0.4,
        belief_ci_low=0.2,
        belief_ci_high=0.6,
        n_experiments=1,
        evidence_weight=0.25,
        contexts_ok=["holdout"],
        contexts_fail=[],
        evidence_ids=["ev-1"],
        trial_ids=["t1"],
        math_version="belief_lab_v0",
        last_reviewed_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    repo = MagicMock()
    repo.get_by_hypothesis_id = AsyncMock(return_value=current)
    repo.upsert_state = AsyncMock()
    out = await update_belief_from_evidence(repo, evidence)
    assert out is current
    repo.upsert_state.assert_not_called()
