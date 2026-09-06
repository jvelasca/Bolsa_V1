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
"""

from __future__ import annotations

import dataclasses
from typing import Any, Protocol

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    LiveOrderStatus,
    build_live_order,
    can_transition_live_order,
    transition_live_order,
)

# Venues bajo las que el cableado puede escribir rastro LIVE.
_LIVE_MACHINE_BRIDGED_VENUES: frozenset[str] = frozenset({"LIVE"})

# fill_status/status del adapter que SÍ dejan rastro in-flight persistible.
_MACHINE_TRACKED_SUBJECT_STATUSES: frozenset[str] = frozenset(
    {"submitted", "unknown"}
)


class LiveOrderStore(Protocol):
    """get/put/delete por order_id. Durabilidad = implementación."""

    async def get(self, order_id: str) -> LiveOrder | None: ...

    async def put(self, order: LiveOrder) -> None: ...

    async def delete(self, order_id: str) -> None: ...


class InMemoryLiveOrderStore:
    """Store de proceso (retry mismo worker; no sobrevive al PID).

    Sled PG para la máquina (V2.12) que abra UNKNOWN recovery; hoy basta para
    cablear y exponer el rastro en el propio Confirm request/response.
    """

    def __init__(self) -> None:
        self._by_order: dict[str, LiveOrder] = {}

    async def get(self, order_id: str) -> LiveOrder | None:
        key = (order_id or "").strip()
        if not key:
            return None
        return self._by_order.get(key)

    async def put(self, order: LiveOrder) -> None:
        key = (order.order_id or "").strip()
        if not key:
            return
        self._by_order[key] = order

    async def delete(self, order_id: str) -> None:
        key = (order_id or "").strip()
        if not key:
            return
        self._by_order.pop(key, None)


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
