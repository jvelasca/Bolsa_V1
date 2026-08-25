"""P2.E — Research Tree mínimo."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.knowledge_node import KnowledgeNode

from bolsa_application.research_tree import (
    CreateResearchTreeEdge,
    consolidation_tree_edge_specs,
    validate_edge_spec,
)


def test_validate_blocks_causes():
    with pytest.raises(ValueError, match="CAUSES"):
        validate_edge_spec(
            from_ref_type="hypothesis",
            from_ref_id="h1",
            to_ref_type="hypothesis",
            to_ref_id="h2",
            edge_type="CAUSES",
        )


def test_validate_allows_hypothesized_causes():
    validate_edge_spec(
        from_ref_type="hypothesis",
        from_ref_id="h1",
        to_ref_type="hypothesis",
        to_ref_id="h2",
        edge_type="HYPOTHESIZED_CAUSES",
    )


def test_validate_rejects_self_loop():
    with pytest.raises(ValueError, match="reflexiva"):
        validate_edge_spec(
            from_ref_type="evidence",
            from_ref_id="e1",
            to_ref_type="evidence",
            to_ref_id="e1",
            edge_type="SUPPORTS",
        )


def test_consolidation_specs_include_supports_and_generalizes():
    node = KnowledgeNode(
        id="k1",
        hypothesis_id="h1",
        stage="EMERGING",
        statement="s",
        knowledge_confidence=0.5,
        validity_context={},
        evidence_ids=["e1", "e2"],
        belief_snapshot={},
        consolidation_report={},
        math_version="consolidation_lab_v0",
        consolidated_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    specs = consolidation_tree_edge_specs(hypothesis_id="h1", knowledge_node=node)
    assert len(specs) == 3
    assert specs[0]["edge_type"] == "SUPPORTS"
    assert specs[0]["from_ref_type"] == "evidence"
    assert specs[-1]["edge_type"] == "GENERALIZES"
    assert specs[-1]["to_ref_id"] == "k1"


@pytest.mark.asyncio
async def test_create_edge_persists():
    from bolsa_domain.entities.research_tree import ResearchTreeEdge

    repo = MagicMock()
    repo.insert = AsyncMock(
        return_value=ResearchTreeEdge(
            id="edge-1",
            from_ref_type="evidence",
            from_ref_id="e1",
            to_ref_type="hypothesis",
            to_ref_id="h1",
            edge_type="SUPPORTS",
            created_at="t0",
        )
    )
    use_case = CreateResearchTreeEdge(repo)
    out = await use_case.execute(
        from_ref_type="evidence",
        from_ref_id="e1",
        to_ref_type="hypothesis",
        to_ref_id="h1",
        edge_type="SUPPORTS",
    )
    assert out.id == "edge-1"
