"""AUTO-1 — store durable de reservas de cartera (``portfolio_reservations``).

Puente entre el motor **puro** de reservas (``bolsa_analytics.cognitive.portfolio_reservation``)
y su espejo en PostgreSQL (migración ``042_portfolio_reservations``). El modelo puro es el
dueño de toda la aritmética (dimensiones, escalado por liberación parcial, ``measurement``);
este módulo **no recalcula nada**: persiste y recupera el estado que el libro ya decidió.

Por qué existe un store y no basta el ledger del tick:

* el ``ReservationLedger`` vive **dentro** de ``plan_v2_tick`` y muere al volver de la
  función; tras un crash/reinicio nadie sabe qué quedó comprometido;
* la autoridad de ``reserved_cash``/``pending_risk`` entre ticks debe ser la reserva
  explícita (identidad + dimensiones), no una reconstrucción desde ``execution_events``;
* ``execution_events`` sigue siendo la **reconciliación de arranque** (qué se materializó
  de verdad), no la fuente de la reserva.

Invariante que sostiene el contrato: **no existe aprobación sin reserva, y no existe
reserva sin liberación**. Por eso el store expone ``save`` (alta/actualización idempotente
por ``reservation_id``) y ``release`` (que reutiliza el libro puro para escalar y marcar la
liberación), y ninguna de las dos borra la fila: la reserva liberada **se conserva** con su
estado, su cantidad liberada y su motivo (historia auditable, no un ``DELETE``).

Convenciones del repo (patrón ``execution_event``/``sim_durable_store``): imports de fila
**perezosos** por método, ``ON CONFLICT`` para idempotencia, y ``autocommit`` explícito
(``True`` por defecto: la reserva debe ser durable antes de emitir la orden; ``False`` cede
el commit a la unidad-de-trabajo del llamante).

La lectura declara su suelo: ``list_live``/``list_all`` devuelven como máximo ``limit``
filas y el llamante que reciba exactamente ``limit`` **no** puede afirmar que vio todo el
libro (fail-closed: "no pude leerlo todo" ≠ "no hay más").
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    RESERVATION_RELEASED_BY_CANCEL,
    PortfolioReservation,
    ReservationLedger,
    ReservationStatus,
    build_reservation,
    coerce_reservation_status,
    coerce_trading_cost,
    normalize_side,
)

__all__ = [
    "InMemoryReservationStore",
    "PostgresReservationStore",
    "ReservationStore",
]

# Columnas de la reserva que el ``save`` escribe. Es la lista única que comparten el
# insert y el ``ON CONFLICT DO UPDATE`` (una sola fuente de verdad del mapeo).
_WRITABLE_COLUMNS: tuple[str, ...] = (
    "account_id",
    "tick_id",
    "instrument_id",
    "sector",
    "strategy_version_id",
    "side",
    "quantity",
    "entry",
    "stop",
    "reserved_cash",
    "reserved_risk",
    "asset_exposure",
    "sector_exposure",
    "correlation",
    "strategy_capacity",
    "liquidity_capacity",
    "cost",
    "status",
    "created_at",
    "released_at",
    "release_reason",
    "released_qty",
    "remaining_qty",
    "lease_generation",
    "exit_order_id",
)


class ReservationStore(Protocol):
    """Persistencia de reservas (Protocol: in-memory para tests, PostgreSQL en producción)."""

    async def save(self, reservation: PortfolioReservation) -> bool:
        """Alta o actualización idempotente por ``reservation_id``.

        Devuelve ``True`` si la fila se **insertó** y ``False`` si ya existía y se
        actualizó. La idempotencia importa: un tick re-ejecutado (replay, reintento tras
        fallo de red) no puede duplicar el compromiso.
        """
        ...

    async def get(self, reservation_id: str) -> PortfolioReservation | None:
        """La reserva con esa identidad, o ``None`` (desconocida ≠ liberada)."""
        ...

    async def list_live(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        """Reservas vivas (``status='OPEN'`` con cantidad > 0) de la cuenta.

        Son la **autoridad** de ``reserved_cash``/``pending_risk`` entre ticks.
        ``account_id=None`` ⇒ sin filtro de cuenta (el llamante que no pudo determinarla
        prefiere ver todo antes que asumir que no hay nada: fail-closed).
        """
        ...

    async def list_all(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        """Todas las reservas de la cuenta (vivas y liberadas), para auditoría/replay."""
        ...

    async def release(
        self,
        reservation_id: str,
        *,
        status: ReservationStatus = RESERVATION_RELEASED_BY_CANCEL,
        reason: str | None = None,
        released_qty: Any = None,
        at: str | None = None,
    ) -> PortfolioReservation | None:
        """Libera (total o parcialmente) una reserva viva y persiste el resultado.

        ``None`` si no había nada que liberar (reserva desconocida o ya liberada): la
        liberación es **idempotente**, nunca un doble liberado.
        """
        ...

    async def commit(self) -> None:
        """Hace durable lo escrito (no-op en el store in-memory)."""
        ...


def _as_float(value: Any) -> float | None:
    """``Decimal``/``str``/``int`` → ``float``; ``None`` si no es finito.

    El modelo puro trabaja en ``float``; PostgreSQL devuelve ``Decimal`` en ``Numeric``.
    Sin esta coerción, la aritmética del libro mezclaría tipos y el redondeo de la casa
    dejaría de ser determinista.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _to_iso(value: Any) -> str | None:
    """Instante de la fila → ``str`` ISO (el contrato del modelo puro es ``str``)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value.isoformat())
    except AttributeError:
        return str(value)


def _to_instant(value: Any) -> datetime | None:
    """ISO del modelo puro → ``datetime`` (la columna es ``DateTime(timezone=True)``).

    El modelo puro trabaja con ``str`` (sin reloj, determinista) y la columna es
    ``timestamptz``: la conversión se hace AQUÍ, explícita, en vez de confiar en que el
    driver parsee el texto. Una fecha ilegible queda ``None`` (sin fecha) — nunca una
    fecha inventada, y ``created_at`` NULL significa "no se puede ventanear" (el
    reconciliador conserva la reserva en lugar de liberarla por un hueco).
    """
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


def _row_to_reservation(row: Any) -> PortfolioReservation:
    """Fila ``portfolio_reservations`` → ``PortfolioReservation`` (una sola verdad).

    Se reconstruye con ``build_reservation`` (no con el constructor directo) para que la
    normalización sea la misma que en el alta, y se sobrescribe el ciclo de vida con lo
    persistido: estado, cantidades liberada/viva, motivo e instantes.
    """
    reservation = build_reservation(
        reservation_id=row.reservation_id,
        account_id=row.account_id or "",
        tick_id=row.tick_id or "",
        instrument_id=row.instrument_id or "",
        side=normalize_side(row.side),
        sector=row.sector,
        strategy_version_id=row.strategy_version_id,
        quantity=_as_float(row.quantity),
        entry=_as_float(row.entry),
        stop=_as_float(row.stop),
        reserved_cash=_as_float(row.reserved_cash),
        reserved_risk=_as_float(row.reserved_risk),
        asset_exposure=_as_float(row.asset_exposure),
        sector_exposure=_as_float(row.sector_exposure),
        correlation=_as_float(row.correlation),
        strategy_capacity=_as_float(row.strategy_capacity),
        liquidity_capacity=_as_float(row.liquidity_capacity),
        cost=coerce_trading_cost(row.cost),
        lease_generation=int(row.lease_generation or 0),
    )
    quantity = _as_float(row.quantity)
    return PortfolioReservation(
        reservation_id=reservation.reservation_id,
        account_id=reservation.account_id,
        tick_id=reservation.tick_id,
        instrument_id=reservation.instrument_id,
        side=reservation.side,
        sector=reservation.sector,
        strategy_version_id=reservation.strategy_version_id,
        quantity=quantity if quantity is not None else reservation.quantity,
        entry=reservation.entry,
        stop=reservation.stop,
        reserved_cash=reservation.reserved_cash,
        reserved_risk=reservation.reserved_risk,
        asset_exposure=reservation.asset_exposure,
        sector_exposure=reservation.sector_exposure,
        correlation=reservation.correlation,
        strategy_capacity=reservation.strategy_capacity,
        liquidity_capacity=reservation.liquidity_capacity,
        cost=reservation.cost,
        status=coerce_reservation_status(row.status) or RESERVATION_OPEN,
        created_at=_to_iso(row.created_at),
        released_at=_to_iso(row.released_at),
        release_reason=row.release_reason,
        released_qty=_as_float(row.released_qty) or 0.0,
        remaining_qty=_as_float(row.remaining_qty) or 0.0,
        lease_generation=int(row.lease_generation or 0),
        exit_order_id=getattr(row, "exit_order_id", None),
    )


def _reservation_values(reservation: PortfolioReservation) -> dict[str, Any]:
    """Valores de escritura de una reserva (mismo mapeo para insert y update)."""
    return {
        "reservation_id": reservation.reservation_id,
        "account_id": reservation.account_id or None,
        "tick_id": reservation.tick_id or None,
        "instrument_id": reservation.instrument_id or None,
        "sector": reservation.sector,
        "strategy_version_id": reservation.strategy_version_id,
        "side": reservation.side or None,
        "quantity": reservation.quantity,
        "entry": reservation.entry,
        "stop": reservation.stop,
        "reserved_cash": reservation.reserved_cash,
        "reserved_risk": reservation.reserved_risk,
        "asset_exposure": reservation.asset_exposure,
        "sector_exposure": reservation.sector_exposure,
        "correlation": reservation.correlation,
        "strategy_capacity": reservation.strategy_capacity,
        "liquidity_capacity": reservation.liquidity_capacity,
        "cost": None if reservation.cost is None else reservation.cost.to_dict(),
        "status": reservation.status,
        "created_at": _to_instant(reservation.created_at),
        "released_at": _to_instant(reservation.released_at),
        "release_reason": reservation.release_reason,
        "released_qty": reservation.released_qty,
        "remaining_qty": reservation.remaining_qty,
        "lease_generation": reservation.lease_generation,
        "exit_order_id": reservation.exit_order_id,
    }


async def _commit_if(session: Any, autocommit: bool) -> None:
    """Commit condicional (patrón ``sim_durable_store._commit_if``).

    ``autocommit=True`` (default): la reserva debe ser durable **antes** de que el worker
    emita la orden, para que un crash justo después no pierda el compromiso.
    ``autocommit=False``: el llamante (unidad-de-trabajo) controla el commit y puede
    componer la reserva y su ejecución en una sola transacción.
    """
    if autocommit:
        await session.commit()


def _order_key(reservation: PortfolioReservation) -> tuple[str, str]:
    """Orden determinista del libro: por instante de alta y, a igualdad, por identidad."""
    return (reservation.created_at or "", reservation.reservation_id)


class InMemoryReservationStore:
    """Store in-memory con la MISMA semántica que el PG (tests y camino hermético)."""

    def __init__(self, seed: Iterable[PortfolioReservation] = ()) -> None:
        self._rows: dict[str, PortfolioReservation] = {
            reservation.reservation_id: reservation for reservation in seed
        }

    def __len__(self) -> int:
        return len(self._rows)

    async def save(self, reservation: PortfolioReservation) -> bool:
        """Espeja ``ON CONFLICT``: inserta si es nueva, actualiza si ya estaba."""
        key = reservation.reservation_id
        inserted = key not in self._rows
        self._rows[key] = reservation
        return inserted

    async def get(self, reservation_id: str) -> PortfolioReservation | None:
        return self._rows.get(str(reservation_id or "").strip())

    async def list_live(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        if limit <= 0:
            return []
        rows = [
            row
            for row in self._rows.values()
            if row.is_live and (account_id is None or row.account_id == account_id)
        ]
        rows.sort(key=_order_key)
        return rows[:limit]

    async def list_all(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        if limit <= 0:
            return []
        rows = [
            row
            for row in self._rows.values()
            if account_id is None or row.account_id == account_id
        ]
        rows.sort(key=_order_key)
        return rows[:limit]

    async def release(
        self,
        reservation_id: str,
        *,
        status: ReservationStatus = RESERVATION_RELEASED_BY_CANCEL,
        reason: str | None = None,
        released_qty: Any = None,
        at: str | None = None,
    ) -> PortfolioReservation | None:
        return await _release(self, reservation_id, status, reason, released_qty, at)

    async def commit(self) -> None:
        """No-op: el store in-memory ya es visible (espeja el contrato del PG)."""
        return None


class PostgresReservationStore:
    """``portfolio_reservations`` en PostgreSQL (idempotente por ``reservation_id``).

    ``save`` es un ``INSERT ... ON CONFLICT (reservation_id) DO UPDATE`` con ``RETURNING``:
    una sola ida y vuelta, sin lectura previa y sin ventana de carrera entre dos ticks.
    """

    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def save(self, reservation: PortfolioReservation) -> bool:
        """Alta idempotente; ``False`` + ``UPDATE`` si la identidad ya existía.

        Se resuelve en dos pasos (``ON CONFLICT DO NOTHING`` + ``UPDATE`` condicional) en
        vez de un ``ON CONFLICT DO UPDATE`` porque el contrato necesita saber **si insertó
        o actualizó**: un tick re-ejecutado (replay, reintento de red) debe poder
        distinguir "ya estaba" de "acabo de comprometer capital". El update existe para el
        camino de liberación, que persiste el estado nuevo que calculó el libro puro.
        """
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

        values = _reservation_values(reservation)
        insert_statement = (
            pg_insert(PortfolioReservationRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["reservation_id"])
            .returning(PortfolioReservationRow.reservation_id)
        )
        result = await self._session.execute(insert_statement)
        inserted = result.scalars().first() is not None
        if not inserted:
            update_values = {name: values[name] for name in _WRITABLE_COLUMNS}
            await self._session.execute(
                sa.update(PortfolioReservationRow)
                .where(
                    PortfolioReservationRow.reservation_id == reservation.reservation_id
                )
                .values(**update_values)
            )
        await _commit_if(self._session, self._autocommit)
        return inserted

    async def get(self, reservation_id: str) -> PortfolioReservation | None:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

        row = (
            await self._session.execute(
                sa.select(PortfolioReservationRow).where(
                    PortfolioReservationRow.reservation_id == str(reservation_id or "").strip()
                )
            )
        ).scalar_one_or_none()
        return None if row is None else _row_to_reservation(row)

    async def list_live(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        """Reservas vivas de la cuenta (autoridad de ``reserved_cash``/``pending_risk``).

        ``remaining_qty > 0`` es el criterio duro: una fila ``OPEN`` con cantidad 0 no
        compromete nada (espeja ``PortfolioReservation.is_live``).
        """
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

        if limit <= 0:
            return []
        query = (
            sa.select(PortfolioReservationRow)
            .where(PortfolioReservationRow.status == RESERVATION_OPEN)
            .where(PortfolioReservationRow.remaining_qty > 0)
            .order_by(
                PortfolioReservationRow.created_at.asc().nulls_first(),
                PortfolioReservationRow.reservation_id.asc(),
            )
            .limit(limit)
        )
        if account_id is not None:
            query = query.where(PortfolioReservationRow.account_id == account_id)
        rows = (await self._session.execute(query)).scalars().all()
        return [_row_to_reservation(row) for row in rows]

    async def list_all(
        self, account_id: str | None, *, limit: int = 500
    ) -> list[PortfolioReservation]:
        import sqlalchemy as sa

        from bolsa_infrastructure.database.models.tables import PortfolioReservationRow

        if limit <= 0:
            return []
        query = (
            sa.select(PortfolioReservationRow)
            .order_by(
                PortfolioReservationRow.created_at.asc().nulls_first(),
                PortfolioReservationRow.reservation_id.asc(),
            )
            .limit(limit)
        )
        if account_id is not None:
            query = query.where(PortfolioReservationRow.account_id == account_id)
        rows = (await self._session.execute(query)).scalars().all()
        return [_row_to_reservation(row) for row in rows]

    async def release(
        self,
        reservation_id: str,
        *,
        status: ReservationStatus = RESERVATION_RELEASED_BY_CANCEL,
        reason: str | None = None,
        released_qty: Any = None,
        at: str | None = None,
    ) -> PortfolioReservation | None:
        return await _release(self, reservation_id, status, reason, released_qty, at)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


async def _release(
    store: Any,
    reservation_id: str,
    status: ReservationStatus,
    reason: str | None,
    released_qty: Any,
    at: str | None,
) -> PortfolioReservation | None:
    """Libera reutilizando el **libro puro** (una sola aritmética, no dos).

    El escalado de dimensiones por liberación parcial, el estado resultante y la
    cantidad viva los decide ``ReservationLedger.release`` — el mismo código que corre
    dentro del tick. El store solo lee, deja que el libro calcule y persiste el
    resultado. Idempotente: si la reserva no está viva, no toca nada y devuelve ``None``.
    """
    key = str(reservation_id or "").strip()
    current = await store.get(key)
    if current is None or not current.is_live:
        return None
    book = ReservationLedger(account_id=current.account_id, tick_id=current.tick_id)
    book.reserve(current)
    updated = book.release(
        key,
        status=status,
        reason=reason,
        released_qty=released_qty,
        at=at,
    )
    if updated is None:
        return None
    await store.save(updated)
    return updated
