"""P2.F — Sync MKL stub (RFC-008 D5). Records Fact-shaped payload; no trading gate."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_tree import MklSyncEvent

MATH_VERSION_MKL_SYNC_V0 = "mkl_sync_lab_v0"
SYNCABLE_STAGES = frozenset({"EMERGING", "ACCEPTED", "CANONICAL"})


class _KnowledgeRepo(Protocol):
    async def get_by_id(self, node_id: str) -> KnowledgeNode | None: ...

    async def update_stage(
        self, node_id: str, stage: str
    ) -> KnowledgeNode | None: ...


class _MklRepo(Protocol):
    async def append(
        self,
        *,
        knowledge_node_id: str,
        status: str,
        fact_payload: dict[str, Any],
        math_version: str,
        notes: list[str] | None = None,
        event_id: str | None = None,
    ) -> MklSyncEvent: ...

    async def list_for_knowledge(
        self,
        knowledge_node_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MklSyncEvent], int]: ...


def build_mkl_fact_payload(node: KnowledgeNode) -> dict[str, Any]:
    """Fact-shaped stub for Market Knowledge Layer (RFC-008 §7). Not a trade signal."""
    belief = node.belief_snapshot if isinstance(node.belief_snapshot, dict) else {}
    return {
        "evidenceKind": "ScientificKnowledgeFact",
        "claim": node.statement,
        "direction": "supports",
        "knowledgeNodeId": node.id,
        "hypothesisId": node.hypothesis_id,
        "stage": node.stage,
        "knowledgeConfidence": node.knowledge_confidence,
        "validityContext": node.validity_context,
        "belief": belief.get("belief"),
        "nExperiments": belief.get("nExperiments"),
        "evidenceIds": list(node.evidence_ids),
        "mathVersion": MATH_VERSION_MKL_SYNC_V0,
        "notes": [
            "stub_only",
            "not_auto_live",
            "does_not_authorize_orders",
        ],
    }


class SyncKnowledgeToMkl:
    """Sincroniza Knowledge To Mkl."""
    def __init__(
        self,
        knowledge: _KnowledgeRepo,
        mkl: _MklRepo,
    ) -> None:
        self._knowledge = knowledge
        self._mkl = mkl

    async def execute(
        self,
        knowledge_node_id: str,
        *,
        dry_run: bool = False,
        promote_to_accepted: bool = True,
    ) -> dict[str, Any]:
        node = await self._knowledge.get_by_id(knowledge_node_id)
        if node is None:
            raise LookupError("Knowledge node not found")
        if node.stage == "DEPRECATED":
            raise ValueError("Cannot sync DEPRECATED knowledge")
        if node.stage not in SYNCABLE_STAGES:
            raise ValueError(
                f"stage {node.stage} not syncable — need EMERGING/ACCEPTED/CANONICAL"
            )

        payload = build_mkl_fact_payload(node)
        if dry_run:
            event = await self._mkl.append(
                knowledge_node_id=node.id,
                status="dry_run",
                fact_payload=payload,
                math_version=MATH_VERSION_MKL_SYNC_V0,
                notes=["dry_run", "not_persisted_to_live_mkl"],
            )
            return {
                "synced": False,
                "dryRun": True,
                "event": event,
                "node": node,
                "factPayload": payload,
            }

        event = await self._mkl.append(
            knowledge_node_id=node.id,
            status="stub_recorded",
            fact_payload=payload,
            math_version=MATH_VERSION_MKL_SYNC_V0,
            notes=["stub_recorded", "not_auto_live", "rfc008_mkl_destination"],
        )
        updated = node
        if promote_to_accepted and node.stage == "EMERGING":
            promoted = await self._knowledge.update_stage(node.id, "ACCEPTED")
            if promoted is not None:
                updated = promoted
        return {
            "synced": True,
            "dryRun": False,
            "event": event,
            "node": updated,
            "factPayload": payload,
        }


class ListMklSyncEvents:
    """Lista Mkl Sync Events."""
    def __init__(self, repository: _MklRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        knowledge_node_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MklSyncEvent], int]:
        return await self._repository.list_for_knowledge(
            knowledge_node_id, limit=limit, offset=offset
        )
