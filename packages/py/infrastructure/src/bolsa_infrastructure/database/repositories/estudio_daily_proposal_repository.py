"""Repositorio SQLAlchemy — propuestas diarias ESTUDIO con identidad durable (058).

El contrato del handoff es pequeño y explícito:

* ``upsert_pending`` — registra la propuesta del parte. **Idempotente**: reejecutar el
  job del día no duplica la fila (la clave pendiente ``(cuenta, día, instrumento)``
  lo impide) y la identidad publicada nunca se pisa con un plan distinto.
* ``pending_for`` — lo que el productor puede adoptar: propuestas pendientes de la
  cuenta para esos instrumentos, con ``bar_date`` **no posterior** a la frontera de
  decisión (la frescura la declara la vela, no el reloj del job).
* ``mark_consumed`` / ``mark_settled`` — desenlace durable. Un cambio de estado es
  terminal: consumir dos veces la misma propuesta no puede atribuir dos ciclos.

Fail-closed: nada se rellena. Una propuesta sin ``decision_id`` se guarda igual (el
hueco es información) pero no se consume: sin identidad de plan no hay atribución
exacta posible.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.estudio_daily_proposal import (
    PROPOSAL_PENDING_STATUSES,
    PROPOSAL_STATUS_CONSUMED,
    PROPOSAL_STATUS_PROPOSED,
    EstudioDailyProposal,
)
from bolsa_infrastructure.database.models import EstudioDailyProposalRow
from bolsa_infrastructure.ids import new_id

__all__ = ["SqlAlchemyEstudioDailyProposalRepository"]


async def _commit_if(session: AsyncSession, autocommit: bool) -> None:
    """Commitea cuando el store es autónomo (default).

    La marca de consumo debe ser durable ANTES de emitir la orden: de ella depende que
    la cadena pueda atribuir el ciclo sin depender de que el proceso sobreviva.
    """
    if autocommit:
        await session.commit()


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _text(value: Any) -> str | None:
    """Texto normalizado o ``None`` (un hueco NUNCA se convierte en cadena vacía)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _upper(value: Any) -> str | None:
    text = _text(value)
    return None if text is None else text.upper()


class SqlAlchemyEstudioDailyProposalRepository:
    """Acceso durable a ``estudio_daily_proposals``."""

    def __init__(self, session: AsyncSession, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    # ── mapeo ────────────────────────────────────────────────────────────────

    def _map(self, row: EstudioDailyProposalRow) -> EstudioDailyProposal:
        return EstudioDailyProposal(
            id=row.id,
            account_id=row.account_id,
            day=row.day,
            instrument_id=row.instrument_id,
            status=row.status,
            symbol=row.symbol,
            decision_id=row.decision_id,
            signal_id=row.signal_id,
            strategy_definition_id=row.strategy_definition_id,
            strategy_version=row.strategy_version,
            preset_key=row.preset_key,
            bar_date=row.bar_date,
            plan=dict(row.plan or {}),
            consumed_cycle_id=row.consumed_cycle_id,
            consumed_at=_iso(row.consumed_at),
            reason=row.reason,
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        )

    # ── lectura ──────────────────────────────────────────────────────────────

    async def get(self, proposal_id: str) -> EstudioDailyProposal | None:
        stmt = select(EstudioDailyProposalRow).where(
            EstudioDailyProposalRow.id == proposal_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list_for_day(
        self, *, account_id: str, day: str
    ) -> list[EstudioDailyProposal]:
        """Todas las propuestas de una cuenta y día (cualquier estado)."""
        stmt = (
            select(EstudioDailyProposalRow)
            .where(
                EstudioDailyProposalRow.account_id == account_id,
                EstudioDailyProposalRow.day == day,
            )
            .order_by(EstudioDailyProposalRow.instrument_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(row) for row in rows]

    async def pending_for(
        self,
        *,
        account_id: str,
        instruments: Iterable[str],
        max_bar_date: str,
        limit: int = 200,
    ) -> list[EstudioDailyProposal]:
        """Propuestas PENDIENTES adoptables por el productor.

        ``instruments`` son las claves con las que el motor identifica el activo
        (símbolo en AUTO, id en ESTUDIO): se aceptan ambas porque la propuesta publica
        las dos. ``max_bar_date`` es la frontera de decisión: una propuesta con vela
        POSTERIOR no se adelanta (sería lookahead) y no se devuelve.
        """
        keys: set[str] = set()
        for item in instruments:
            text = _text(item)
            if text is not None:
                keys.add(text)
        if not keys:
            return []
        widened: set[str] = set(keys)
        widened.update(key.upper() for key in keys)
        stmt = (
            select(EstudioDailyProposalRow)
            .where(
                EstudioDailyProposalRow.account_id == account_id,
                EstudioDailyProposalRow.status.in_(PROPOSAL_PENDING_STATUSES),
                or_(
                    EstudioDailyProposalRow.instrument_id.in_(widened),
                    EstudioDailyProposalRow.symbol.in_(widened),
                ),
            )
            .order_by(
                desc(EstudioDailyProposalRow.bar_date),
                desc(EstudioDailyProposalRow.created_at),
            )
            .limit(max(1, min(int(limit), 500)))
        )
        if max_bar_date:
            stmt = stmt.where(
                or_(
                    EstudioDailyProposalRow.bar_date.is_(None),
                    EstudioDailyProposalRow.bar_date <= max_bar_date,
                )
            )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(row) for row in rows]

    # ── escritura ────────────────────────────────────────────────────────────

    async def upsert_pending(
        self,
        *,
        account_id: str,
        day: str,
        instrument_id: str,
        symbol: str | None = None,
        decision_id: str | None = None,
        signal_id: str | None = None,
        strategy_definition_id: str | None = None,
        strategy_version: int | None = None,
        preset_key: str | None = None,
        bar_date: str | None = None,
        plan: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> EstudioDailyProposal:
        """Registra (o reafirma) la propuesta pendiente del valor. Idempotente.

        Si ya existe una propuesta PENDIENTE para ``(cuenta, día, instrumento)`` se
        reutiliza su fila y se actualizan los campos que el parte vuelve a declarar; el
        estado NO retrocede (una propuesta ya consumida no vuelve a ``proposed``) y el
        ``consumed_cycle_id`` no se borra.
        """
        moment = now or datetime.now(UTC)
        stmt = select(EstudioDailyProposalRow).where(
            EstudioDailyProposalRow.account_id == account_id,
            EstudioDailyProposalRow.day == day,
            EstudioDailyProposalRow.instrument_id == instrument_id,
            EstudioDailyProposalRow.status == PROPOSAL_STATUS_PROPOSED,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = EstudioDailyProposalRow(
                id=new_id(),
                account_id=account_id,
                day=day,
                instrument_id=instrument_id,
                symbol=_upper(symbol),
                decision_id=_text(decision_id),
                signal_id=_text(signal_id),
                strategy_definition_id=_text(strategy_definition_id),
                strategy_version=(
                    int(strategy_version) if strategy_version is not None else None
                ),
                preset_key=_text(preset_key),
                bar_date=_text(bar_date),
                plan=dict(plan or {}),
                status=PROPOSAL_STATUS_PROPOSED,
                created_at=moment,
                updated_at=moment,
            )
            self._session.add(row)
            await self._session.flush()
            await _commit_if(self._session, self._autocommit)
            return self._map(row)
        row.symbol = _upper(symbol) or row.symbol
        row.decision_id = _text(decision_id) or row.decision_id
        row.signal_id = _text(signal_id) or row.signal_id
        row.strategy_definition_id = (
            _text(strategy_definition_id) or row.strategy_definition_id
        )
        row.strategy_version = (
            int(strategy_version)
            if strategy_version is not None
            else row.strategy_version
        )
        row.preset_key = _text(preset_key) or row.preset_key
        row.bar_date = _text(bar_date) or row.bar_date
        if plan:
            row.plan = dict(plan)
        row.updated_at = moment
        await self._session.flush()
        await _commit_if(self._session, self._autocommit)
        return self._map(row)

    async def mark_consumed(
        self,
        proposal_id: str,
        *,
        cycle_id: str,
        now: datetime | None = None,
    ) -> bool:
        """Marca ``consumed`` con el ciclo que la adoptó. ``False`` si ya no era pendiente.

        El chequeo de estado se hace en la MISMA sentencia (``UPDATE ... WHERE
        status='proposed'``): dos workers concurrentes no pueden atribuir dos ciclos a la
        misma propuesta.
        """
        moment = now or datetime.now(UTC)
        from sqlalchemy import update

        stmt = (
            update(EstudioDailyProposalRow)
            .where(
                EstudioDailyProposalRow.id == proposal_id,
                EstudioDailyProposalRow.status == PROPOSAL_STATUS_PROPOSED,
            )
            .values(
                status=PROPOSAL_STATUS_CONSUMED,
                consumed_cycle_id=_text(cycle_id),
                consumed_at=moment,
                reason=None,
                updated_at=moment,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        await _commit_if(self._session, self._autocommit)
        return cast(CursorResult[Any], result).rowcount > 0

    async def mark_settled(
        self,
        proposal_id: str,
        *,
        status: str,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        """Cierra la propuesta (``rejected``/``expired``) con su motivo. Terminal."""
        moment = now or datetime.now(UTC)
        from sqlalchemy import update

        stmt = (
            update(EstudioDailyProposalRow)
            .where(
                EstudioDailyProposalRow.id == proposal_id,
                EstudioDailyProposalRow.status == PROPOSAL_STATUS_PROPOSED,
            )
            .values(status=status, reason=_text(reason), updated_at=moment)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        await _commit_if(self._session, self._autocommit)
        return cast(CursorResult[Any], result).rowcount > 0

    async def has_pending(self, *, account_id: str, day: str) -> bool:
        """¿Queda alguna propuesta pendiente para ``(cuenta, día)``?"""
        stmt = (
            select(EstudioDailyProposalRow.id)
            .where(
                EstudioDailyProposalRow.account_id == account_id,
                EstudioDailyProposalRow.day == day,
                and_(
                    EstudioDailyProposalRow.status == PROPOSAL_STATUS_PROPOSED,
                    EstudioDailyProposalRow.decision_id.is_not(None),
                ),
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
