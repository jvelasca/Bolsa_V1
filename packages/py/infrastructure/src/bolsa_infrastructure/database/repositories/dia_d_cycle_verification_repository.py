"""Repositorio SQLAlchemy — verificación DÍA-D enlazada a un ciclo AUTO (P2/v111).

El ``upsert`` es **atómico** (``INSERT ... ON CONFLICT DO UPDATE``) y está acotado por
``account_id`` en la clave natural ``(account_id, cycle_id, dia_d, end_date, mode)``: re-verificar
el mismo ciclo de la MISMA cuenta actualiza la fila; el ciclo de OTRA cuenta no se reasigna jamás
(guarda explícita antes de escribir).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification
from bolsa_infrastructure.database.models import DiaDCycleVerificationRow
from bolsa_infrastructure.ids import new_id

#: Columnas que participan de la clave natural del ``upsert`` (debe casar con la
#: ``UniqueConstraint`` de la tabla/migración 054).
_CONFLICT_COLUMNS = ("account_id", "cycle_id", "dia_d", "end_date", "mode")


class DiaDCycleVerificationOwnershipConflictError(ValueError):
    """El ``cycleId`` ya está verificado por OTRA cuenta: nunca se reasigna la fila."""


class SqlAlchemyDiaDCycleVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: DiaDCycleVerificationRow) -> DiaDCycleVerification:
        return DiaDCycleVerification(
            id=row.id,
            cycle_id=row.cycle_id,
            account_id=row.account_id,
            instrument_id=row.instrument_id,
            symbol=row.symbol,
            dia_d=row.dia_d,
            end_date=row.end_date,
            mode=row.mode,
            created_at=row.created_at.isoformat(),
            strategy_preset_key=row.strategy_preset_key,
            strategy_version=row.strategy_version,
            strategy_definition_id=row.strategy_definition_id,
            band=row.band,
            result=row.result if isinstance(row.result, dict) else None,
            research_evidence_id=row.research_evidence_id,
            facts_hash=getattr(row, "facts_hash", None),
            verified_by=getattr(row, "verified_by", None),
        )

    async def _find(
        self,
        *,
        cycle_id: str,
        dia_d: str,
        end_date: str,
        mode: str,
        account_id: str | None,
    ) -> DiaDCycleVerificationRow | None:
        stmt = select(DiaDCycleVerificationRow).where(
            DiaDCycleVerificationRow.cycle_id == cycle_id,
            DiaDCycleVerificationRow.dia_d == dia_d,
            DiaDCycleVerificationRow.end_date == end_date,
            DiaDCycleVerificationRow.mode == mode,
        )
        if account_id is None:
            stmt = stmt.where(DiaDCycleVerificationRow.account_id.is_(None))
        else:
            stmt = stmt.where(DiaDCycleVerificationRow.account_id == account_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _find_foreign_owner(
        self,
        *,
        cycle_id: str,
        dia_d: str,
        end_date: str,
        mode: str,
        account_id: str | None,
    ) -> str | None:
        """``account_id`` de una fila con la MISMA clave natural pero de OTRA cuenta (o ``None``).

        Defensa explícita: un ``cycleId`` ya verificado por otra cuenta NUNCA se reasigna. Con la
        clave natural acotada por ``account_id`` el ``ON CONFLICT`` ya no puede alcanzar la fila
        ajena; esta guarda convierte el intento en un **conflicto declarado** (409 en la ruta) en
        vez de crear una verificación fantasma de la otra cuenta.

        **Límite declarado:** es una comprobación *previa* (``SELECT`` + ``INSERT``), no un cierre
        atómico; bajo una carrera real de dos cuentas a la vez la fila ajena no se pisa (la clave
        acotada lo impide) pero podría crearse la segunda. En el modelo operativo single-cuenta el
        caso no ocurre; su valor es hacer **visible** la anomalía, no certificar exclusividad.
        """
        stmt = select(DiaDCycleVerificationRow.account_id).where(
            DiaDCycleVerificationRow.cycle_id == cycle_id,
            DiaDCycleVerificationRow.dia_d == dia_d,
            DiaDCycleVerificationRow.end_date == end_date,
            DiaDCycleVerificationRow.mode == mode,
        )
        if account_id is None:
            stmt = stmt.where(DiaDCycleVerificationRow.account_id.is_not(None))
        else:
            stmt = stmt.where(DiaDCycleVerificationRow.account_id != account_id)
        return (await self._session.execute(stmt.limit(1))).scalar_one_or_none()

    async def upsert(
        self,
        *,
        cycle_id: str,
        instrument_id: str,
        symbol: str,
        dia_d: str,
        end_date: str,
        mode: str,
        account_id: str | None = None,
        strategy_preset_key: str | None = None,
        strategy_version: str | None = None,
        strategy_definition_id: str | None = None,
        band: str | None = None,
        result: dict[str, Any] | None = None,
        research_evidence_id: str | None = None,
        facts_hash: str | None = None,
        verified_by: str | None = None,
        verification_id: str | None = None,
    ) -> DiaDCycleVerification:
        """Idempotente por ``(account_id, cycle_id, dia_d, end_date, mode)``, ATÓMICO.

        Un ``field`` ``None`` NO se rellena con relleno: se persiste el hueco declarado. La
        operación es un único ``INSERT ... ON CONFLICT DO UPDATE`` (sin ``SELECT``+``INSERT``),
        de modo que dos peticiones concurrentes convergen en una sola fila.
        """
        foreign_owner = await self._find_foreign_owner(
            cycle_id=cycle_id,
            dia_d=dia_d,
            end_date=end_date,
            mode=mode,
            account_id=account_id,
        )
        if foreign_owner is not None:
            raise DiaDCycleVerificationOwnershipConflictError(
                f"cycle {cycle_id} ya verificado por otra cuenta"
            )

        values: dict[str, Any] = {
            "id": verification_id or new_id(),
            "cycle_id": cycle_id,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "symbol": symbol,
            "strategy_preset_key": strategy_preset_key,
            "strategy_version": strategy_version,
            "strategy_definition_id": strategy_definition_id,
            "dia_d": dia_d,
            "end_date": end_date,
            "mode": mode,
            "band": band,
            "result": result or {},
            "research_evidence_id": research_evidence_id,
            "facts_hash": facts_hash,
            "verified_by": verified_by,
            "created_at": datetime.now(UTC),
        }
        insert_stmt = pg_insert(DiaDCycleVerificationRow).values(**values)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=list(_CONFLICT_COLUMNS),
            set_={
                "instrument_id": insert_stmt.excluded.instrument_id,
                "symbol": insert_stmt.excluded.symbol,
                "strategy_preset_key": insert_stmt.excluded.strategy_preset_key,
                "strategy_version": insert_stmt.excluded.strategy_version,
                "strategy_definition_id": insert_stmt.excluded.strategy_definition_id,
                "band": insert_stmt.excluded.band,
                "result": insert_stmt.excluded.result,
                "research_evidence_id": insert_stmt.excluded.research_evidence_id,
                "facts_hash": insert_stmt.excluded.facts_hash,
                "verified_by": insert_stmt.excluded.verified_by,
                "created_at": insert_stmt.excluded.created_at,
            },
        ).returning(DiaDCycleVerificationRow)
        row = (await self._session.execute(stmt)).scalar_one()
        return self._map(row)

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]:
        """Verificaciones del principal; con ``cycle_id`` acota a un ciclo.

        ``account_id`` es el aislamiento por cuenta (fail-closed en el llamante).
        """
        filters = []
        if account_id is not None:
            filters.append(DiaDCycleVerificationRow.account_id == account_id)
        if cycle_id is not None:
            filters.append(DiaDCycleVerificationRow.cycle_id == cycle_id)
        stmt = select(DiaDCycleVerificationRow)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(DiaDCycleVerificationRow.created_at)).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]

    async def get_by_id(self, verification_id: str) -> DiaDCycleVerification | None:
        stmt = select(DiaDCycleVerificationRow).where(
            DiaDCycleVerificationRow.id == verification_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)
