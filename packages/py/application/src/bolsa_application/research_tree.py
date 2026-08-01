"""P2.E — Research Tree mínimo (ADR-011 D20)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_domain.entities.research_tree import ResearchTreeEdge

ALLOWED_REF_TYPES = frozenset({"hypothesis", "knowledge", "evidence"})
ALLOWED_EDGE_TYPES = frozenset(
    {
        "SUPPORTS",
        "CONTRADICTS",
        "DEPENDS_ON",
        "SPECIAL_CASE_OF",
        "GENERALIZES",
        "CORRELATED_WITH",
        "HYPOTHESIZED_CAUSES",
        # CAUSES reserved — blocked in v0 (ADR-012 L1)
    }
)
BLOCKED_EDGE_TYPES = frozenset({"CAUSES"})


class _TreeRepo(Protocol):
    async def insert(
        self,
        *,
        from_ref_type: str,
        from_ref_id: str,
        to_ref_type: str,
        to_ref_id: str,
        edge_type: str,
        notes: str | None = None,
        payload: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> ResearchTreeEdge: ...

    async def get_by_id(self, edge_id: str) -> ResearchTreeEdge | None: ...

    async def soft_delete(self, edge_id: str) -> ResearchTreeEdge | None: ...

    async def list_edges(
        self,
        *,
        from_ref_type: str | None = None,
        from_ref_id: str | None = None,
        to_ref_type: str | None = None,
        to_ref_id: str | None = None,
        edge_type: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ResearchTreeEdge], int]: ...


def validate_edge_spec(
    *,
    from_ref_type: str,
    from_ref_id: str,
    to_ref_type: str,
    to_ref_id: str,
    edge_type: str,
) -> None:
    if from_ref_type not in ALLOWED_REF_TYPES:
        raise ValueError(f"fromRefType: uno de {sorted(ALLOWED_REF_TYPES)}")
    if to_ref_type not in ALLOWED_REF_TYPES:
        raise ValueError(f"toRefType: uno de {sorted(ALLOWED_REF_TYPES)}")
    if not from_ref_id or not to_ref_id:
        raise ValueError("fromRefId y toRefId son obligatorios")
    if edge_type in BLOCKED_EDGE_TYPES:
        raise ValueError(
            "CAUSES prohibido en P2.E — usar HYPOTHESIZED_CAUSES (ADR-012 L1)"
        )
    if edge_type not in ALLOWED_EDGE_TYPES:
        raise ValueError(f"edgeType: uno de {sorted(ALLOWED_EDGE_TYPES)}")
    if from_ref_type == to_ref_type and from_ref_id == to_ref_id:
        raise ValueError("arista reflexiva no permitida")


def consolidation_tree_edge_specs(
    *,
    hypothesis_id: str,
    knowledge_node: KnowledgeNode,
) -> list[dict[str, Any]]:
    """Edges created when Consolidation succeeds (P2.D→P2.E bridge)."""
    specs: list[dict[str, Any]] = []
    for eid in knowledge_node.evidence_ids:
        specs.append(
            {
                "from_ref_type": "evidence",
                "from_ref_id": eid,
                "to_ref_type": "hypothesis",
                "to_ref_id": hypothesis_id,
                "edge_type": "SUPPORTS",
                "notes": "auto:consolidation",
                "payload": {"source": "consolidation_lab_v0"},
            }
        )
    specs.append(
        {
            "from_ref_type": "hypothesis",
            "from_ref_id": hypothesis_id,
            "to_ref_type": "knowledge",
            "to_ref_id": knowledge_node.id,
            "edge_type": "GENERALIZES",
            "notes": "auto:consolidation",
            "payload": {"source": "consolidation_lab_v0", "stage": knowledge_node.stage},
        }
    )
    return specs


class CreateResearchTreeEdge:
    def __init__(self, repository: _TreeRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        from_ref_type: str,
        from_ref_id: str,
        to_ref_type: str,
        to_ref_id: str,
        edge_type: str,
        notes: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ResearchTreeEdge:
        validate_edge_spec(
            from_ref_type=from_ref_type,
            from_ref_id=from_ref_id,
            to_ref_type=to_ref_type,
            to_ref_id=to_ref_id,
            edge_type=edge_type,
        )
        return await self._repository.insert(
            from_ref_type=from_ref_type,
            from_ref_id=from_ref_id,
            to_ref_type=to_ref_type,
            to_ref_id=to_ref_id,
            edge_type=edge_type,
            notes=notes,
            payload=payload,
        )


class ListResearchTreeEdges:
    def __init__(self, repository: _TreeRepo) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        from_ref_type: str | None = None,
        from_ref_id: str | None = None,
        to_ref_type: str | None = None,
        to_ref_id: str | None = None,
        edge_type: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ResearchTreeEdge], int]:
        if edge_type is not None and edge_type not in ALLOWED_EDGE_TYPES | BLOCKED_EDGE_TYPES:
            raise ValueError(f"edgeType inválido: {edge_type}")
        return await self._repository.list_edges(
            from_ref_type=from_ref_type,
            from_ref_id=from_ref_id,
            to_ref_type=to_ref_type,
            to_ref_id=to_ref_id,
            edge_type=edge_type,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )


class SoftDeleteResearchTreeEdge:
    def __init__(self, repository: _TreeRepo) -> None:
        self._repository = repository

    async def execute(self, edge_id: str) -> ResearchTreeEdge | None:
        return await self._repository.soft_delete(edge_id)


async def link_consolidation_tree(
    tree_repo: _TreeRepo | None,
    *,
    hypothesis_id: str,
    knowledge_node: KnowledgeNode,
) -> list[ResearchTreeEdge]:
    if tree_repo is None:
        return []
    created: list[ResearchTreeEdge] = []
    for spec in consolidation_tree_edge_specs(
        hypothesis_id=hypothesis_id, knowledge_node=knowledge_node
    ):
        created.append(await tree_repo.insert(**spec))
    return created
