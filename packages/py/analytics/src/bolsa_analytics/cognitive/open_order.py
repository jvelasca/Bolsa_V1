"""OpenOrder — órdenes en vuelo como CAPITAL y RIESGO comprometidos (AUTO 2.0 · V2.40.4).

El snapshot de cartera sabía ``open_orders: int`` — un contador. Eso es información
insuficiente para decidir: ``open_orders = 3`` no dice cuánto capital está comprometido
ni cuánto riesgo. El caso real que motiva este módulo:

    Cash = 50.000 €
    pero BUY pending = 40.000 €
    ⇒ AUTO NO tiene 50.000 € disponibles para otra entrada.

AUTO SIM liquida dentro del mismo tick, así que **no** existen órdenes de venue en
vuelo. Lo que sí existe —y sobrevive a un crash— son ``ExecutionEvent`` en estado
no-``APPLIED``: fills capturados cuyo dinero todavía no se ha materializado. Su
instrumento/lado/cantidad/precio viven en ``sim_fill_finance_context``. Ese es el
productor de ``OpenOrder``.

Reglas de honestidad (V2.40.4):

* Una orden cuyo capital **no** se puede cuantificar (sin cantidad o sin precio) no
  reserva 0: reserva **desconocido**, y el resumen lo declara con
  ``measurement != COMPLETE`` sobre el total.
* Una orden de VENTA nunca añade riesgo: reserva 0 € de capital y 0 € de riesgo (libera
  o cierra). Una orden de COMPRA reserva su notional, y reserva riesgo solo si alguien
  lo declara (``risk_amount`` explícito, p.ej. desde el ``TradePlan``); si no, el riesgo
  pendiente es un SUELO y el resumen lo declara.

Los importes son aritmética pura sobre lo que se recibe: este módulo no lee la base de
datos ni decide. El veto vive en ``PortfolioDecisionEngine``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MeasurementStatus,
    measurement_from_counts,
)

# Estados de un ``ExecutionEvent`` que NO han materializado dinero. Son los únicos en
# los que una orden existe sin haber movido caja (``APPLIED`` es terminal: ya movió).
OpenOrderStatus = Literal["CAPTURED", "APPLYING", "RETRY", "FAILED"]

OPEN_ORDER_CAPTURED: OpenOrderStatus = "CAPTURED"
OPEN_ORDER_APPLYING: OpenOrderStatus = "APPLYING"
OPEN_ORDER_RETRY: OpenOrderStatus = "RETRY"
OPEN_ORDER_FAILED: OpenOrderStatus = "FAILED"

# Orden estable y exhaustiva de los estados NO terminales. Un estado desconocido NO se
# asume terminal: el llamante lo trata como pendiente (fail-closed) y lo declara.
NON_TERMINAL_APPLY_STATUSES: tuple[OpenOrderStatus, ...] = (
    OPEN_ORDER_CAPTURED,
    OPEN_ORDER_APPLYING,
    OPEN_ORDER_RETRY,
    OPEN_ORDER_FAILED,
)

SIDE_BUY = "buy"
SIDE_SELL = "sell"


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


def _finite_positive(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def _normalize_side(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in {SIDE_BUY, SIDE_SELL} else ""


def _normalize_status(value: Any) -> OpenOrderStatus:
    raw = str(value or "").strip().upper()
    if raw in NON_TERMINAL_APPLY_STATUSES:
        return raw  # type: ignore[return-value]
    # Un estado no reconocido (o ``APPLIED``, que el llamante no debería pasar) se
    # declara como el más conservador: capturado y pendiente de resolver.
    return OPEN_ORDER_CAPTURED


@dataclass(frozen=True, slots=True)
class OpenOrder:
    """Orden AUTO pendiente de materializar, con su capital/riesgo comprometidos.

    ``reserved_cash`` / ``risk_amount`` son ``None`` cuando **no se pueden cuantificar**
    (nunca 0 silencioso): el resumen agregado convierte esos huecos en
    ``measurement != COMPLETE``, que es lo que veta la entrada.
    """

    execution_id: str
    order_id: str = ""
    venue_order_id: str | None = None
    instrument_id: str = ""
    side: str = ""
    requested_qty: float | None = None
    remaining_qty: float | None = None
    price: float | None = None
    reserved_cash: float | None = None
    risk_amount: float | None = None
    sector: str | None = None
    strategy_version_id: str | None = None
    trade_plan_id: str | None = None
    status: OpenOrderStatus = OPEN_ORDER_CAPTURED

    @property
    def is_buy(self) -> bool:
        return self.side == SIDE_BUY

    @property
    def is_sell(self) -> bool:
        return self.side == SIDE_SELL

    @property
    def market_value(self) -> float | None:
        """Notional de lo que queda por materializar (``None`` si no es calculable)."""
        qty = _finite_positive(self.remaining_qty)
        price = _finite_positive(self.price)
        if qty is None or price is None:
            return None
        return _round4(qty * price)

    @property
    def is_quantified(self) -> bool:
        """True si capital, riesgo y exposición de esta orden son cuantificables.

        Es la unidad con la que el resumen decide ``measurement``: una orden que no se
        puede cuantificar del todo convierte el agregado en un SUELO.
        """
        return (
            self.side in (SIDE_BUY, SIDE_SELL)
            and self.market_value is not None
            and self.reserved_cash is not None
            and self.risk_amount is not None
            and self.sector is not None
            and bool(str(self.sector).strip())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "executionId": self.execution_id,
            "orderId": self.order_id,
            "venueOrderId": self.venue_order_id,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "requestedQty": self.requested_qty,
            "remainingQty": self.remaining_qty,
            "price": self.price,
            "reservedCash": self.reserved_cash,
            "riskAmount": self.risk_amount,
            "sector": self.sector,
            "strategyVersionId": self.strategy_version_id,
            "tradePlanId": self.trade_plan_id,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class OpenOrderSummary:
    """Agregado del libro de órdenes pendientes (capital, riesgo y exposición).

    Los importes son **suelos** cuando ``measurement != COMPLETE``: suman solo las
    órdenes cuantificables. El consumidor que no pueda tolerar un suelo debe vetar —es
    lo que hace ``PortfolioDecisionEngine`` con ``open_orders_unmeasurable``.
    """

    orders: tuple[OpenOrder, ...] = ()
    reserved_cash: float = 0.0
    pending_risk: float = 0.0
    pending_exposure_pct: float | None = None
    pending_exposure_by_sector: dict[str, float] = field(default_factory=dict)
    pending_sell_qty: dict[str, float] = field(default_factory=dict)
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE

    @property
    def count(self) -> int:
        return len(self.orders)

    @property
    def is_complete(self) -> bool:
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "orders": [o.to_dict() for o in self.orders],
            "count": self.count,
            "reservedCash": self.reserved_cash,
            "pendingRisk": self.pending_risk,
            "pendingExposurePct": self.pending_exposure_pct,
            "pendingExposureBySector": dict(self.pending_exposure_by_sector),
            "pendingSellQty": dict(self.pending_sell_qty),
            "measurement": self.measurement,
        }


def build_open_order(
    *,
    execution_id: str,
    order_id: str = "",
    venue_order_id: str | None = None,
    instrument_id: str = "",
    side: Any = "",
    quantity: Any = None,
    price: Any = None,
    requested_qty: Any = None,
    sector: Any = None,
    reserved_cash: Any = None,
    risk_amount: Any = None,
    strategy_version_id: Any = None,
    trade_plan_id: Any = None,
    status: Any = OPEN_ORDER_CAPTURED,
) -> OpenOrder:
    """Construye una orden pendiente derivando capital/riesgo de lo que se conozca.

    Derivación (fail-closed):

    * VENTA ⇒ ``reserved_cash = 0``, ``risk_amount = 0`` (vender no añade riesgo; libera
      capital o cierra exposición). Solo necesita cantidad y precio para ser cuantificable.
    * COMPRA ⇒ ``reserved_cash = cantidad × precio``. El ``risk_amount`` **no se inventa**:
      si el llamante no lo aporta (p.ej. desde el ``TradePlan``) queda ``None`` y el
      riesgo pendiente del resumen es un suelo.
    * Lado desconocido o cantidad/precio no positivos ⇒ importes ``None``.

    ``reserved_cash``/``risk_amount`` explícitos tienen prioridad sobre la derivación: el
    llamante que conoce el número real (una reserva ya calculada) manda.
    """
    qty = _finite_positive(quantity)
    px = _finite_positive(price)
    normalized_side = _normalize_side(side)

    explicit_cash = _finite(reserved_cash)
    explicit_risk = _finite(risk_amount)

    derived_cash: float | None = None
    derived_risk: float | None = None
    if normalized_side == SIDE_SELL:
        derived_cash = 0.0
        derived_risk = 0.0
    elif normalized_side == SIDE_BUY and qty is not None and px is not None:
        derived_cash = _round4(qty * px)

    resolved_sector = (
        str(sector).strip() if isinstance(sector, str) and str(sector).strip() else None
    )
    return OpenOrder(
        execution_id=str(execution_id or "").strip(),
        order_id=str(order_id or "").strip(),
        venue_order_id=str(venue_order_id).strip() if venue_order_id else None,
        instrument_id=str(instrument_id or "").strip(),
        side=normalized_side,
        requested_qty=_finite_positive(requested_qty) or qty,
        remaining_qty=qty,
        price=px,
        reserved_cash=explicit_cash if explicit_cash is not None else derived_cash,
        risk_amount=explicit_risk if explicit_risk is not None else derived_risk,
        sector=resolved_sector,
        strategy_version_id=(
            str(strategy_version_id).strip() if strategy_version_id else None
        ),
        trade_plan_id=str(trade_plan_id).strip() if trade_plan_id else None,
        status=_normalize_status(status),
    )


def summarize_open_orders(
    orders: tuple[OpenOrder, ...],
    *,
    equity: float | None = None,
) -> OpenOrderSummary:
    """Agrega el libro de órdenes: capital reservado, riesgo y exposición pendientes.

    ``equity`` es el denominador de la exposición pendiente (%; ``None`` si no hay
    equity evaluable). ``measurement`` es ``COMPLETE`` solo si **todas** las órdenes son
    cuantificables (capital + riesgo + sector): si no, los importes son suelos y el motor
    de decisión no debe autorizar entrada nueva contra ellos.
    """
    tuple_orders = tuple(orders or ())
    if not tuple_orders:
        return OpenOrderSummary(
            orders=(),
            reserved_cash=0.0,
            pending_risk=0.0,
            pending_exposure_pct=_round4(0.0) if _finite_positive(equity) else None,
            measurement=MEASUREMENT_COMPLETE,
        )

    reserved_cash = 0.0
    pending_risk = 0.0
    exposure_value = 0.0
    by_sector: dict[str, float] = {}
    sell_qty: dict[str, float] = {}
    quantified = 0

    for order in tuple_orders:
        cash = _finite(order.reserved_cash)
        risk = _finite(order.risk_amount)
        if cash is not None:
            reserved_cash += cash
        if risk is not None:
            pending_risk += risk
        if order.is_sell:
            qty = _finite_positive(order.remaining_qty)
            if qty is not None and order.instrument_id:
                sell_qty[order.instrument_id] = sell_qty.get(order.instrument_id, 0.0) + qty
        if order.is_buy:
            mv = order.market_value
            if mv is not None:
                exposure_value += mv
                if order.sector:
                    by_sector[order.sector] = by_sector.get(order.sector, 0.0) + mv
        if order.is_quantified:
            quantified += 1

    eq = _finite_positive(equity)
    exposure_pct = None
    by_sector_pct: dict[str, float] = {}
    if eq is not None:
        exposure_pct = _round4((exposure_value / eq) * 100.0)
        by_sector_pct = {k: _round4((v / eq) * 100.0) for k, v in by_sector.items()}

    return OpenOrderSummary(
        orders=tuple_orders,
        reserved_cash=_round4(reserved_cash),
        pending_risk=_round4(pending_risk),
        pending_exposure_pct=exposure_pct,
        pending_exposure_by_sector=by_sector_pct,
        pending_sell_qty={k: _round4(v) for k, v in sell_qty.items()},
        measurement=measurement_from_counts(
            valued=quantified, unvalued=len(tuple_orders) - quantified
        ),
    )


def coerce_open_order(raw: Any) -> OpenOrder | None:
    """Normaliza una orden pendiente (``OpenOrder``, ``Mapping`` o atributos).

    Fail-closed: sin ``execution_id`` no hay identidad de fill y la fila se descarta (el
    llamante lo detecta porque el conteo no cuadra con lo leído). Los importes se
    derivan con ``build_open_order`` si el origen no los trae: un origen que solo conoce
    lado/cantidad/precio no puede dejar la reserva en 0 por omisión.
    """
    if isinstance(raw, OpenOrder):
        return raw
    if isinstance(raw, Mapping):
        execution_id = raw.get("executionId") or raw.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id.strip():
            return None
        remaining = raw.get("remainingQty")
        if remaining is None:
            remaining = raw.get("remaining_qty")
        return build_open_order(
            execution_id=execution_id,
            order_id=raw.get("orderId") or raw.get("order_id") or "",
            venue_order_id=raw.get("venueOrderId") or raw.get("venue_order_id"),
            instrument_id=raw.get("instrumentId") or raw.get("instrument_id") or "",
            side=raw.get("side"),
            requested_qty=raw.get("requestedQty") or raw.get("requested_qty"),
            quantity=remaining if remaining is not None else raw.get("quantity"),
            price=raw.get("price"),
            sector=raw.get("sector"),
            reserved_cash=raw.get("reservedCash") or raw.get("reserved_cash"),
            risk_amount=raw.get("riskAmount") or raw.get("risk_amount"),
            strategy_version_id=(
                raw.get("strategyVersionId") or raw.get("strategy_version_id")
            ),
            trade_plan_id=raw.get("tradePlanId") or raw.get("trade_plan_id"),
            status=raw.get("status"),
        )

    execution_id = getattr(raw, "execution_id", None)
    if not isinstance(execution_id, str) or not execution_id.strip():
        return None
    return build_open_order(
        execution_id=execution_id,
        order_id=getattr(raw, "order_id", "") or "",
        venue_order_id=getattr(raw, "venue_order_id", None),
        instrument_id=getattr(raw, "instrument_id", "") or "",
        side=getattr(raw, "side", ""),
        requested_qty=getattr(raw, "requested_qty", None),
        quantity=getattr(raw, "remaining_qty", None)
        if getattr(raw, "remaining_qty", None) is not None
        else getattr(raw, "requested_qty", None),
        price=getattr(raw, "price", None),
        sector=getattr(raw, "sector", None),
        reserved_cash=getattr(raw, "reserved_cash", None),
        risk_amount=getattr(raw, "risk_amount", None),
        strategy_version_id=getattr(raw, "strategy_version_id", None),
        trade_plan_id=getattr(raw, "trade_plan_id", None),
        status=getattr(raw, "status", OPEN_ORDER_CAPTURED),
    )


__all__ = [
    "NON_TERMINAL_APPLY_STATUSES",
    "OPEN_ORDER_APPLYING",
    "OPEN_ORDER_CAPTURED",
    "OPEN_ORDER_FAILED",
    "OPEN_ORDER_RETRY",
    "SIDE_BUY",
    "SIDE_SELL",
    "OpenOrder",
    "OpenOrderStatus",
    "OpenOrderSummary",
    "build_open_order",
    "coerce_open_order",
    "summarize_open_orders",
]
