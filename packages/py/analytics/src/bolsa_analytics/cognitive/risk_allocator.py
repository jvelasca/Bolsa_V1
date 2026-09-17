"""RiskAllocator — sizing por riesgo y geometría de operación (AUTO 2.0 · P1).

Separa la DECISIÓN de cuánto invertir de la ESTRATEGIA. La estrategia aporta la
oportunidad (``edge``/``confidence``/``stop_distance``); el allocator calcula la
cantidad a partir del presupuesto de riesgo y la acota por límites de cartera. La
estrategia **nunca** fija ``lot_qty`` (debilidad estructural detectada en v2.39.3).

Fórmula núcleo::

    risk_amount   = min(risk_budget, equity × max_risk_per_trade_pct / 100)
    stop_distance = |entry − stop|
    quantity      = risk_amount / stop_distance

Acotaciones posteriores (cada una registra su ``reason`` en el resultado):

1. ``max_position_pct`` — peso máximo por activo (concentración).
2. ``max_position_value`` — tope de notional por orden (liquidez/capacidad).
3. ``buying_power`` — caja/poder de compra disponible (BRUTO: el allocator le resta
   ``reserved_cash`` antes de acotar, V2.40.4).
4. ``reserved_cash`` — capital comprometido por órdenes PENDIENTES (BUY sin materializar):
   no es falta de dinero, es dinero ya comprometido (``CAP_RESERVED_CASH``).

También aporta la geometría dinámica de la operación (SL/TP por ATR), sustituyendo la
política global de protección (``ProtectionConfig``) por niveles **por operación**:
una estrategia de baja volatilidad y otra de alta no pueden compartir el mismo stop %.

Fail-closed: stop inválido (≤0, o en el lado equivocado del precio), entry ≤0,
``risk_budget``/equity no positivos ⇒ cantidad 0 y ``approved=False`` (nunca se inventa
un tamaño).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.portfolio_reservation import (
    TradingCost,
    TradingCostModel,
    estimate_trading_cost,
)

TradePlanDirection = Literal["long", "short", "none"]

# Razones de acotación (reason codes observables en el Decision Journal).
CAP_RISK_BUDGET = "risk_budget"
CAP_RISK_PCT = "max_risk_per_trade_pct"
CAP_POSITION_PCT = "max_position_pct"
CAP_POSITION_VALUE = "max_position_value"
CAP_BUYING_POWER = "buying_power"
# V2.40.4 — el capital RESERVADO por órdenes pendientes no es poder de compra. Se separa
# de ``CAP_BUYING_POWER`` para que el journal diga POR QUÉ no hay cash (no es lo mismo "no
# queda dinero" que "el dinero está comprometido en órdenes sin materializar").
CAP_RESERVED_CASH = "reserved_cash"
# AUTO-1 — el coste de negociación (comisión + spread + slippage) consume presupuesto de
# riesgo. El tamaño se reduce para que ``stop loss + coste`` quepa en el presupuesto: sin
# esto, el riesgo real de la operación supera el que el motor cree estar asumiendo.
CAP_TRADING_COST = "trading_cost"
# AUTO-1 — el coste no se pudo cuantificar (falta un componente). El tamaño NO se ajusta
# (se degrada al sizing por stop, el histórico) pero se declara: "no sé el coste" no puede
# confundirse con "el coste es 0".
CAP_COST_UNMEASURED = "cost_unmeasured"


def _finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


@dataclass(frozen=True, slots=True)
class RiskAllocatorConfig:
    """Límites del allocator (todo en valores absolutos o %; nada global de la estrategia)."""

    max_risk_per_trade_pct: float | None = 1.0  # % de equity de riesgo por operación.
    max_position_pct: float | None = 20.0  # % de equity como peso máximo por activo.
    max_position_value: float | None = None  # notional máximo por orden (capacidad).
    # Presupuesto de riesgo global se inyecta por llamada (es estado de cartera, no
    # política estática): no vive aquí.


@dataclass(frozen=True, slots=True)
class AllocationResult:
    """Resultado del sizing: cantidad, riesgo consumido y razones de acotación.

    ``risk_amount`` es el **presupuesto de riesgo comprometido** (lo que se reserva), no la
    pérdida del stop: con el coste real activado, parte de ese presupuesto se lo comen las
    fricciones y por eso ``risk_real`` (pérdida esperada = stop loss + coste) es menor. Sin
    ``cost_model`` ambos coinciden y el contrato es el histórico.
    """

    quantity: float
    risk_amount: float | None
    risk_pct: float | None
    stop_distance: float | None
    position_value: float | None
    approved: bool
    capped_reasons: tuple[str, ...] = ()
    # AUTO-1 — riesgo REAL (stop loss + comisión + spread + slippage) de la cantidad final.
    # ``None`` cuando no se pidió modelo de coste (retrocompatible) o no es medible.
    risk_real: float | None = None
    risk_real_pct: float | None = None
    trading_cost: TradingCost | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "riskAmount": self.risk_amount,
            "riskPct": self.risk_pct,
            "riskReal": self.risk_real,
            "riskRealPct": self.risk_real_pct,
            "stopDistance": self.stop_distance,
            "positionValue": self.position_value,
            "approved": self.approved,
            "cappedReasons": list(self.capped_reasons),
            "tradingCost": None if self.trading_cost is None else self.trading_cost.to_dict(),
        }


def compute_stop_distance(
    *,
    entry: float,
    stop: float,
    direction: TradePlanDirection,
) -> float | None:
    """Distancia de riesgo |entry − stop|, válida solo si el stop está del lado correcto.

    Long: stop < entry. Short: stop > entry. Cualquier otra geometría ⇒ ``None``.
    """
    if direction == "long":
        if stop >= entry:
            return None
        return _round4(entry - stop)
    if direction == "short":
        if stop <= entry:
            return None
        return _round4(stop - entry)
    return None


def compute_atr_stop(
    *,
    entry: float,
    atr: float,
    atr_multiplier: float = 1.5,
    direction: TradePlanDirection = "long",
) -> float | None:
    """Stop dinámico por ATR: ``entry − k×ATR`` (long) / ``entry + k×ATR`` (short).

    ``None`` si entry/atr no positivos, o si el stop resultante es inválido (≤0 en long).
    """
    e = _finite_positive(entry)
    a = _finite_positive(atr)
    k = _finite_positive(atr_multiplier)
    if e is None or a is None or k is None:
        return None
    if direction == "long":
        stop = e - k * a
        return _round4(stop) if stop > 0 else None
    if direction == "short":
        return _round4(e + k * a)
    return None


def compute_take_profit(
    *,
    entry: float,
    stop: float,
    r_multiple: float,
    direction: TradePlanDirection = "long",
) -> float | None:
    """Target por múltiplo R: ``entry + R×|entry−stop|`` (long) / espejo (short).

    ``None`` si la distancia de riesgo es inválida o ``r_multiple`` no positivo.
    """
    e = _finite_positive(entry)
    r = _finite_positive(r_multiple)
    if e is None or r is None:
        return None
    distance = compute_stop_distance(entry=e, stop=stop, direction=direction)
    if distance is None:
        return None
    if direction == "long":
        return _round4(e + r * distance)
    if direction == "short":
        return _round4(e - r * distance)
    return None


def compute_allocation(
    *,
    equity: float,
    entry: float,
    stop: float,
    direction: TradePlanDirection = "long",
    risk_budget: float | None = None,
    config: RiskAllocatorConfig | None = None,
    buying_power: float | None = None,
    reserved_cash: float | None = None,
    cost_model: TradingCostModel | None = None,
) -> AllocationResult:
    """Calcula el tamaño de posición por riesgo, acotado por límites de cartera.

    ``risk_budget`` es el riesgo monetario MÁXIMO que se permite consumir en esta
    operación (estado de cartera). Si es ``None``, se usa solo el % de equity de
    ``config``. ``config`` por defecto aplica límites conservadores.

    ``reserved_cash`` (V2.40.4) es capital comprometido por órdenes PENDIENTES (BUY sin
    materializar). Se resta de ``buying_power`` porque ese dinero ya está comprometido:
    sin esta resta, dos entradas del mismo tick podrían gastar el mismo cash. Si la
    resta deja 0 ⇒ ``approved=False`` con ``CAP_RESERVED_CASH`` (motivo distinto de
    ``CAP_BUYING_POWER``: no es falta de dinero, es dinero ya comprometido).

    ``cost_model`` (AUTO-1) hace el riesgo **real**: ``risk_real = stop loss + comisión +
    spread + slippage``. El presupuesto de riesgo debe cubrir los dos sumandos, así que el
    tamaño se reduce para que la pérdida esperada (stop + fricciones) quepa en él. Sin
    ``cost_model`` el contrato es el histórico (solo stop) y el resultado no cambia.

    Devuelve ``AllocationResult`` con ``approved=True`` solo si la cantidad final > 0.
    """
    cfg = config if config is not None else RiskAllocatorConfig()
    eq = _finite_positive(equity)
    e = _finite_positive(entry)
    distance = compute_stop_distance(entry=e or 0.0, stop=stop, direction=direction)
    if eq is None or e is None or distance is None:
        return AllocationResult(
            quantity=0.0,
            risk_amount=None,
            risk_pct=None,
            stop_distance=distance,
            position_value=None,
            approved=False,
        )

    capped: list[str] = []

    # Capital ya comprometido por órdenes PENDIENTES (BUY sin materializar). Se resta del
    # poder de compra para que dos entradas del mismo tick no gasten el mismo cash.
    reserved = _finite(reserved_cash) or 0.0

    # 1) Riesgo monetario a consumir: min(risk_budget, equity × max_risk_per_trade_pct).
    max_by_pct = None
    if cfg.max_risk_per_trade_pct is not None:
        pct = _finite(cfg.max_risk_per_trade_pct)
        if pct is not None and pct > 0:
            max_by_pct = eq * (pct / 100.0)
    risk_amount: float | None = None
    if risk_budget is not None and risk_budget > 0:
        risk_amount = risk_budget
        if max_by_pct is not None and max_by_pct < risk_amount:
            risk_amount = max_by_pct
            capped.append(CAP_RISK_PCT)
    elif max_by_pct is not None:
        risk_amount = max_by_pct
    else:
        return AllocationResult(
            quantity=0.0,
            risk_amount=None,
            risk_pct=None,
            stop_distance=distance,
            position_value=None,
            approved=False,
        )

    qty = risk_amount / distance

    # 1-bis) AUTO-1 — coste real: el presupuesto de riesgo debe cubrir el stop loss Y las
    # fricciones (comisión + spread + slippage). Se estima el coste de la cantidad por
    # riesgo y se reduce el tamaño para que ``stop loss + coste`` quepa en el presupuesto.
    # Como el coste depende del tamaño (y la comisión tiene mínimos/máximos), se resuelve
    # en dos pasadas sobre la cantidad por riesgo ANTES de los topes de cartera: los topes
    # siguen recortando después, y un recorte por concentración simplemente deja el riesgo
    # real por debajo del presupuesto (conservador).
    cost_real: TradingCost | None = None
    if cost_model is not None:
        preliminary = estimate_trading_cost(
            quantity=qty, entry=e, stop=stop, direction=direction, model=cost_model
        )
        cost_real = preliminary
        expected = _finite_positive(preliminary.expected_loss)
        if expected is None:
            # Coste no medible: NO se ajusta (se degrada al sizing por stop, el histórico)
            # pero se declara. "No sé el coste" nunca puede leerse como "coste = 0".
            capped.append(CAP_COST_UNMEASURED)
        else:
            adjusted = qty * (risk_amount / expected)
            if adjusted < qty:
                qty = adjusted
                capped.append(CAP_TRADING_COST)

    # 2) Tope por concentración de activo (max_position_pct).
    if cfg.max_position_pct is not None:
        pct = _finite(cfg.max_position_pct)
        if pct is not None and pct > 0:
            max_qty_pct = (eq * (pct / 100.0)) / e
            if max_qty_pct < qty:
                qty = max_qty_pct
                capped.append(CAP_POSITION_PCT)

    # 3) Tope por notional por orden (capacidad/liquidez).
    if cfg.max_position_value is not None:
        mv = _finite_positive(cfg.max_position_value)
        if mv is not None and mv > 0:
            max_qty_value = mv / e
            if max_qty_value < qty:
                qty = max_qty_value
                capped.append(CAP_POSITION_VALUE)

    # 4) Tope por poder de compra disponible, NETO del capital ya reservado por órdenes
    #    pendientes (V2.40.4): si la reserva es lo que rebaja el tope, el motivo es
    #    ``CAP_RESERVED_CASH`` (no es falta de dinero: es dinero ya comprometido).
    if buying_power is not None:
        bp = _finite(buying_power)
        if bp is not None and bp >= 0:
            gross_cap = bp / e
            net_cap = max(0.0, bp - reserved) / e
            if net_cap < qty:
                qty = net_cap
                if reserved > 0 and net_cap < gross_cap:
                    capped.append(CAP_RESERVED_CASH)
                else:
                    capped.append(CAP_BUYING_POWER)

    qty = _round4(max(0.0, qty))
    risk_pct = _round4((risk_amount / eq) * 100.0) if eq > 0 else None

    # Riesgo REAL de la cantidad FINAL (después de todos los topes). Se recalcula porque
    # los topes cambian el tamaño y, con él, las fricciones. Se publica aunque no se haya
    # podido ajustar: es la pérdida esperada que la operación asume de verdad.
    risk_real: float | None = None
    risk_real_pct: float | None = None
    if cost_model is not None and qty > 0:
        final_cost = estimate_trading_cost(
            quantity=qty, entry=e, stop=stop, direction=direction, model=cost_model
        )
        cost_real = final_cost
        risk_real = _finite_positive(final_cost.expected_loss)
        if risk_real is not None and eq > 0:
            risk_real_pct = _round4((risk_real / eq) * 100.0)

    return AllocationResult(
        quantity=qty,
        risk_amount=_round4(risk_amount),
        risk_pct=risk_pct,
        stop_distance=distance,
        position_value=_round4(qty * e) if qty > 0 else None,
        approved=qty > 0,
        capped_reasons=tuple(dict.fromkeys(capped)),
        risk_real=risk_real,
        risk_real_pct=risk_real_pct,
        trading_cost=None if (cost_model is None or qty <= 0) else cost_real,
    )
