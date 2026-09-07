"""LiveOrderStore — puerto durable del dominio XL-3 (ADR future / RL-3).

Cableado Confirm (persist only · sin recovery en esta tanda):

* Solo se persiste una máquina ``LiveOrder`` cuando el adapter LIVE confirma
  ``submitted`` (bridge lo tiene, sin ack de fill) o ``unknown`` (timeout /
  perdida de respuesta). En esos dos estados el rastro es real y NO re-POST.
* ``PAPER`` no tiene máquina LIVE. ``not_wired``/``rejected`` (incl. sandbox
  VIRTUAL ``live_virtual_sandbox``) no dejan rastro de cash; ``executed`` es el
  slice XL-2 cerrado → a ledger, no machine in-flight. → NINGUNO persiste.
* ``query_broker`` (movernos fuera de UNKNOWN) queda PARKED en Confirm; solo
  la UI red / tests lo harán. ≠ thaw · ≠ PAPER_D_EXECUTE · ≠ autoriza re-POST.

V2.12 (scope-out "list_open_orders + cancel_order"): este store es **durable y
dominio-only**. ``cancel_order`` NO hace round-trip de broker real: persiste una
decisión autorizada de cancelación (el contrato XTB cancel sigue PARKED). Solo un
llamador que ya puede acreditar cancelación broker-side (o razón interna
autoritativa) debe invocarlo; aquí nunca se fabrica un resultado de broker
(fail-closed, misma boundary honesta que el UNKNOWN recovery).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_analytics.cognitive.live_order import (
    NON_TERMINAL_LIVE_STATUSES,
    LiveOrder,
    LiveOrderStatus,
    build_live_order,
    can_transition_live_order,
    transition_live_order,
)
from bolsa_infrastructure.database.models.tables import LiveOrderRow
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Venues bajo las que el cableado puede escribir rastro LIVE.
_LIVE_MACHINE_BRIDGED_VENUES: frozenset[str] = frozenset({"LIVE"})

# fill_status/status del adapter que SÍ dejan rastro in-flight persistible.
_MACHINE_TRACKED_SUBJECT_STATUSES: frozenset[str] = frozenset({"submitted", "unknown"})


@dataclass(frozen=True, slots=True)
class CancelDocumentation:
    """Rastro durable de una decisión de cancelación (honest-cancel V2.13).

    Distingue si una cancelación es sólo una DECISIÓN LOCAL autorizada (quién/
    cuándo/por qué pidió) de una confirmación real del broker (que hoy, PARKED,
    quedaría está en ``broker_confirmed_at`` = None). Una capa superior debe usar
    ``broker_confirmed`` para NO presentar CANCELLED como confirmación del venue
    cuando no la hay.
    """

    order_id: str
    requested_by: str | None = None
    reason: str | None = None
    requested_at: datetime | None = None
    broker_confirmed_at: datetime | None = None

    @property
    def broker_confirmed(self) -> bool:
        """¿Ya confirmó el broker (venue) que la orden cayó cancelada?"""
        return self.broker_confirmed_at is not None


class LiveOrderStore(Protocol):
    """get/put/delete por order_id. Durabilidad = implementación."""

    async def get(self, order_id: str) -> LiveOrder | None: ...

    async def put(
        self,
        order: LiveOrder,
        *,
        account_id: str | None = None,
    ) -> None: ...

    async def delete(self, order_id: str) -> None: ...

    async def list_unknown(self, *, limit: int = 50) -> list[LiveOrder]: ...

    async def claim_unknown_batch(
        self,
        *,
        limit: int = 50,
        worker_id: str,
        stale_after_seconds: int = 60,
    ) -> list[LiveOrder]:
        """Reclama filas UNKNOWN para un worker (lease/row-lock cross-PID).

        Caso técnico: un worker reclama una fila UNKNOWN y otro NO la re-procesa
        hasta expirar la ventana ``stale_after_seconds`` (crash/restart). Nunca
        es un estado de negocio: se deriva del filtro ``status='UNKNOWN'``.
        """

    async def list_open_orders(self, *, limit: int = 50) -> list[LiveOrder]: ...

    async def cancel_order(
        self,
        order_id: str,
        *,
        reason: str | None = None,
        by: str | None = None,
    ) -> LiveOrder | None: ...

    async def get_cancel_meta(
        self, order_id: str
    ) -> CancelDocumentation | None: ...

    async def set_broker_cancel_confirmed(
        self,
        order_id: str,
        *,
        when: datetime | None = None,
    ) -> CancelDocumentation | None:
        """PARKED: registrar confirmación broker-side de la cancelación.

        Se reserva (sin uso) hasta que exista un round-trip real de canc; hoy
        ninguna capa llama este método, así nunca se fabrica confirmación.
        """


class InMemoryLiveOrderStore:
    """Store de proceso (retry mismo worker; no sobrevive al PID).

    Sled PG para la máquina (V2.12) que abra UNKNOWN recovery; hoy basta para
    cablear y exponer el rastro en el propio Confirm request/response.
    """

    def __init__(self) -> None:
        self._by_order: dict[str, LiveOrder] = {}
        self._claims: dict[str, tuple[str, datetime]] = {}
        self._cancel_docs: dict[str, CancelDocumentation] = {}

    async def get(self, order_id: str) -> LiveOrder | None:
        key = (order_id or "").strip()
        if not key:
            return None
        return self._by_order.get(key)

    async def put(
        self,
        order: LiveOrder,
        *,
        account_id: str | None = None,
    ) -> None:
        _ = account_id  # InMemory no persiste cuenta en la máquina.
        key = (order.order_id or "").strip()
        if not key:
            return
        self._by_order[key] = order

    async def delete(self, order_id: str) -> None:
        key = (order_id or "").strip()
        if not key:
            return
        self._by_order.pop(key, None)

    async def list_unknown(self, *, limit: int = 50) -> list[LiveOrder]:
        cap = max(1, int(limit))
        return [order for order in self._by_order.values() if order.status == "UNKNOWN"][:cap]

    async def claim_unknown_batch(
        self,
        *,
        limit: int = 50,
        worker_id: str,
        stale_after_seconds: int = 60,
    ) -> list[LiveOrder]:
        """InMemory: claim cross-PID simulado (diccionario por proceso).

        Un mismo store InMemory es monoproceso; el claim modela la exclusión
        entre llamadas dentro de "otro worker" lógico respetando la misma
        semántica stale del caso PG (no re-procesar un claim fresco de otro).
        """
        from datetime import timedelta

        cap = max(1, int(limit))
        now = _utcnow()
        stale_before = now - timedelta(seconds=max(1, int(stale_after_seconds)))
        claimed: list[LiveOrder] = []
        for order in sorted(
            (o for o in self._by_order.values() if o.status == "UNKNOWN"),
            key=lambda o: o.order_id,
        ):
            if len(claimed) >= cap:
                break
            owner, at = self._claims.get(order.order_id, (None, None))
            # Un claim fresco (por quien sea: este u otro worker) excluye la fila
            # hasta que expire; así no se hila fino en bucle un UNKNOWN que no
            # se resuelve y un segundo worker no duplica el proceso en caliente.
            if owner is not None and at is not None and at > stale_before:
                continue
            self._claims[order.order_id] = (worker_id, now)
            claimed.append(order)
        return claimed

    async def release_claim(self, order_id: str) -> None:
        key = (order_id or "").strip()
        if key:
            self._claims.pop(key, None)

    async def list_open_orders(self, *, limit: int = 50) -> list[LiveOrder]:
        """Órdenes **no terminales** (excluye FILLED/REJECTED/CANCELLED).

        "open" = la orden sigue viva / en curso / en riesgo y puede evolucionar
        (incluye UNKNOWN: en vuelo no resuelto, aún puede cancelarse vía el
        grafo). Filtra por ``NON_TERMINAL_LIVE_STATUSES`` (derivado de
        ``_TERMINAL`` del dominio, sin strings mágicos).
        """
        cap = max(1, int(limit))
        return [
            order
            for order in self._by_order.values()
            if order.status in NON_TERMINAL_LIVE_STATUSES
        ][:cap]

    async def cancel_order(
        self,
        order_id: str,
        *,
        reason: str | None = None,
        by: str | None = None,
    ) -> LiveOrder | None:
        """Persiste una cancelación (dominio → CANCELLED) si el grafo lo permite.

        honest-boundary: este método NO consulta/interactúa con el broker real.
        Solo persiste la decisión autorizada por el llamador; debe invocarse
        únicamente cuando ya existe una prueba de cancelación broker-side o una
        razón interna autoritativa equivalente. Un round-trip real de cancel es
        PARKED (no hay contrato XTB cancel).

        La durabilidad de quién/cuándo/por qué queda en ``get_cancel_meta``; un
        CANCELLED sin ``broker_confirmed`` es una decisión local, NO un ack del
        venue (PARKED: broker_cancel_confirmed_at nunca se setea hoy).
        """
        key = (order_id or "").strip()
        if not key:
            return None
        current = await self.get(key)
        if current is None:
            return None
        if not can_transition_live_order(current.status, "CANCELLED"):
            # Terminal u orden no cancelable → no-op idempotente, jamás un falso éxito.
            return current
        cancelled = transition_live_order(current, "CANCELLED")
        await self.put(cancelled, account_id=current.account_id)
        self._cancel_docs[key] = CancelDocumentation(
            order_id=key,
            requested_by=by or "operator",
            reason=reason,
            requested_at=_utcnow(),
            broker_confirmed_at=None,
        )
        return cancelled

    async def get_cancel_meta(self, order_id: str) -> CancelDocumentation | None:
        key = (order_id or "").strip()
        if not key:
            return None
        return self._cancel_docs.get(key)

    async def set_broker_cancel_confirmed(
        self,
        order_id: str,
        *,
        when: datetime | None = None,
    ) -> CancelDocumentation | None:
        key = (order_id or "").strip()
        current = self._cancel_docs.get(key)
        if current is None:
            return None
        updated = CancelDocumentation(
            order_id=key,
            requested_by=current.requested_by,
            reason=current.reason,
            requested_at=current.requested_at,
            broker_confirmed_at=when if when is not None else _utcnow(),
        )
        self._cancel_docs[key] = updated
        return updated


_PROCESS_STORE = InMemoryLiveOrderStore()


def process_live_order_store() -> InMemoryLiveOrderStore:
    """Singleton de proceso (runtime sin PG). Tests pueden inyectar otro."""
    return _PROCESS_STORE


def live_order_persistable(*, pb: Any) -> bool:
    """¿Este resultado de adapter debe abrir/mantener rastro LiveOrder?

    Solo venue LIVE y status submitted|unknown. Todo lo demás (PAPER, sandbox
    VIRTUAL not_wired, rejected, executed→XL-2) NO toca la máquina.
    """
    venue = (getattr(pb, "venue", None) or "").strip().upper()
    status = (getattr(pb, "status", None) or "").strip().lower()
    if venue not in _LIVE_MACHINE_BRIDGED_VENUES:
        return False
    return status in _MACHINE_TRACKED_SUBJECT_STATUSES


def live_status_of_adapter_status(status: str) -> LiveOrderStatus:
    """Mapea el fill/status del puerto al estado maquina XL-3 (PARKED conserva)."""
    s = (status or "").strip().lower()
    if s in {"submitted", "submitting"}:
        return "SUBMITTED"
    if s == "unknown":
        return "UNKNOWN"
    # executed/not_wired/rejected no llegan aquí (guard live_order_persistable); por
    # seguridad si algo invoca mal → UNKNOWN (fail-closed, nunca un falso FILLED).
    return "UNKNOWN"


def _bind_venue(order: LiveOrder, venue_order_id: Any) -> LiveOrder:
    """Devuelve el LiveOrder con venue_order_id poblado (replace, no transición)."""
    vid = venue_order_id if venue_order_id not in (None, "") else order.venue_order_id
    if vid == order.venue_order_id:
        return order
    return dataclasses.replace(order, venue_order_id=vid)


def live_order_from_submit_result(
    *,
    order_id: str,
    instrument_id: str,
    side: str,
    quantity: float,
    intent_id: str | None,
    pb: Any,
    existing: LiveOrder | None = None,
) -> LiveOrder | None:
    """Construye/avanza el LiveOrder a partir de un pb persistible (o None).

    ``existing`` si el orden ya tenía rastro en la máquina (retry same worker).
    Fail-closed: nunca inventa un FILLED/PARTIAL; solo refleja lo que el puerto
    reporta (`submitted`→SUBMITTED, `unknown`→UNKNOWN).
    """
    status_text = (getattr(pb, "status", None) or "").strip().lower()
    venue_order_id = getattr(pb, "venue_order_id", None)
    if not live_order_persistable(pb=pb):
        return None

    target: LiveOrderStatus = live_status_of_adapter_status(status_text)

    if existing is not None:
        if target == "UNKNOWN":
            # 1) avanzo a UNKNOWN solo desde estados abiertos (no terminales) legales.
            if can_transition_live_order(existing.status, "UNKNOWN"):
                try:
                    advanced = transition_live_order(existing, "UNKNOWN")
                    return _bind_venue(advanced, venue_order_id)
                except Exception:  # noqa: BLE001 — conservar si topa el veto
                    return existing
            return existing
        if target == "SUBMITTED":
            # 2) re-submit idempotente de algo ya bindeado: no dupliques, solo
            #    completa el venue_order_id si el pb lo aporta de nuevo.
            if existing.status in {"SUBMITTED", "SUBMITTING", "WORKING"}:
                return _bind_venue(existing, venue_order_id)
            # 3) existía con otro estado (p.ej. no esperado) → no regresar jamás
            #    a SUBMITTED desde un punto avanzado/cerrado.
            return existing
        return existing

    # Rastro nuevo tras un submit real. Bind del venue id si el bridge lo devolvió.
    built = build_live_order(
        order_id=order_id,
        instrument_id=instrument_id,
        side=str(side).lower() if str(side).lower() in {"buy", "sell"} else "buy",  # type: ignore[arg-type]
        quantity=float(quantity),
        intent_id=intent_id,
        status=target,
    )
    return _bind_venue(built, venue_order_id)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def live_order_to_row_fields(
    order: LiveOrder,
    *,
    account_id: str,
    created_at: datetime,
    updated_at: datetime,
) -> LiveOrderRow:
    """Mapea el dominio a fila física (replica las columnas 1:1)."""
    return LiveOrderRow(
        order_id=order.order_id,
        account_id=account_id,
        status=order.status,
        venue=order.venue,
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=order.quantity,
        filled_quantity=order.filled_quantity,
        remaining_quantity=order.remaining_quantity,
        venue_order_id=order.venue_order_id,
        intent_id=order.intent_id,
        financial_apply_count=order.financial_apply_count,
        created_at=created_at,
        updated_at=updated_at,
    )


def live_order_from_row(row: LiveOrderRow) -> LiveOrder:
    """Mapea fila física a dominio LiveOrder (confiar en invariantes de BD)."""
    return LiveOrder(
        order_id=row.order_id,
        status=row.status,  # type: ignore[arg-type]
        venue=row.venue,  # type: ignore[arg-type]
        instrument_id=row.instrument_id,
        side=row.side,  # type: ignore[arg-type]
        quantity=float(row.quantity),
        filled_quantity=float(row.filled_quantity),
        remaining_quantity=float(row.remaining_quantity),
        venue_order_id=row.venue_order_id,
        intent_id=row.intent_id,
        financial_apply_count=int(row.financial_apply_count),
        account_id=row.account_id,
    )


class PostgresLiveOrderStore:
    """Persistencia física cross-PID de la máquina XL-3.

    ``put``/``delete`` hacen commit (escribe/avanza el rastro durable). El worker
    de recovery relee las filas ``UNKNOWN`` y las resuelve vía query_broker
    (NUNCA re-POST), sin depender del worker/request que escribió la fila.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, order_id: str) -> LiveOrder | None:
        key = (order_id or "").strip()
        if not key:
            return None
        stmt = select(LiveOrderRow).where(LiveOrderRow.order_id == key)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return live_order_from_row(row) if row is not None else None

    async def put(
        self,
        order: LiveOrder,
        *,
        account_id: str | None = None,
    ) -> None:
        key = (order.order_id or "").strip()
        if not key:
            return
        now = _utcnow()
        # Upsert atómico a nivel de base de datos: elimina la ventana TOCTOU
        # "get() → decide → INSERT/UPDATE" del clásico read-modify-write. Dos
        # workers cross-PID pueden correr put() para el mismo order_id casi a la
        # vez; ON CONFLICT DO UPDATE serializa la escritura en el PK en vez de
        # que ambos vean "no existe" y peleen por un INSERT (IntegrityError) con
        # pérdida silenciosa de la última actualización.
        resolved_account = account_id or order.account_id or "live"
        row_fields = live_order_to_row_fields(
            order,
            account_id=resolved_account,
            created_at=now,
            updated_at=now,
        )
        values = {
            col.name: getattr(row_fields, col.name)
            for col in LiveOrderRow.__table__.columns
        }
        update: dict[str, object] = {
            "status": order.status,
            "venue": order.venue,
            "instrument_id": order.instrument_id,
            "side": order.side,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": order.remaining_quantity,
            "intent_id": order.intent_id,
            "financial_apply_count": order.financial_apply_count,
            "account_id": resolved_account,
            "updated_at": now,
        }
        # venue_order_id sólo se machaca cuando el llamador aporta uno (paridad
        # con el update previo: `if order.venue_order_id is not None`); si el
        # domain no lo conoce aún, se conserva el bind previo de la BD.
        if order.venue_order_id is not None:
            update["venue_order_id"] = order.venue_order_id
        stmt = (
            pg_insert(LiveOrderRow)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[LiveOrderRow.order_id],
                set_=update,
            )
        )
        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise

    async def delete(self, order_id: str) -> None:
        key = (order_id or "").strip()
        if not key:
            return
        row = await self._load_row(key)
        if row is None:
            return
        await self._session.delete(row)
        await self._session.commit()

    async def list_unknown(self, *, limit: int = 50) -> list[LiveOrder]:
        cap = max(1, int(limit))
        stmt = (
            select(LiveOrderRow)
            .where(LiveOrderRow.status == "UNKNOWN")
            .order_by(LiveOrderRow.updated_at.asc())
            .limit(cap)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [live_order_from_row(r) for r in rows]

    async def claim_unknown_batch(
        self,
        *,
        limit: int = 50,
        worker_id: str,
        stale_after_seconds: int = 60,
    ) -> list[LiveOrder]:
        """Reclama filas UNKNOWN con row-lock (SKIP LOCKED) + lease de worker.

        Dos workers que drenen la misma orden UNKNOWN: el primero hace
        ``SELECT ... FOR UPDATE`` sobre la fila y la marca con su
        ``recovery_worker_id/claimed_at``; el segundo ve la fila (a) lockeada y
        la skipea, o (b) reclamada en fresco y la excluye. Tras ``stale
        (crash/restart)`` otro worker puede reclamarla (reclaim con lease).
        Marcas técnicas; NUNCA alteran el estado de negocio.
        """
        from datetime import timedelta

        cap = max(1, int(limit))
        now = _utcnow()
        stale_before = now - timedelta(seconds=max(1, int(stale_after_seconds)))
        stmt = (
            select(LiveOrderRow)
            .where(LiveOrderRow.status == "UNKNOWN")
            .where(
                or_(
                    LiveOrderRow.recovery_claimed_at.is_(None),
                    LiveOrderRow.recovery_claimed_at <= stale_before,
                )
            )
            .order_by(LiveOrderRow.updated_at.asc())
            .limit(cap)
            .with_for_update(skip_locked=True)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        claimed: list[LiveOrder] = []
        for row in rows:
            row.recovery_worker_id = worker_id
            row.recovery_claimed_at = now
            row.updated_at = now
            claimed.append(live_order_from_row(row))
        if claimed:
            # flush (sin commit): el worker resuelve y la persiste en el mismo
            # tx/commit (put). El lock se libera cuando ese put commitee.
            await self._session.flush()
        return claimed

    async def release_claim(self, order_id: str) -> None:
        """Libera el lease de una fila UNKNOWN (reclaimable de inmediato)."""
        key = (order_id or "").strip()
        if not key:
            return
        row = await self._load_row(key)
        if row is None:
            return
        row.recovery_worker_id = None
        row.recovery_claimed_at = None
        row.updated_at = _utcnow()
        await self._session.flush()

    async def list_open_orders(self, *, limit: int = 50) -> list[LiveOrder]:
        """Órdenes **no terminales** (excluye FILLED/REJECTED/CANCELLED).

        "open" = orden viva / en curso / en riesgo (incluye UNKNOWN). Filtra por
        ``NON_TERMINAL_LIVE_STATUSES`` (derivado de ``_TERMINAL`` del dominio,
        sin strings mágicos), ordena por ``updated_at`` ascendente como
        ``list_unknown`` y limita el lote.
        """
        cap = max(1, int(limit))
        stmt = (
            select(LiveOrderRow)
            .where(LiveOrderRow.status.in_(sorted(NON_TERMINAL_LIVE_STATUSES)))
            .order_by(LiveOrderRow.updated_at.asc())
            .limit(cap)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [live_order_from_row(r) for r in rows]

    async def cancel_order(
        self,
        order_id: str,
        *,
        reason: str | None = None,
        by: str | None = None,
    ) -> LiveOrder | None:
        """Persiste una cancelación (dominio → CANCELLED) + docs si el grafo.

        honest-boundary: igual que en InMemory, NO consulta el broker real; solo
        persiste la decisión autorizada. Un round-trip real de cancel es PARKED.
        La cancelación queda como DECISIÓN LOCAL: las columnas
        ``cancel_requested_by/reason/requested_at`` se rellenan y
        ``broker_cancel_confirmed_at`` queda NULL (no se fabrica ack del broker).
        """
        key = (order_id or "").strip()
        if not key:
            return None
        current = await self.get(key)
        if current is None:
            return None
        if not can_transition_live_order(current.status, "CANCELLED"):
            return current
        cancelled = transition_live_order(current, "CANCELLED")
        now = _utcnow()
        account = current.account_id or "live"
        row_fields = live_order_to_row_fields(
            cancelled,
            account_id=account,
            created_at=now,
            updated_at=now,
        )
        values = {
            col.name: getattr(row_fields, col.name)
            for col in LiveOrderRow.__table__.columns
        }
        update: dict[str, object] = {
            "status": "CANCELLED",
            "venue": cancelled.venue,
            "instrument_id": cancelled.instrument_id,
            "side": cancelled.side,
            "quantity": cancelled.quantity,
            "filled_quantity": cancelled.filled_quantity,
            "remaining_quantity": cancelled.remaining_quantity,
            "intent_id": cancelled.intent_id,
            "financial_apply_count": cancelled.financial_apply_count,
            "account_id": account,
            "cancel_requested_by": by or "operator",
            "cancel_reason": reason,
            "cancel_requested_at": now,
            # broker_cancel_confirmed_at queda sin tocar (NULL) — no fabricamos
            # confirmación del venue. Se podría setear cuando el round-trip de
            # canc confirme realmente (reservado, PARKED).
            "updated_at": now,
        }
        if cancelled.venue_order_id is not None:
            update["venue_order_id"] = cancelled.venue_order_id
        stmt = (
            pg_insert(LiveOrderRow)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[LiveOrderRow.order_id],
                set_=update,
            )
        )
        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise
        return cancelled

    async def get_cancel_meta(self, order_id: str) -> CancelDocumentation | None:
        key = (order_id or "").strip()
        if not key:
            return None
        row = await self._load_row(key)
        if row is None:
            return None
        return CancelDocumentation(
            order_id=row.order_id,
            requested_by=row.cancel_requested_by,
            reason=row.cancel_reason,
            requested_at=row.cancel_requested_at,
            broker_confirmed_at=row.broker_cancel_confirmed_at,
        )

    async def set_broker_cancel_confirmed(
        self,
        order_id: str,
        *,
        when: datetime | None = None,
    ) -> CancelDocumentation | None:
        key = (order_id or "").strip()
        if not key:
            return None
        row = await self._load_row(key)
        if row is None:
            return None
        confirmed_at = when if when is not None else _utcnow()
        row.broker_cancel_confirmed_at = confirmed_at
        row.updated_at = _utcnow()
        await self._session.commit()
        return CancelDocumentation(
            order_id=row.order_id,
            requested_by=row.cancel_requested_by,
            reason=row.cancel_reason,
            requested_at=row.cancel_requested_at,
            broker_confirmed_at=confirmed_at,
        )

    async def _load_row(self, order_id: str) -> LiveOrderRow | None:
        key = (order_id or "").strip()
        if not key:
            return None
        stmt = select(LiveOrderRow).where(LiveOrderRow.order_id == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()
