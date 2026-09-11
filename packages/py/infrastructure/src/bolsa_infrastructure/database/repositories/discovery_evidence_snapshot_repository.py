from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.discovery_evidence_snapshot import DiscoveryEvidenceSnapshot
from bolsa_infrastructure.database.models import DiscoveryEvidenceSnapshotRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyDiscoveryEvidenceSnapshotRepository:
    """Persistencia append-only de snapshots de evidencia (V2.36, incremento 1).

    Inmutable por ``snapshot_hash``: ``save`` es idempotente (si el hash ya existe
    devuelve la fila almacenada sin reescribirla). El worker solo necesita
    ``get_latest``; el resto de métodos sirven al job batch y a la auditoría.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: DiscoveryEvidenceSnapshotRow) -> DiscoveryEvidenceSnapshot:
        payload = row.payload if isinstance(row.payload, dict) else {}
        family_weights = {
            str(k): float(v) for k, v in (payload.get("familyWeights") or {}).items()
        }
        lane_weights = {
            str(k): float(v) for k, v in (payload.get("laneWeights") or {}).items()
        }
        sample_sizes = {
            str(k): int(v) for k, v in (payload.get("sampleSizes") or {}).items()
        }
        return DiscoveryEvidenceSnapshot(
            id=row.id,
            snapshot_hash=row.snapshot_hash,
            math_version=row.math_version,
            window_from=row.window_from or "",
            window_to=row.window_to or "",
            family_weights=family_weights,
            lane_weights=lane_weights,
            sample_sizes=sample_sizes,
            payload=payload,
            created_at=row.created_at.isoformat(),
        )

    async def save(
        self, snapshot: DiscoveryEvidenceSnapshot
    ) -> DiscoveryEvidenceSnapshot:
        """Persiste el snapshot; idempotente por ``snapshot_hash``."""
        existing = await self.get_by_hash(snapshot.snapshot_hash)
        if existing is not None:
            return existing
        row = DiscoveryEvidenceSnapshotRow(
            id=snapshot.id or new_id(),
            snapshot_hash=snapshot.snapshot_hash,
            math_version=snapshot.math_version,
            window_from=snapshot.window_from or None,
            window_to=snapshot.window_to or None,
            payload=snapshot.payload,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_latest(self) -> DiscoveryEvidenceSnapshot | None:
        stmt = (
            select(DiscoveryEvidenceSnapshotRow)
            .order_by(desc(DiscoveryEvidenceSnapshotRow.created_at))
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def get_by_hash(
        self, snapshot_hash: str
    ) -> DiscoveryEvidenceSnapshot | None:
        stmt = select(DiscoveryEvidenceSnapshotRow).where(
            DiscoveryEvidenceSnapshotRow.snapshot_hash == snapshot_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list_recent(self, *, limit: int = 20) -> list[DiscoveryEvidenceSnapshot]:
        stmt = (
            select(DiscoveryEvidenceSnapshotRow)
            .order_by(desc(DiscoveryEvidenceSnapshotRow.created_at))
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]
