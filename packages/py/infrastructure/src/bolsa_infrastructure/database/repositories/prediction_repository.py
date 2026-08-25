"""Persistencia ART-MODEL / ART-PREDICTION (F2)."""

from __future__ import annotations

from datetime import UTC, datetime

from bolsa_domain.entities.cognitive_artifacts import ModelArtifactRecord, PredictionRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models.tables import ModelArtifactRow, PredictionRow


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class SqlAlchemyPredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_model(self, record: ModelArtifactRecord) -> ModelArtifactRecord:
        now = datetime.now(UTC)
        row = await self._session.get(ModelArtifactRow, record.id)
        trained = _parse_ts(record.trained_at)
        if row is None:
            row = ModelArtifactRow(
                id=record.id,
                model_id=record.model_id,
                model_version=record.model_version,
                framework=record.framework,
                feature_set_id=record.feature_set_id,
                composition_hash=record.composition_hash,
                model_checksum=record.model_checksum,
                trained_at=trained,
                payload=record.payload,
                updated_at=now,
                created_at=_parse_ts(record.created_at) or now,
            )
            self._session.add(row)
        else:
            row.model_id = record.model_id
            row.model_version = record.model_version
            row.framework = record.framework
            row.feature_set_id = record.feature_set_id
            row.composition_hash = record.composition_hash
            row.model_checksum = record.model_checksum
            row.trained_at = trained
            row.payload = record.payload
            row.updated_at = now
        await self._session.flush()
        return record

    async def get_model(self, model_id: str) -> ModelArtifactRecord | None:
        stmt = select(ModelArtifactRow).where(ModelArtifactRow.model_id == model_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return None if row is None else self._map_model(row)

    async def list_models(self, *, limit: int = 50) -> list[ModelArtifactRecord]:
        stmt = (
            select(ModelArtifactRow)
            .order_by(ModelArtifactRow.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._map_model(row) for row in result.scalars().all()]

    async def append_prediction(self, record: PredictionRecord) -> PredictionRecord:
        now = datetime.now(UTC)
        row = PredictionRow(
            id=record.id,
            instrument_id=record.instrument_id,
            model_id=record.model_id,
            model_version=record.model_version,
            horizon=record.horizon,
            value=record.value,
            confidence=record.confidence,
            as_of=_parse_ts(record.as_of),
            payload=record.payload,
            created_at=_parse_ts(record.created_at) or now,
        )
        self._session.add(row)
        await self._session.flush()
        return record

    async def list_predictions(
        self,
        *,
        instrument_id: str | None = None,
        model_id: str | None = None,
        limit: int = 40,
    ) -> list[PredictionRecord]:
        stmt = select(PredictionRow).order_by(PredictionRow.created_at.desc()).limit(limit)
        if instrument_id:
            stmt = stmt.where(PredictionRow.instrument_id == instrument_id)
        if model_id:
            stmt = stmt.where(PredictionRow.model_id == model_id)
        result = await self._session.execute(stmt)
        return [self._map_prediction(row) for row in result.scalars().all()]

    def _map_model(self, row: ModelArtifactRow) -> ModelArtifactRecord:
        return ModelArtifactRecord(
            id=row.id,
            model_id=row.model_id,
            model_version=row.model_version,
            framework=row.framework,
            feature_set_id=row.feature_set_id,
            created_at=_iso(row.created_at) or "",
            composition_hash=row.composition_hash,
            model_checksum=row.model_checksum,
            trained_at=_iso(row.trained_at),
            updated_at=_iso(row.updated_at),
            payload=dict(row.payload) if row.payload else None,
        )

    def _map_prediction(self, row: PredictionRow) -> PredictionRecord:
        return PredictionRecord(
            id=row.id,
            instrument_id=row.instrument_id,
            model_id=row.model_id,
            model_version=row.model_version,
            created_at=_iso(row.created_at) or "",
            horizon=row.horizon,
            value=float(row.value) if row.value is not None else None,
            confidence=float(row.confidence) if row.confidence is not None else None,
            as_of=_iso(row.as_of),
            payload=dict(row.payload) if row.payload else None,
        )
