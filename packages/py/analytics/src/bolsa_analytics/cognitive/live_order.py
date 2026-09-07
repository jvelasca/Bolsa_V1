"""LiveOrder — XL-3 LIVE execution state machine (domain only).

≠ PaperOrder (venue PAPER) · ≠ XL-2 sync filled→ledger slice (cerrado).
UNKNOWN is first-class: timeout/lost response → UNKNOWN · NO automatic re-POST.
PARTIAL: filledQuantity + remainingQuantity · execute_trade with full qty FORBIDDEN.
query_broker is the only path out of UNKNOWN (real poll PARKED; mock in tests).

≠ thaw · ≠ PAPER_D_EXECUTE · ≠ LIVE_EXECUTION_UNLOCKED.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

LiveOrderStatus = Literal[
    "AUTHORIZED",
    "SUBMITTING",
    "SUBMITTED",
    "WORKING",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCEL_REQUESTED",
    "CANCELLED",
    "UNKNOWN",
]

LiveOrderSide = Literal["buy", "sell"]
LiveOrderVenue = Literal["LIVE"]

LIVE_ORDER_KEY = "liveOrder"

# ---------------------------------------------------------------------------
# Cantidades deterministas (Decimal, paridad NUMERIC(18,6) de live_orders).
# Cierra H1 de la auditoría V2.13: la DB ya es NUMERIC(18,6) (migración 021),
# pero el dominio seguía casteando a `float`. Aquí toda cantidad se normaliza a
# ``Decimal`` con 6 decimales (misma escala física), de modo que la aritmética
# filled/remaining y el invariante ``filled + remaining == quantity`` son
# EXACTOS en memoria, no aproximados con epsilons de float.
# ---------------------------------------------------------------------------

_QTY_SCALE = Decimal("0.000001")
_ZERO = Decimal("0")


def _qty(value: object) -> Decimal:
    """Convierte/redondea a ``Decimal`` de 6 decimales (ROUND_HALF_UP).

    Acepta int/float/str/Decimal (nan/inf → error). ``None`` no es válido.
    ``int``/``float`` exactos pasan limpios; otros como 0.1 se redondean a 6dp
    (semántica de ``NUMERIC(18,6)``). Fuera de escala se trunca con redondeo
    half-up (evita sesgo bancario/even en magnitudes de cuenta).
    """
    try:
        return Decimal(str(value)).quantize(_QTY_SCALE, rounding=ROUND_HALF_UP)
    except (TypeError, ValueError, InvalidOperation) as exc:  # noqa: BLE001
        raise ValueError(f"quantity not quantizable: {value!r}") from exc

# Terminales: resultado cerrado (FILLED/REJECTED/CANCELLED). Una fila aquí ya no
# está in-flight: no admite más transiciones ni cuenta como "open".
_TERMINAL: frozenset[LiveOrderStatus] = frozenset({"FILLED", "REJECTED", "CANCELLED"})

# V2.13 honest-cancel (intención vs resultado): una cancelación LOCAL = ``DECISION
# (CANCEL_REQUESTED)``, una cancelación de VERACIDAD broker = ``CANCELLED``.
# - Cualquier estado en-vuelo puede DECIDIR CancelarRequest → CANCEL_REQUESTED.
# - CANCEL_REQUESTED NO es terminal: deja de estar in-flight SOLO cuando el broker
#   confirma (→ CANCELLED) o resuelve por otra vía (UNKNOWN/FILLED/REJECTED…). El
#   hecho de pedirlo se persiste en ``cancel_requested_*`` (intención) y la
#   confirmación del venue en ``broker_cancel_confirmed_at`` (resultado).
# Se conservan los bordes directos → CANCELLED para los flujos que YA tienen la
# confirmación del venue (reconcilier/worker), sin romper los existentes.

# UNKNOWN → SUBMITTING (re-POST) is intentionally ABSENT.
ALLOWED_LIVE_ORDER_TRANSITIONS: dict[LiveOrderStatus, frozenset[LiveOrderStatus]] = {
    "AUTHORIZED": frozenset({"SUBMITTING", "REJECTED", "CANCELLED", "CANCEL_REQUESTED"}),
    "SUBMITTING": frozenset({"REJECTED", "UNKNOWN", "SUBMITTED", "CANCEL_REQUESTED"}),
    "SUBMITTED": frozenset({"WORKING", "UNKNOWN", "CANCELLED", "REJECTED", "CANCEL_REQUESTED"}),
    "WORKING": frozenset({"PARTIAL", "FILLED", "UNKNOWN", "CANCELLED", "REJECTED", "CANCEL_REQUESTED"}),
    "PARTIAL": frozenset({"FILLED", "UNKNOWN", "CANCELLED", "CANCEL_REQUESTED"}),
    "FILLED": frozenset(),
    "REJECTED": frozenset(),
    # CANCEL_REQUESTED = decisión local pendiente de confirmación o desenlace.
    "CANCEL_REQUESTED": frozenset({"CANCELLED", "UNKNOWN", "REJECTED", "FILLED", "WORKING"}),
    "CANCELLED": frozenset(),
    # Resolve UNKNOWN only via broker query (not re-POST).
    "UNKNOWN": frozenset({"WORKING", "REJECTED", "FILLED", "PARTIAL", "CANCELLED", "CANCEL_REQUESTED"}),
}

# "open" = no-terminal: la orden sigue viva / en curso / en riesgo. Complemento
# de ``_TERMINAL`` sobre las claves del grafo (que cubren todo el literal), para
# que listar/cancelar no repita strings mágicos y derive de la misma semántica
# terminal del grafo.
NON_TERMINAL_LIVE_STATUSES: frozenset[LiveOrderStatus] = frozenset(
    set(ALLOWED_LIVE_ORDER_TRANSITIONS) - _TERMINAL
)


@dataclass(frozen=True, slots=True)
class LiveOrder:
    order_id: str
    status: LiveOrderStatus
    venue: LiveOrderVenue
    instrument_id: str
    side: LiveOrderSide
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    venue_order_id: str | None
    intent_id: str | None
    financial_apply_count: int
    account_id: str | None = None

    def __post_init__(self) -> None:
        """Coerce cantidades a Decimal(6dp) en CUALQUIER ruta de construcción.

        Garantiza el invariante en memoria: una ``LiveOrder`` siempre guarda
        Decimal exacto de 6 decimales, nunca float/int suelto. (frozen+slots:
        escritura temprana vía object.__setattr__).
        """
        object.__setattr__(self, "quantity", _qty(self.quantity))
        object.__setattr__(self, "filled_quantity", _qty(self.filled_quantity))
        object.__setattr__(self, "remaining_quantity", _qty(self.remaining_quantity))

    def to_dict(self) -> dict[str, object]:
        # La proyección de red/TS consume números (`LiveOrderV1.number`); el valor
        # de verdad (Decimal) vive en el dominio y en BM `NUMERIC(18,6)`.
        return {
            "orderId": self.order_id,
            "status": self.status,
            "venue": self.venue,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "quantity": float(self.quantity),
            "filledQuantity": float(self.filled_quantity),
            "remainingQuantity": float(self.remaining_quantity),
            "venueOrderId": self.venue_order_id,
            "intentId": self.intent_id,
            "financialApplyCount": self.financial_apply_count,
            "accountId": self.account_id,
        }


def build_live_order(
    *,
    order_id: str,
    instrument_id: str,
    side: LiveOrderSide,
    quantity: object,
    intent_id: str | None = None,
    status: LiveOrderStatus = "AUTHORIZED",
    account_id: str | None = None,
) -> LiveOrder:
    qty = _qty(quantity)
    return LiveOrder(
        order_id=order_id,
        status=status,
        venue="LIVE",
        instrument_id=instrument_id,
        side=side,
        quantity=qty,
        filled_quantity=_ZERO,
        remaining_quantity=qty,
        venue_order_id=None,
        intent_id=intent_id,
        financial_apply_count=0,
        account_id=account_id,
    )


def can_transition_live_order(current: LiveOrderStatus, nxt: LiveOrderStatus) -> bool:
    if current in _TERMINAL and nxt != current:
        return False
    return nxt in ALLOWED_LIVE_ORDER_TRANSITIONS.get(current, frozenset())


class LiveOrderTransitionError(ValueError):
    """Transición ilegal del grafo LIVE (p.ej. UNKNOWN → SUBMITTING)."""


def transition_live_order(
    order: LiveOrder,
    nxt: LiveOrderStatus,
    *,
    filled_quantity: object | None = None,
    venue_order_id: str | None = None,
    apply_financial: bool = False,
) -> LiveOrder:
    """Aplica transición. apply_financial solo en FILLED (idempotente).

    Decimal(6dp) exacto: filled/remaining CIERRAN en memoria
    (filled + remaining === quantity), sin epsilon float.
    """
    if not can_transition_live_order(order.status, nxt):
        raise LiveOrderTransitionError(f"live_order forbidden: {order.status} → {nxt}")

    filled = order.filled_quantity
    remaining = order.remaining_quantity
    if filled_quantity is not None:
        filled = _qty(filled_quantity)
        if filled < _ZERO or filled > order.quantity:
            raise LiveOrderTransitionError(
                f"filled_quantity {filled} out of range (0..{order.quantity})"
            )
        remaining = _qty(order.quantity - filled)
        if remaining < _ZERO:
            raise LiveOrderTransitionError(
                f"remaining negative: {order.quantity} - {filled}"
            )

    if nxt == "PARTIAL":
        if filled <= _ZERO:
            raise LiveOrderTransitionError("PARTIAL requires filled_quantity > 0")
        if remaining <= _ZERO:
            raise LiveOrderTransitionError("PARTIAL requires remaining_quantity > 0")
    if nxt == "FILLED":
        if filled_quantity is None:
            # FILLED sin detalle de broker → el total capturado es la orden entera.
            filled = order.quantity
        elif filled != order.quantity:
            # FILLED con filled < quantity = desacuerdo broker-truth; fail-closed
            # para reconciliar, NUNCA un estado terminal normalizado a la fuerza.
            raise LiveOrderTransitionError(
                "FILLED requires filled_quantity == quantity "
                f"(order {order.quantity}, broker {filled}) · reconciliation required"
            )
        remaining = _ZERO

    apply_count = order.financial_apply_count
    if apply_financial:
        if nxt != "FILLED":
            raise LiveOrderTransitionError("financial apply only allowed on FILLED")
        # Duplicate FILLED events: only one financial effect. The counter is a
        # monotonic "first financial application recorded" marker: it never
        # decreases, so a callar que ya aplicó (>=1) no se colapsa a 1 ni se
        # pierde el hecho de que el efecto financiero ya se aplicó.
        if apply_count < 1:
            apply_count = 1

    return LiveOrder(
        order_id=order.order_id,
        status=nxt,
        venue="LIVE",
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=order.quantity,
        filled_quantity=filled,
        remaining_quantity=remaining,
        venue_order_id=venue_order_id if venue_order_id is not None else order.venue_order_id,
        intent_id=order.intent_id,
        financial_apply_count=apply_count,
        account_id=order.account_id,
    )


def forbid_execute_trade_for_partial(order: LiveOrder) -> None:
    """PARKED: Partial → PositionState/ledger. Never execute_trade with full qty."""
    if order.status == "PARTIAL":
        raise LiveOrderTransitionError(
            "execute_trade forbidden on PARTIAL · use filled_quantity only (PARKED)"
        )


def forbid_repost_from_unknown(order: LiveOrder) -> None:
    """UNKNOWN must not re-POST; only query_broker may resolve."""
    if order.status == "UNKNOWN":
        raise LiveOrderTransitionError("UNKNOWN forbids re-POST · query_broker only")


# ---------------------------------------------------------------------------
# V2.13 — Reconcile LiveOrder vs broker-truth (order-level, read-only report).
# ---------------------------------------------------------------------------

# Resultado de contrastar la máquina local contra lo que contesta el broker.
LiveOrderReconcileStatus = Literal[
    "consistent",
    "reconciliation_required",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class LiveOrderReconcileReport:
    """Informe *declarativo* (detecta, no muta ni auto-heal).

    Reconciliación a nivel de orden (broker-truth vs local-truth). Un status
    ``reconciliation_required`` significa que local y broker no cuadran y NO debe
    normalizarse; la cancel/shadow real de broker (PARKED) podrá alimentar esto
    para abrir un incidente / veto OR-4 por cuenta.
    """

    order_id: str
    status: LiveOrderReconcileStatus
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "orderId": self.order_id,
            "status": self.status,
            "detail": self.detail,
            "reconciliationRequired": self.status == "reconciliation_required",
        }


_QTY_EPS = Decimal("0")  # paridad exacta con invariante Decimal(6dp) de dominio


def reconcile_live_order_vs_broker(
    *,
    order: LiveOrder,
    broker_status: str | None,
    broker_filled: object | None,
) -> LiveOrderReconcileReport:
    """Contrasta una respuesta broker-side contra la máquina local de la orden.

    Report puro y declarativo (detecta, no muta ni auto-heal). Fail-closed: ante
    ambigüedad o desajuste irreconciliable devuelve ``reconciliation_required``.
    Semántica clave del modelo FILLED (V2.13): el broker nunca da un FILLED
    terminal con filled parcial de la orden; si lo hace → reconciliation_required,
    jamás un estado terminal fabricado. Compara en Decimal exacto (order.quantity
    es Decimal); un broker_filled float se reduce a la misma escala 6dp.
    """
    oid = order.order_id
    st = (broker_status or "").strip().lower()

    if st in {"", "unavailable"}:
        return LiveOrderReconcileReport(oid, "unavailable", "broker unavailable")

    if st == "filled":
        if order.quantity > _QTY_EPS:
            broker = _qty(broker_filled) if broker_filled is not None else None
            if broker is None or broker != order.quantity:
                return LiveOrderReconcileReport(
                    oid,
                    "reconciliation_required",
                    f"broker filled={broker_filled} != order qty={order.quantity}",
                )
        if order.status == "FILLED":
            return LiveOrderReconcileReport(oid, "consistent", "filled (local==broker)")
        if order.status in {"CANCELLED", "REJECTED", "PARTIAL"}:
            return LiveOrderReconcileReport(
                oid,
                "consistent",
                "filled posterior coherente con trayectoria local",
            )
        return LiveOrderReconcileReport(
            oid,
            "consistent",
            "filled con cantidad completa (aplicar efecto financiero = PARKED)",
        )

    if st == "partial":
        broker = _qty(broker_filled) if broker_filled is not None else None
        if broker is None or not (_ZERO < broker < order.quantity):
            return LiveOrderReconcileReport(
                oid,
                "reconciliation_required",
                f"partial con filled={broker_filled} fuera de (0, qty={order.quantity})",
            )
        if order.status in {"FILLED", "CANCELLED", "REJECTED"}:
            return LiveOrderReconcileReport(
                oid,
                "reconciliation_required",
                f"broker partial pero local ya {order.status}",
            )
        return LiveOrderReconcileReport(
            oid,
            "consistent",
            "partial coherente con la orden en curso",
        )

    # working / cancelled / rejected
    if st == "working":
        if order.status in {"CANCELLED", "REJECTED", "FILLED"}:
            return LiveOrderReconcileReport(
                oid,
                "reconciliation_required",
                f"broker working pero local ya {order.status}",
            )
        return LiveOrderReconcileReport(oid, "consistent", "working (en curso)")
    if st in {"cancelled", "rejected"}:
        if order.status == {"cancelled": "CANCELLED", "rejected": "REJECTED"}[st]:
            return LiveOrderReconcileReport(
                oid, "consistent", f"{st} corroborado por el broker"
            )
        return LiveOrderReconcileReport(
            oid,
            "reconciliation_required",
            f"broker {st} pero local {order.status}",
        )
    return LiveOrderReconcileReport(oid, "unavailable", "outcome no reconocido")

