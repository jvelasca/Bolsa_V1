"""Contrato/Puerto de repositorio del snapshot de evidencia de discovery (Protocol).

V2.36 (incremento 1): persistencia versionada del prior que alimenta el carril
``adaptive`` del ``DiscoveryBudgetAllocator``. Solo lectura/escritura del snapshot: no
toca decisiones de promoción ni el hot path del discovery.
"""
from typing import Protocol

from bolsa_domain.entities.discovery_evidence_snapshot import DiscoveryEvidenceSnapshot


class DiscoveryEvidenceSnapshotRepository(Protocol):
    """Persistencia append-only de snapshots de evidencia (inmutables por hash)."""

    async def save(
        self, snapshot: DiscoveryEvidenceSnapshot
    ) -> DiscoveryEvidenceSnapshot: ...

    async def get_latest(self) -> DiscoveryEvidenceSnapshot | None: ...

    async def get_by_hash(
        self, snapshot_hash: str
    ) -> DiscoveryEvidenceSnapshot | None: ...

    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryEvidenceSnapshot]: ...
