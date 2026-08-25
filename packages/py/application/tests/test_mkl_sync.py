"""P2.F — MKL sync stub."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_application.mkl_sync import (
    MATH_VERSION_MKL_SYNC_V0,
    SyncKnowledgeToMkl,
    build_mkl_fact_payload,
)
from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_tree import MklSyncEvent


def _node(**overrides) -> KnowledgeNode:
    base = dict(
        id="k1",
        hypothesis_id="h1",
        stage="EMERGING",
        statement="SMA edge persists OOS",
        knowledge_confidence=0.55,
        validity_context={"domain": "IBEX35"},
        evidence_ids=["e1"],
        belief_snapshot={"belief": 0.62, "nExperiments": 4},
        consolidation_report={},
        math_version="consolidation_lab_v0",
        consolidated_at="t0",
        created_at="t0",
        updated_at="t0",
    )
    base.update(overrides)
    return KnowledgeNode(**base)


def test_fact_payload_is_not_trade_signal():
    payload = build_mkl_fact_payload(_node())
    assert payload["evidenceKind"] == "ScientificKnowledgeFact"
    assert "not_auto_live" in payload["notes"]
    assert payload["mathVersion"] == MATH_VERSION_MKL_SYNC_V0
    assert payload["claim"] == "SMA edge persists OOS"


@pytest.mark.asyncio
async def test_sync_dry_run_does_not_promote():
    knowledge = MagicMock()
    knowledge.get_by_id = AsyncMock(return_value=_node())
    knowledge.update_stage = AsyncMock()
    mkl = MagicMock()
    mkl.append = AsyncMock(
        return_value=MklSyncEvent(
            id="ev1",
            knowledge_node_id="k1",
            status="dry_run",
            fact_payload={},
            math_version=MATH_VERSION_MKL_SYNC_V0,
            created_at="t0",
            notes=["dry_run"],
        )
    )
    result = await SyncKnowledgeToMkl(knowledge, mkl).execute("k1", dry_run=True)
    assert result["synced"] is False
    assert result["dryRun"] is True
    knowledge.update_stage.assert_not_called()
    assert mkl.append.await_args.kwargs["status"] == "dry_run"


@pytest.mark.asyncio
async def test_sync_promotes_emerging_to_accepted():
    knowledge = MagicMock()
    knowledge.get_by_id = AsyncMock(return_value=_node())
    promoted = _node(stage="ACCEPTED")
    knowledge.update_stage = AsyncMock(return_value=promoted)
    mkl = MagicMock()
    mkl.append = AsyncMock(
        return_value=MklSyncEvent(
            id="ev2",
            knowledge_node_id="k1",
            status="stub_recorded",
            fact_payload={},
            math_version=MATH_VERSION_MKL_SYNC_V0,
            created_at="t0",
            notes=[],
        )
    )
    result = await SyncKnowledgeToMkl(knowledge, mkl).execute("k1")
    assert result["synced"] is True
    assert result["node"].stage == "ACCEPTED"
    knowledge.update_stage.assert_awaited_once_with("k1", "ACCEPTED")


@pytest.mark.asyncio
async def test_sync_rejects_deprecated():
    knowledge = MagicMock()
    knowledge.get_by_id = AsyncMock(return_value=_node(stage="DEPRECATED"))
    mkl = MagicMock()
    with pytest.raises(ValueError, match="DEPRECATED"):
        await SyncKnowledgeToMkl(knowledge, mkl).execute("k1")
