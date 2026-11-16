"""Repositorio SQLAlchemy — índice durable de la verificación periódica (ADR-050).

Contrato
--------
* **Un run sellado no se reescribe.** Si llega la misma clave natural
  ``(account_id, profile_id, kind, day, to_day)`` con un ``measurement_hash`` distinto, el
  repositorio levanta :class:`SealedVerificationRunConflictError`: una corrección de barras o
  un rejuego distinto es una **identidad nueva** que debe declararse, no un ``UPDATE``
  silencioso que cambiaría la historia.
* Misma clave y mismo ``measurement_hash`` ⇒ idempotente: devuelve la fila existente.
* ``kind`` separa ``epoch`` (decide) de ``rolling`` (historial). La ventana móvil nunca puede
  confundirse con una época porque la clave la distingue.

El JSON del artefacto sigue siendo la fuente de verdad de la medición; ``payload`` guarda el
veredicto y sus gates para consulta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import StrategyVerificationRunRow
from bolsa_infrastructure.ids import new_id

__all__ = [
    "SealedVerificationRunConflictError",
    "SqlAlchemyStrategyVerificationRepository",
    "VerificationRunRecord",
]


class SealedVerificationRunConflictError(ValueError):
    """La misma época ya está sellada con OTRA medición."""


@dataclass(frozen=True, slots=True)
class VerificationRunRecord:
    id: str
    account_id: str
    profile_id: str
    profile_hash: str
    kind: str
    day: str
    to_day: str
    measurement_hash: str
    verdict: str
    strategy_version: str | None
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "accountId": self.account_id,
            "profileId": self.profile_id,
            "profileHash": self.profile_hash,
            "kind": self.kind,
            "day": self.day,
            "toDay": self.to_day,
            "measurementHash": self.measurement_hash,
            "verdict": self.verdict,
            "strategyVersion": self.strategy_version,
            "payload": self.payload,
            "createdAt": self.created_at,
        }


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


class SqlAlchemyStrategyVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: StrategyVerificationRunRow) -> VerificationRunRecord:
        return VerificationRunRecord(
            id=row.id,
            account_id=row.account_id,
            profile_id=row.profile_id,
            profile_hash=row.profile_hash,
            kind=row.kind,
            day=str(row.day),
            to_day=str(row.to_day),
            measurement_hash=row.measurement_hash,
            verdict=row.verdict,
            strategy_version=row.strategy_version,
            payload=row.payload if isinstance(row.payload, dict) else {},
            created_at=_iso(row.created_at),
        )

    async def _find(
        self,
        *,
        account_id: str,
        profile_id: str,
        kind: str,
        day: str,
        to_day: str,
    ) -> StrategyVerificationRunRow | None:
        stmt = select(StrategyVerificationRunRow).where(
            StrategyVerificationRunRow.account_id == account_id,
            StrategyVerificationRunRow.profile_id == profile_id,
            StrategyVerificationRunRow.kind == kind,
            StrategyVerificationRunRow.day == date.fromisoformat(day),
            StrategyVerificationRunRow.to_day == date.fromisoformat(to_day),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_run(
        self,
        *,
        account_id: str,
        profile_id: str,
        profile_hash: str,
        kind: str,
        day: str,
        to_day: str,
        measurement_hash: str,
        verdict: str,
        strategy_version: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> VerificationRunRecord:
        """Inserta el run o devuelve el existente si es la MISMA medición."""
        existing = await self._find(
            account_id=account_id,
            profile_id=profile_id,
            kind=kind,
            day=day,
            to_day=to_day,
        )
        if existing is not None:
            if existing.measurement_hash != measurement_hash:
                raise SealedVerificationRunConflictError(
                    "la época ya está sellada con otra medición: "
                    f"{existing.measurement_hash[:12]} != {measurement_hash[:12]}. "
                    "Una revisión de datos exige declarar una identidad nueva, no reescribir."
                )
            return self._map(existing)

        statement = (
            pg_insert(StrategyVerificationRunRow)
            .values(
                id=new_id(),
                account_id=account_id,
                profile_id=profile_id,
                profile_hash=profile_hash,
                kind=kind,
                day=date.fromisoformat(day),
                to_day=date.fromisoformat(to_day),
                measurement_hash=measurement_hash,
                verdict=verdict,
                strategy_version=strategy_version,
                payload=dict(payload or {}),
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "profile_id", "kind", "day", "to_day"]
            )
            .returning(StrategyVerificationRunRow.id)
        )
        inserted = (await self._session.execute(statement)).scalar_one_or_none()
        await self._session.flush()
        if inserted is None:
            # Carrera con otra transacción: se resuelve releyendo (misma medición o conflicto).
            raced = await self._find(
                account_id=account_id,
                profile_id=profile_id,
                kind=kind,
                day=day,
                to_day=to_day,
            )
            if raced is None:
                raise SealedVerificationRunConflictError("no se pudo insertar ni releer el run")
            if raced.measurement_hash != measurement_hash:
                raise SealedVerificationRunConflictError(
                    "otra transacción selló la época con una medición distinta"
                )
            return self._map(raced)
        row = await self._find(
            account_id=account_id,
            profile_id=profile_id,
            kind=kind,
            day=day,
            to_day=to_day,
        )
        if row is None:  # pragma: no cover — la fila recién insertada debe existir
            raise SealedVerificationRunConflictError("run insertado pero no releíble")
        return self._map(row)

    async def latest(
        self, *, account_id: str, profile_id: str | None = None
    ) -> VerificationRunRecord | None:
        stmt = select(StrategyVerificationRunRow).where(
            StrategyVerificationRunRow.account_id == account_id
        )
        if profile_id is not None:
            stmt = stmt.where(StrategyVerificationRunRow.profile_id == profile_id)
        stmt = stmt.order_by(
            StrategyVerificationRunRow.to_day.desc(),
            StrategyVerificationRunRow.created_at.desc(),
        ).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list_runs(
        self,
        *,
        account_id: str,
        profile_id: str | None = None,
        kind: str | None = None,
        limit: int = 200,
    ) -> tuple[VerificationRunRecord, ...]:
        """Histórico ascendente (para dibujar la serie) acotado por ``limit``.

        Se ordena ascendente y se recorta por la cola: el llamante recibe las ``limit``
        épocas más recientes, en orden temporal natural.
        """
        stmt = select(StrategyVerificationRunRow).where(
            StrategyVerificationRunRow.account_id == account_id
        )
        if profile_id is not None:
            stmt = stmt.where(StrategyVerificationRunRow.profile_id == profile_id)
        if kind is not None:
            stmt = stmt.where(StrategyVerificationRunRow.kind == kind)
        stmt = stmt.order_by(
            StrategyVerificationRunRow.to_day.asc(),
            StrategyVerificationRunRow.created_at.asc(),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        bound = max(1, int(limit))
        return tuple(self._map(row) for row in rows[-bound:])
