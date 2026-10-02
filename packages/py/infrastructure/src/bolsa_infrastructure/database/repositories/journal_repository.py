"""Persistencia append-only de decision_journal_entries (ADR-029 F1/F2)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
from bolsa_infrastructure.database.models import DecisionJournalEntryRow


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _row_to_record(row: DecisionJournalEntryRow) -> DecisionJournalEntryRecord:
    return DecisionJournalEntryRecord(
        id=row.id,
        decision_id=row.decision_id,
        event_type=row.event_type,
        actor=row.actor,
        created_at=_iso(row.created_at),
        session_id=row.session_id,
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        payload=dict(row.payload) if row.payload else None,
    )


class SqlAlchemyJournalRepository:
    """Implementación SQLAlchemy del puerto JournalWriter + lectura paginada (F2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: DecisionJournalEntryRecord) -> DecisionJournalEntryRecord:
        now = _parse_ts(entry.created_at) or datetime.now(UTC)
        row = DecisionJournalEntryRow(
            id=entry.id,
            decision_id=entry.decision_id,
            session_id=entry.session_id,
            account_id=entry.account_id,
            instrument_id=entry.instrument_id,
            event_type=entry.event_type,
            actor=entry.actor,
            payload=entry.payload,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return entry

    async def list_by_decision_ids(
        self,
        decision_ids: Sequence[str],
        *,
        limit: int | None = None,
    ) -> list[DecisionJournalEntryRecord]:
        """AUTO-10 — entradas de un conjunto de ``decision_id``, por el índice existente.

        Se lee por ``decision_id`` y **no** por ``payload->>'cycleId'``: la sonda de coste midió
        que la segunda obliga a un recorrido de la tabla (1348 filas, 56 buffers), mientras que
        la primera **tiene índice** y lo usa cuando se pide un solo id (0,03 ms frente a
        0,13 ms). Con una tanda grande sobre una tabla pequeña el planner prefiere el recorrido
        —es más barato que N sondas—, y eso está MEDIDO y declarado: <0,1 ms por tanda de 15
        ciclos. A escala no está medido; si el spine crece, la decisión es un índice parcial o de
        expresión, no cambiar la identidad.

        Más nueva primero (``created_at DESC``), que es justo lo que necesita la resolución del
        reintento ("última gana").

        No filtra por ``account_id`` ni por ``event_type``: el ``decision_id`` de un ciclo lo
        comparten su entrada de ventana y su traza de régimen, así que quien lee es quien
        confirma en el ``payload`` lo que le sirve (el lector puro lo hace y lo declara).
        """
        ids = [text for text in (str(value).strip() for value in decision_ids) if text]
        if not ids:
            return []
        statement = (
            select(DecisionJournalEntryRow)
            .where(DecisionJournalEntryRow.decision_id.in_(ids))
            .order_by(
                DecisionJournalEntryRow.created_at.desc(),
                DecisionJournalEntryRow.id.desc(),
            )
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return [_row_to_record(row) for row in result.scalars().all()]

    async def list_entries(
        self,
        *,
        account_id: str,
        instrument_id: str | None = None,
        since: str | None = None,
        event_type: str | None = None,
        engine_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DecisionJournalEntryRecord], int]:
        filters = [DecisionJournalEntryRow.account_id == account_id]
        if instrument_id:
            filters.append(DecisionJournalEntryRow.instrument_id == instrument_id)
        if since:
            since_dt = _parse_ts(since)
            if since_dt is not None:
                filters.append(DecisionJournalEntryRow.created_at >= since_dt)
        if event_type:
            filters.append(DecisionJournalEntryRow.event_type == event_type)
        # Alcance por motor (AUTO monitor A4): el evento durable ``auto_entry_decision`` sella
        # ``engineId`` en el ``payload`` (JSONB, sin migración). Con ``engine_id`` se acota la
        # lectura al motor que la produce: dos motores de una cuenta no comparten "última decisión".
        if engine_id:
            filters.append(
                DecisionJournalEntryRow.payload["engineId"].as_string() == engine_id
            )

        count_stmt = select(func.count()).select_from(DecisionJournalEntryRow).where(*filters)
        count_result = await self._session.execute(count_stmt)
        total = int(count_result.scalar_one())

        stmt = (
            select(DecisionJournalEntryRow)
            .where(*filters)
            # Desempate determinista (``id``) para que un ``LIMIT`` sobre timestamps empatados
            # (resolución limitada) no dependa del orden físico de la tabla.
            .order_by(
                DecisionJournalEntryRow.created_at.desc(),
                DecisionJournalEntryRow.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_record(row) for row in rows], total

    async def aggregate_auto_operational_audit(
        self,
        *,
        account_id: str,
        claim_event_type: str = "auto_reservation_claim",
        reconciliation_event_type: str = "auto_reservation_reconciliation",
        grace_window_reason: str = "grace_window_keep",
    ) -> dict[str, int]:
        """(AUTO Monitor) conteos GLOBALES de la auditoría operativa, agregados en la base.

        El monitor proyecta claims/reconciliaciones y necesita contadores **completos**: cargar
        las filas con un ``limit`` truncaba el universo y lo declaraba ``COMPLETE``. Aquí se
        agrega con ``COUNT(*) FILTER`` sobre el mismo ``account_id`` y ``event_type`` del índice,
        de modo que el conteo **no depende del límite de lectura** y no escala con el número de
        eventos. Los campos del ``payload`` se leen como texto (``->>``); un campo ausente/null
        sale ``NULL`` (no declarado) y por eso ``lostClaimsUndeclaredConflict`` los separa.

        Los ``event_type``/motivo llegan por parámetro (con defaults locales) para no invertir la
        dirección infraestructura→aplicación: la fuente única de los literales sigue en
        ``auto_operational_monitor`` y el monitor los inyecta.
        """
        claims = DecisionJournalEntryRow.event_type == claim_event_type
        reconciliations = DecisionJournalEntryRow.event_type == reconciliation_event_type
        claimed = DecisionJournalEntryRow.payload["claimed"].as_string()
        conflict = DecisionJournalEntryRow.payload["conflict"].as_string()
        reason = DecisionJournalEntryRow.payload["reason"].as_string()
        statement = select(
            func.count().filter(claims).label("claimAttempts"),
            func.count().filter(claims, claimed == "true").label("successfulClaims"),
            func.count().filter(claims, claimed == "false").label("lostClaims"),
            func.count().filter(claims, conflict == "true").label("raceConflicts"),
            func.count()
            .filter(claims, claimed == "false", conflict.is_(None))
            .label("lostClaimsUndeclaredConflict"),
            func.count().filter(reconciliations).label("reconciliations"),
            func.count().filter(reconciliations, reason == grace_window_reason).label(
                "graceWindowKeeps"
            ),
        ).where(DecisionJournalEntryRow.account_id == account_id)
        result = await self._session.execute(statement)
        row = result.mappings().one()
        return {key: int(value or 0) for key, value in row.items()}



# Alias retrocompatible con F1 (JournalWriter DI).
SqlAlchemyJournalWriter = SqlAlchemyJournalRepository
