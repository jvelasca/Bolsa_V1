"""ExitOrderStore — espejo durable del INTENT de salida (``auto_exit_orders``, V2.43.3).

Puente entre el modelo **puro** ``bolsa_analytics.cognitive.exit_order.ExitOrder`` y su tabla
en PostgreSQL (migración ``043_exit_identity_and_kill_state``). El modelo puro es el dueño de
la aritmética (qué es un fill, cuál es la cola); este módulo **no recalcula nada**: persiste
y recupera.

Por qué existe un store y no basta el ``ExitPlan`` del tick:

* el plan vive **dentro** de ``plan_v2_tick`` y muere al volver de la función; tras un
  crash nadie sabe qué salida quedó a medias;
* la identidad de salida era ``exit:{engine}:{symbol}:{seq}`` con ``seq`` de un contador de
  proceso que volvía a 0 en cada arranque, así que un reinicio podía REUTILIZAR una
  identidad histórica (y, con ``ON CONFLICT ... UPDATE``, actualizar una reserva antigua);
* el ``execution_id`` es por FILL, así que no puede nombrar la cola viva de una salida
  parcial.

El ``exit_order_id`` se persiste **antes** de reservar y de emitir, y sobrevive a

    decisión → reserva → orden → fills parciales → reintento → reinicio.

Convenciones del repo (patrón ``reservation_store``): imports de fila perezosos,
``ON CONFLICT`` para idempotencia, ``autocommit`` explícito y lectura acotada (``limit``: el
llamante que recibe exactamente ``limit`` filas **no** puede afirmar que vio todo el libro).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from bolsa_analytics.cognitive.exit_order import (
    OPEN_STATES,
    ExitOrder,
    build_exit_order,
)

__all__ = [
    "InMemoryExitOrderStore",
    "ExitOrderStore",
    "PostgresExitOrderStore",
]

_WRITABLE_COLUMNS: tuple[str, ...] = (
    "account_id",
    "engine_id",
    "instrument_id",
    "side",
    "requested_qty",
    "filled_qty",
    "remaining_qty",
    "reservation_id",
    "venue_order_id",
    "state",
    "emergency",
    "reason",
    "created_at",
    "updated_at",
    "cycle_id",
)

#: Estados que representan un INTENT vivo.
_OPEN_STATE_VALUES: tuple[str, ...] = tuple(sorted(OPEN_STATES))


class ExitOrderStore(Protocol):
    """Persistencia de los INTENT de salida."""

    async def save(self, order: ExitOrder) -> bool:
        """Alta/actualización idempotente por ``exit_order_id``; ``True`` si insertó."""
        ...

    async def get(self, exit_order_id: str) -> ExitOrder | None:
        """El intent con esa identidad, o ``None`` (desconocido ≠ cerrado)."""
        ...

    async def list_open(self, account_id: str | None, *, limit: int = 500) -> list[ExitOrder]:
        """INTENT vivos de la cuenta (los que aún tienen cola por materializar)."""
        ...

    async def commit(self) -> None:
        """Hace durable lo escrito (no-op en el store in-memory)."""
        ...


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value.isoformat())
    except AttributeError:
        return str(value)


def _to_instant(value: Any) -> Any:
    from datetime import UTC, datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _row_to_order(row: Any) -> ExitOrder | None:
    return build_exit_order(
        exit_order_id=row.exit_order_id,
        instrument_id=row.instrument_id,
        side=row.side,
        requested_qty=_as_float(row.requested_qty),
        account_id=row.account_id or "",
        engine_id=row.engine_id or "",
        filled_qty=_as_float(row.filled_qty) or 0.0,
        remaining_qty=_as_float(row.remaining_qty),
        reservation_id=row.reservation_id,
        venue_order_id=row.venue_order_id,
        state=row.state,
        emergency=row.emergency,
        reason=row.reason,
        created_at=_to_iso(row.created_at),
        updated_at=_to_iso(row.updated_at),
        cycle_id=getattr(row, "cycle_id", None),
    )


def _order_values(order: ExitOrder) -> dict[str, Any]:
    return {
        "exit_order_id": order.exit_order_id,
        "account_id": order.account_id or None,
        "engine_id": order.engine_id or None,
        "instrument_id": order.instrument_id or None,
        "side": order.side or None,
        "requested_qty": order.requested_qty,
        "filled_qty": order.filled_qty,
        "remaining_qty": order.remaining_qty,
        "reservation_id": order.reservation_id,
        "venue_order_id": order.venue_order_id,
        "state": order.state,
        "emergency": order.emergency,
        "reason": order.reason,
        "created_at": _to_instant(order.created_at),
        "updated_at": _to_instant(order.updated_at),
        "cycle_id": order.cycle_id,
    }


class InMemoryExitOrderStore:
    """Store in-memory con la MISMA semántica que el PG (tests y camino hermético)."""

    def __init__(self, seed: Iterable[ExitOrder] = ()) -> None:
        self._rows: dict[str, ExitOrder] = {order.exit_order_id: order for order in seed}

    def __len__(self) -> int:
        return len(self._rows)

    async def save(self, order: ExitOrder) -> bool:
        key = order.exit_order_id
        inserted = key not in self._rows
        self._rows[key] = order
        return inserted

    async def get(self, exit_order_id: str) -> ExitOrder | None:
        return self._rows.get(str(exit_order_id or "").strip())

    async def list_open(self, account_id: str | None, *, limit: int = 500) -> list[ExitOrder]:
        if limit <= 0:
            return []
        rows = [
            row
            for row in self._rows.values()
            if row.is_open and (account_id is None or row.account_id == account_id)
        ]
        rows.sort(key=lambda row: (row.created_at or "", row.exit_order_id))
        return rows[:limit]

    async def commit(self) -> None:
        """No-op: el store in-memory ya es visible (espeja el contrato del PG)."""
        return None


class PostgresExitOrderStore:
    """``auto_exit_orders`` en PostgreSQL (idempotente por ``exit_order_id``)."""

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def save(self, order: ExitOrder) -> bool:
        """Alta idempotente; ``False`` + ``UPDATE`` si la identidad ya existía.

        Igual que el store de reservas: el contrato necesita saber si insertó o actualizó,
        así que se resuelve en dos pasos (``ON CONFLICT DO NOTHING`` + ``UPDATE``).
        """
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import AutoExitOrderRow

        values = _order_values(order)
        insert_statement = (
            pg_insert(AutoExitOrderRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["exit_order_id"])
            .returning(AutoExitOrderRow.exit_order_id)
        )
        result = await self._session.execute(insert_statement)
        inserted = result.scalars().first() is not None
        if not inserted:
            update_values = {name: values[name] for name in _WRITABLE_COLUMNS}
            await self._session.execute(
                sa.update(AutoExitOrderRow)
                .where(AutoExitOrderRow.exit_order_id == order.exit_order_id)
                .values(**update_values)
            )
        if self._autocommit:
            await self._session.commit()
        return inserted

    async def get(self, exit_order_id: str) -> ExitOrder | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoExitOrderRow

        row = (
            await self._session.execute(
                sa.select(AutoExitOrderRow).where(
                    AutoExitOrderRow.exit_order_id == str(exit_order_id or "").strip()
                )
            )
        ).scalar_one_or_none()
        return None if row is None else _row_to_order(row)

    async def list_open(self, account_id: str | None, *, limit: int = 500) -> list[ExitOrder]:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import AutoExitOrderRow

        if limit <= 0:
            return []
        query = (
            sa.select(AutoExitOrderRow)
            .where(AutoExitOrderRow.state.in_(_OPEN_STATE_VALUES))
            .order_by(
                AutoExitOrderRow.created_at.asc().nulls_first(),
                AutoExitOrderRow.exit_order_id.asc(),
            )
            .limit(limit)
        )
        if account_id is not None:
            query = query.where(AutoExitOrderRow.account_id == account_id)
        rows = (await self._session.execute(query)).scalars().all()
        orders = [_row_to_order(row) for row in rows]
        return [order for order in orders if order is not None]

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
