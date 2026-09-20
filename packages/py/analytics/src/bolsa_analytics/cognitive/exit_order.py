"""ExitOrder — la identidad DURABLE de una orden de salida (AUTO-3 cierre V2.43.3).

El hueco que cierra este módulo (auditoría de ``v2.43.2-beta``, P0 nº2):

    identidad de salida  =  engine_id + contador LOCAL del proceso   ← no sobrevive a nada
    identidad de salida  =  exit_order_id (ULID) persistido ANTES    ← única verdad

Entre el ``ExitPlan`` (la decisión) y el ``execution_id`` (que es por FILL) faltaba un
identificador intermedio que sobreviviera a:

    decisión → reserva → orden → fills parciales → reintento → reinicio

Sin él, la reserva de salida se identificaba con ``exit:{engine_id}:{symbol}:{seq}`` donde
``seq`` venía de un contador de proceso (``_v2_exit_seq``) que volvía a 0 en cada arranque.
Tras un reinicio, el primer cierre del mismo símbolo re-generaba la MISMA identidad, y como
el store hace ``ON CONFLICT ... UPDATE``, eso **actualizaba una reserva histórica** en vez de
representar una salida nueva. Aquí la identidad se mintea UNA vez y se persiste.

El módulo también modela el ciclo de vida del INTENT (``state``), que es lo que permite
distinguir tres conceptos que la auditoría pidió separar:

    INTENT  (qué riesgo quise cerrar)   → ``requested_qty``
    ORDER   (qué envié al venue)        → ``venue_order_id``
    FILL    (qué se materializó)        → ``filled_qty`` / ``remaining_qty``

Módulo puro y determinista salvo el generador de identidad (``new_exit_order_id``), que sí
usa reloj/aleatoriedad por construcción; el ``ExitOrder`` en sí no lee reloj: el instante lo
aporta el llamante. Un dato ilegible se declara (``build_exit_order`` devuelve ``None``),
nunca se convierte en un cero inventado.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from bolsa_analytics.cognitive.position_ledger import (
    SIDE_BUY,
    SIDE_SELL,
    normalize_side,
)

#: Ciclo de vida del INTENT de salida (contrato con el journal y el store).
ExitOrderState = Literal[
    "INTENT",  # decidida y persistida; aún sin reserva
    "RESERVED",  # reserva viva creada
    "EMITTED",  # orden enviada al venue
    "PARTIAL",  # materializada en parte (la cola sigue viva)
    "FILLED",  # completamente materializada
    "EMERGENCY",  # la reserva no fue durable: se emite con identidad de emergencia
    "ABANDONED",  # murió sin materializar (liberada por reinicio/cancelación)
]

ENCODED_EXIT_ORDER_STATES: tuple[ExitOrderState, ...] = (
    "INTENT",
    "RESERVED",
    "EMITTED",
    "PARTIAL",
    "FILLED",
    "EMERGENCY",
    "ABANDONED",
)

_VALID_STATES: frozenset[str] = frozenset(ENCODED_EXIT_ORDER_STATES)

#: Estados en los que el INTENT sigue vivo (queda cantidad por materializar).
OPEN_STATES: frozenset[str] = frozenset({"INTENT", "RESERVED", "EMITTED", "PARTIAL", "EMERGENCY"})

_QTY_EPS = 1e-9

#: Alfabeto Crockford base32 (ULID).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def round4(value: float) -> float:
    """Redondeo de la casa (4 decimales), paridad con el resto del ledger."""
    return round(value * 10000) / 10000


def coerce_exit_order_state(value: Any) -> ExitOrderState | None:
    """Normaliza el estado a un literal canónico; ``None`` si no lo es."""
    text = value.strip().upper() if isinstance(value, str) else ""
    if text in _VALID_STATES:
        return cast(ExitOrderState, text)
    return None


def _encode_crockford(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_exit_order_id(
    *,
    now_ms: int | None = None,
    randomness: bytes | None = None,
) -> str:
    """Identidad de salida única y ordenable (ULID: 48 bits de tiempo + 80 aleatorios).

    Se persiste ANTES de reservar o emitir. ``now_ms``/``randomness`` son inyectables para
    que una prueba sea determinista; en producción se usan reloj y ``os.urandom``. Los 48
    bits de tiempo hacen que la identidad sea monótona a gran escala (auditoría: "qué
    salida fue antes"), y los 80 aleatorios evitan cualquier colisión entre procesos.
    """
    timestamp = int(time.time() * 1000) if now_ms is None else int(now_ms)
    payload = os.urandom(10) if randomness is None else bytes(randomness)
    if len(payload) != 10:
        raise ValueError("randomness debe ser exactamente 10 bytes (80 bits)")
    timestamp &= (1 << 48) - 1
    entropy = int.from_bytes(payload, "big")
    return f"{_encode_crockford(timestamp, 10)}{_encode_crockford(entropy, 16)}"


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


@dataclass(frozen=True, slots=True)
class ExitOrder:
    """El INTENT de salida con identidad propia y ciclo de vida durable.

    ``requested_qty`` es lo que la decisión quiso cerrar (INTENT); ``filled_qty`` lo que el
    venue materializó (FILL) y ``remaining_qty`` la cola viva (ORDER). Los tres se separan a
    propósito: confundirlos es exactamente el error que la auditoría señaló (una orden
    parcial de 40 sobre un intent de 100 no cierra el intent).

    ``emergency=True`` marca la salida que se emitió con la reserva NO durable (política B):
    una salida protectora nunca se bloquea por un fallo contable, pero **jamás** se queda
    sin identidad durable.
    """

    exit_order_id: str
    instrument_id: str
    side: str
    requested_qty: float
    account_id: str = ""
    engine_id: str = ""
    filled_qty: float = 0.0
    remaining_qty: float = 0.0
    reservation_id: str | None = None
    venue_order_id: str | None = None
    state: ExitOrderState = "INTENT"
    emergency: bool = False
    reason: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not str(self.exit_order_id or "").strip():
            raise ValueError("ExitOrder exige exit_order_id no vacío")
        if self.side not in (SIDE_BUY, SIDE_SELL):
            raise ValueError(
                f"ExitOrder exige side {SIDE_BUY!r}/{SIDE_SELL!r}: {self.side!r}"
            )
        if self.state not in _VALID_STATES:
            raise ValueError(
                f"ExitOrder exige state {ENCODED_EXIT_ORDER_STATES}: {self.state!r}"
            )

    @property
    def is_open(self) -> bool:
        """True si el INTENT aún tiene cantidad por materializar."""
        return self.state in OPEN_STATES and self.remaining_qty > _QTY_EPS

    @property
    def is_terminal(self) -> bool:
        return not self.is_open

    @property
    def is_sell(self) -> bool:
        return self.side == SIDE_SELL

    def with_reserved(self, reservation_id: str, *, at: str | None = None) -> ExitOrder:
        """Marca que la reserva viva ya existe (``RESERVED``)."""
        return replace(
            self,
            reservation_id=str(reservation_id) or None,
            state="RESERVED",
            updated_at=at or self.updated_at,
        )

    def with_emitted(self, venue_order_id: str | None, *, at: str | None = None) -> ExitOrder:
        """Marca que la orden se envió al venue (``EMITTED``), conservando la cola viva."""
        return replace(
            self,
            venue_order_id=(str(venue_order_id).strip() or None)
            if venue_order_id is not None
            else self.venue_order_id,
            state="EMITTED",
            updated_at=at or self.updated_at,
        )

    def apply_fill(self, quantity: Any, *, at: str | None = None) -> ExitOrder:
        """Acumula un fill materializado y recalcula la cola (``PARTIAL``/``FILLED``).

        Un fill no positivo o ilegible NO mueve el intent (fail-closed: no se inventa
        materialización). El redondeo es el de la casa, y la cantidad llena nunca supera la
        solicitada (``remaining_qty`` no puede ser negativo).
        """
        qty = _finite(quantity)
        if qty is None or qty <= 0:
            return self
        filled = round4(min(self.requested_qty, self.filled_qty + qty))
        remaining = round4(max(0.0, self.requested_qty - filled))
        state: ExitOrderState = "FILLED" if remaining <= _QTY_EPS else "PARTIAL"
        return replace(
            self,
            filled_qty=filled,
            remaining_qty=remaining,
            state=state,
            updated_at=at or self.updated_at,
        )

    def as_emergency(self, reason: str | None, *, at: str | None = None) -> ExitOrder:
        """Marca la salida como emitida SIN reserva durable (política B)."""
        return replace(
            self,
            emergency=True,
            state="EMERGENCY",
            reason=(str(reason).strip() or None) if reason is not None else self.reason,
            updated_at=at or self.updated_at,
        )

    def abandon(self, reason: str | None, *, at: str | None = None) -> ExitOrder:
        """Cierra el intent sin materializar (orden muerta)."""
        return replace(
            self,
            state="ABANDONED",
            remaining_qty=0.0,
            reason=(str(reason).strip() or None) if reason is not None else self.reason,
            updated_at=at or self.updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "exitOrderId": self.exit_order_id,
            "accountId": self.account_id,
            "engineId": self.engine_id,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "requestedQty": self.requested_qty,
            "filledQty": self.filled_qty,
            "remainingQty": self.remaining_qty,
            "reservationId": self.reservation_id,
            "venueOrderId": self.venue_order_id,
            "state": self.state,
            "emergency": self.emergency,
            "reason": self.reason,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def build_exit_order(
    *,
    exit_order_id: Any,
    instrument_id: Any,
    side: Any = SIDE_SELL,
    requested_qty: Any,
    account_id: Any = None,
    engine_id: Any = None,
    filled_qty: Any = 0.0,
    remaining_qty: Any = None,
    reservation_id: Any = None,
    venue_order_id: Any = None,
    state: Any = "INTENT",
    emergency: Any = False,
    reason: Any = None,
    created_at: Any = None,
    updated_at: Any = None,
) -> ExitOrder | None:
    """Normaliza una fila cruda a ``ExitOrder``; ``None`` si NO es interpretable.

    ``None`` significa "esta fila no se puede leer" (el llamante la declara), nunca "cuenta
    cero". Un INTENT sin instrumento o sin cantidad solicitada positiva no es una salida:
    no se fabrica.
    """
    trimmed_id = str(exit_order_id or "").strip()
    trimmed_instrument = str(instrument_id or "").strip()
    normalized = normalize_side(side)
    requested = _finite(requested_qty)
    if not trimmed_id or not trimmed_instrument or not normalized:
        return None
    if requested is None or requested <= 0:
        return None
    filled = _finite(filled_qty) or 0.0
    filled = round4(min(requested, max(0.0, filled)))
    remaining_value = _finite(remaining_qty)
    remaining = (
        round4(max(0.0, remaining_value))
        if remaining_value is not None
        else round4(max(0.0, requested - filled))
    )
    resolved_state = coerce_exit_order_state(state) or "INTENT"
    return ExitOrder(
        exit_order_id=trimmed_id,
        instrument_id=trimmed_instrument,
        side=normalized,
        requested_qty=round4(requested),
        account_id=str(account_id).strip() if account_id is not None else "",
        engine_id=str(engine_id).strip() if engine_id is not None else "",
        filled_qty=filled,
        remaining_qty=remaining,
        reservation_id=(str(reservation_id).strip() or None)
        if reservation_id is not None
        else None,
        venue_order_id=(str(venue_order_id).strip() or None)
        if venue_order_id is not None
        else None,
        state=resolved_state,
        emergency=bool(emergency),
        reason=(str(reason).strip() or None) if reason is not None else None,
        created_at=(str(created_at).strip() or None) if created_at is not None else None,
        updated_at=(str(updated_at).strip() or None) if updated_at is not None else None,
    )


__all__ = [
    "ENCODED_EXIT_ORDER_STATES",
    "OPEN_STATES",
    "ExitOrder",
    "ExitOrderState",
    "build_exit_order",
    "coerce_exit_order_state",
    "new_exit_order_id",
    "round4",
]
