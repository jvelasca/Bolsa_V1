from typing import Any, Protocol

from bolsa_domain.entities.knowledge_node import KnowledgeNode


class KnowledgeNodeRepository(Protocol):
    async def insert(
        self,
        *,
        hypothesis_id: str,
        stage: str,
        statement: str,
        knowledge_confidence: float,
        validity_context: dict[str, Any],
        evidence_ids: list[str],
        belief_snapshot: dict[str, Any],
        consolidation_report: dict[str, Any],
        math_version: str,
        notes: str | None = None,
        node_id: str | None = None,
    ) -> KnowledgeNode: ...

    async def get_by_id(self, node_id: str) -> KnowledgeNode | None: ...

    async def list(
        self,
        *,
        hypothesis_id: str | None = None,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeNode], int]: ...

    async def list_active_for_hypothesis(
        self, hypothesis_id: str
    ) -> list[KnowledgeNode]: ...

    async def update_stage(
        self, node_id: str, stage: str
    ) -> KnowledgeNode | None: ...
