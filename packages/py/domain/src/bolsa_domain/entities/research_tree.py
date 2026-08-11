"""Entidades de dominio del árbol de investigación y sus eventos de sincronización."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResearchTreeEdge:
    id: str
    from_ref_type: str
    from_ref_id: str
    to_ref_type: str
    to_ref_id: str
    edge_type: str
    created_at: str
    notes: str | None = None
    payload: dict[str, Any] | None = None
    deleted_at: str | None = None


@dataclass(frozen=True, slots=True)
class MklSyncEvent:
    id: str
    knowledge_node_id: str
    status: str
    fact_payload: dict[str, Any]
    math_version: str
    created_at: str
    notes: list[str]
