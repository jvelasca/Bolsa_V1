"""AutoPortfolioSnapshot — estado canónico único del portfolio AUTO (AUTO 2.0 · P0).

Objeto de primera clase que agrega TODO el estado operativo relevante para que el
sistema de decisión AUTO tome TODAS sus decisiones contra una única foto consistente,
en lugar de que cada componente conozca una parte distinta del estado (fragmentación
operativa detectada en la auditoría de v2.39.3-beta).

Campos (canónicos):

* **capital / cash / equity / buying_power** — base de capital y poder de compra.
* **positions** — posiciones abiertas (instrumento, valor de mercado, sector, cantidad,
  P&L no realizado).
* **open_orders** — órdenes abiertas pendientes.
* **daily_pnl / realized_pnl / unrealized_pnl** — P&L del día, realizado y no realizado.
* **risk_used / risk_budget** — riesgo monetario consumido y presupuesto total de
  riesgo abierto; ``risk_remaining = risk_budget - risk_used``.
* **exposure_total / exposure_by_sector / exposure_by_asset** — exposición en % de equity.
* **risk_measurement / exposure.measurement** — estado de MEDICIÓN de esos agregados
  (V2.40.4): un agregado que solo suma lo que sabe medir no es "el total", es un SUELO.
* **drawdown_pct** — drawdown actual.
* **active_strategies** — versiones de estrategia ACTIVE vigentes.
* **market_regime** — régimen operativo vigente.
* **last_reconciliation** / **data_freshness** — salud de reconciliación y frescura de datos.

Es una **foto** (immutable, frozen): no muta posiciones ni decide. Solo agrega y deriva.
La derivación desde el lector canónico del worker (``position_state`` abierto) vive en la
capa application; este módulo es aritmética pura sobre los inputs que reciba.

Fail-closed: valores no finitos o ausentes se tratan como ``None``/``0`` (nunca se inventa
un saldo ni una exposición). Un ``equity`` no positivo impide derivar porcentajes de
exposición (se devuelven vacíos, no ceros engañosos).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    coerce_measurement,
    measurement_from_counts,
)
from bolsa_analytics.cognitive.open_order import (
    OpenOrder,
    OpenOrderSummary,
    coerce_open_order,
    summarize_open_orders,
)

UNKNOWN_SECTOR = "<unknown>"

# Frescura de datos canónica (tri-estado, fail-closed): ``stale`` bloquea aperturas.
DATA_FRESH = "fresh"
DATA_STALE = "stale"
DATA_UNKNOWN = "unknown"

# Estados de reconciliación canónicos (compatibles con ``sim_reconciliation``).
RECON_CLEAN = "clean"
RECON_ATTENTION = "attention"
RECON_CRITICAL = "critical"
RECON_UNKNOWN = "unknown"

# V2.40.4 — estado de MEDICIÓN de una magnitud agregada. Vive en ``measurement`` (módulo
# puro compartido con ``open_order``) y se re-exporta aquí para que los consumidores del
# snapshot no tengan que conocer la ubicación interna.
MeasurementStatus = MeasurementStatus
RiskMeasurementStatus = MeasurementStatus
ExposureMeasurementStatus = MeasurementStatus


def _finite(value: Any) -> float | None:
    """Float finito o ``None`` (NaN/inf/no-numérico ⇒ ausente)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _non_negative(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number < 0:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """Posición abierta del snapshot (mínimo canónico)."""

    instrument_id: str
    quantity: float
    market_value: float | None = None
    sector: str | None = None
    unrealized_pnl: float | None = None
    # Riesgo monetario consumido por esta posición (stop_distance × quantity), si se
    # conoce; contribuye a ``risk_used``.
    risk_amount: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "quantity": self.quantity,
            "marketValue": self.market_value,
            "sector": self.sector,
            "unrealizedPnl": self.unrealized_pnl,
            "riskAmount": self.risk_amount,
        }


@dataclass(frozen=True, slots=True)
class ExposureBreakdown:
    """Desglose de exposición en % de equity (total, por sector, por activo).

    ``measurement`` (V2.40.4) declara si TODAS las posiciones con cantidad pudieron
    valorarse. ``by_asset``/``by_sector`` siguen siendo aritmética pura sobre lo que sí
    se pudo valorar: un ``total_pct`` de 20% con medición ``PARTIAL`` significa "20% o
    más", nunca "20% exactamente".
    """

    total_pct: float | None
    by_sector: dict[str, float] = field(default_factory=dict)
    by_asset: dict[str, float] = field(default_factory=dict)
    measurement: MeasurementStatus = MEASUREMENT_UNKNOWN

    @property
    def is_complete(self) -> bool:
        """True solo si la exposición cubre TODAS las posiciones (fail-closed)."""
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalPct": self.total_pct,
            "bySector": dict(self.by_sector),
            "byAsset": dict(self.by_asset),
            "measurement": self.measurement,
        }


def _safe_market_value(value: Any) -> float | None:
    number = _non_negative(value)
    if number is None or number <= 0:
        return None
    return number


def aggregate_exposure(
    positions: tuple[PortfolioPosition, ...],
    *,
    equity: float | None,
) -> ExposureBreakdown:
    """Exposición agregada (total / por sector / por activo) en % de equity.

    ``equity`` es el denominador. Si es ``None`` o <= 0, se usa la suma de los valores
    de mercado disponibles; si sigue siendo <= 0, no se puede derivar y se devuelve un
    desglose vacío (``total_pct=None``), jamás un cero engañoso (fail-closed).

    V2.40.4: las posiciones con cantidad cuyo ``market_value`` no puede calcularse NO se
    suman (correcto como aritmética) pero **dejan constancia** en ``measurement``: el
    resultado es un SUELO, no el total. ``COMPLETE`` solo si todas se valoraron.
    """
    values: list[tuple[str, float, str]] = []
    unvalued = 0
    for pos in positions:
        if pos.quantity <= 0:
            continue
        mv = _safe_market_value(pos.market_value)
        if mv is None:
            unvalued += 1
            continue
        sector = pos.sector if pos.sector and str(pos.sector).strip() else UNKNOWN_SECTOR
        values.append((str(pos.instrument_id), mv, str(sector)))

    measurement = measurement_from_counts(valued=len(values), unvalued=unvalued)
    if not values:
        return ExposureBreakdown(total_pct=None, measurement=measurement)

    denominator = _safe_market_value(equity)
    if denominator is None:
        denominator = sum(mv for _, mv, _ in values)
    if denominator is None or denominator <= 0:
        return ExposureBreakdown(total_pct=None, measurement=measurement)

    by_asset: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    total = 0.0
    for instrument_id, mv, sector in values:
        by_asset[instrument_id] = by_asset.get(instrument_id, 0.0) + mv
        by_sector[sector] = by_sector.get(sector, 0.0) + mv
        total += mv

    return ExposureBreakdown(
        total_pct=_round4((total / denominator) * 100.0),
        by_sector={k: _round4((v / denominator) * 100.0) for k, v in by_sector.items()},
        by_asset={k: _round4((v / denominator) * 100.0) for k, v in by_asset.items()},
        measurement=measurement,
    )


@dataclass(frozen=True, slots=True)
class AutoPortfolioSnapshot:
    """Foto canónica e inmutable del estado del portfolio AUTO."""

    account_id: str
    capital: float | None = None
    cash: float | None = None
    equity: float | None = None
    buying_power: float | None = None
    positions: tuple[PortfolioPosition, ...] = ()
    # V2.40.4 — órdenes PENDIENTES (no materializadas) con su capital/riesgo comprometido.
    # Es una tupla de ``OpenOrder``, no un contador: ``open_orders = 3`` no dice cuánto
    # capital está comprometido, que es lo que el motor necesita para no gastar dos veces
    # el mismo cash. El agregado se deriva con ``summarize_open_orders``.
    open_orders: tuple[OpenOrder, ...] = ()
    order_book_measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    daily_pnl: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    risk_used: float | None = None
    risk_budget: float | None = None
    # V2.40.4 — estado de medición del riesgo agregado (``risk_used``). Con ``PARTIAL``
    # o ``UNKNOWN`` el número existe pero es un SUELO: el motor veta la entrada.
    risk_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    exposure: ExposureBreakdown = field(default_factory=lambda: ExposureBreakdown(total_pct=None))
    drawdown_pct: float | None = None
    active_strategies: tuple[str, ...] = ()
    market_regime: str | None = None
    last_reconciliation: str = RECON_UNKNOWN
    data_freshness: str = DATA_UNKNOWN
    as_of: str = ""

    @property
    def risk_remaining(self) -> float | None:
        """Riesgo monetario aún disponible (``budget - (used + pending)``).

        ``None`` si no hay budget. Nunca negativo (se clampa a 0). V2.40.4: el riesgo de
        las órdenes PENDIENTES también consume presupuesto: no está en una posición, pero
        ya está comprometido (con ``pending_risk = 0`` sin órdenes, el valor histórico no
        cambia).
        """
        budget = _non_negative(self.risk_budget)
        if budget is None:
            return None
        committed = (_non_negative(self.risk_used) or 0.0) + self.pending_risk
        return _round4(max(0.0, budget - committed))

    @property
    def open_order_count(self) -> int:
        """Número de órdenes pendientes (derivado de la tupla, no un campo suelto)."""
        return len(self.open_orders)

    @property
    def open_order_summary(self) -> OpenOrderSummary:
        """Agregado del libro de órdenes (capital reservado, riesgo y exposición)."""
        return summarize_open_orders(self.open_orders, equity=_finite(self.equity))

    @property
    def reserved_cash(self) -> float:
        """Cash comprometido por órdenes BUY pendientes (SUELO si la medición no es COMPLETE)."""
        return self.open_order_summary.reserved_cash

    @property
    def available_cash(self) -> float | None:
        """``cash − reserved_cash`` (cota SUPERIOR cuando el libro no es medible).

        ``None`` si no hay ``cash`` conocido: no se inventa un disponible. El motor veta
        la apertura cuando la medición no es ``COMPLETE``, así que este valor solo es
        accionable cuando el libro está completamente cuantificado.
        """
        cash = _finite(self.cash)
        if cash is None:
            return None
        return _round4(max(0.0, cash - self.reserved_cash))

    @property
    def pending_risk(self) -> float:
        """Riesgo comprometido por órdenes pendientes (SUELO si la medición no es COMPLETE)."""
        return self.open_order_summary.pending_risk

    @property
    def pending_exposure(self) -> float | None:
        """Exposición (%) que añadirían las órdenes BUY pendientes. ``None`` sin equity."""
        return self.open_order_summary.pending_exposure_pct

    @property
    def order_book_is_complete(self) -> bool:
        """True solo si TODAS las órdenes pendientes son cuantificables (fail-closed)."""
        return self.order_book_measurement == MEASUREMENT_COMPLETE

    @property
    def data_is_fresh(self) -> bool:
        """True solo si la frescura de datos es explícitamente ``fresh`` (fail-closed)."""
        return self.data_freshness == DATA_FRESH

    @property
    def risk_is_complete(self) -> bool:
        """True solo si el riesgo agregado cubre TODAS las posiciones (fail-closed).

        V2.40.4: ``risk_used`` derivado de posiciones que no todas declaran su
        ``risk_amount`` es un SUELO. "Sé 100" no puede leerse como "el total es 100".
        """
        return self.risk_measurement == MEASUREMENT_COMPLETE

    @property
    def exposure_is_complete(self) -> bool:
        """True solo si la exposición cubre TODAS las posiciones (fail-closed)."""
        return self.exposure.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "capital": self.capital,
            "cash": self.cash,
            "equity": self.equity,
            "buyingPower": self.buying_power,
            "positions": [p.to_dict() for p in self.positions],
            "openOrders": [o.to_dict() for o in self.open_orders],
            "openOrderCount": self.open_order_count,
            "reservedCash": self.reserved_cash,
            "availableCash": self.available_cash,
            "pendingRisk": self.pending_risk,
            "pendingExposurePct": self.pending_exposure,
            "orderBookMeasurement": self.order_book_measurement,
            "dailyPnl": self.daily_pnl,
            "realizedPnl": self.realized_pnl,
            "unrealizedPnl": self.unrealized_pnl,
            "riskUsed": self.risk_used,
            "riskBudget": self.risk_budget,
            "riskRemaining": self.risk_remaining,
            "riskMeasurement": self.risk_measurement,
            "exposure": self.exposure.to_dict(),
            "drawdownPct": self.drawdown_pct,
            "activeStrategies": list(self.active_strategies),
            "marketRegime": self.market_regime,
            "lastReconciliation": self.last_reconciliation,
            "dataFreshness": self.data_freshness,
            "asOf": self.as_of,
        }


def _coerce_position(raw: Any) -> PortfolioPosition | None:
    """Normaliza una posición (dataclass, Mapping o atributo) a ``PortfolioPosition``."""
    if isinstance(raw, PortfolioPosition):
        return raw
    if isinstance(raw, dict):
        instrument_id = raw.get("instrumentId") or raw.get("instrument_id")
        qty = _finite(raw.get("quantity"))
        if not isinstance(instrument_id, str) or not instrument_id.strip() or qty is None:
            return None
        return PortfolioPosition(
            instrument_id=instrument_id.strip(),
            quantity=qty,
            market_value=_finite(raw.get("marketValue") or raw.get("market_value")),
            sector=raw.get("sector"),
            unrealized_pnl=_finite(raw.get("unrealizedPnl") or raw.get("unrealized_pnl")),
            risk_amount=_finite(raw.get("riskAmount") or raw.get("risk_amount")),
        )
    instrument_id = getattr(raw, "instrument_id", None) or getattr(raw, "instrumentId", None)
    qty = _finite(getattr(raw, "quantity", None))
    if not isinstance(instrument_id, str) or not instrument_id.strip() or qty is None:
        return None
    return PortfolioPosition(
        instrument_id=instrument_id.strip(),
        quantity=qty,
        market_value=_finite(getattr(raw, "market_value", None) or getattr(raw, "marketValue", None)),
        sector=getattr(raw, "sector", None),
        unrealized_pnl=_finite(
            getattr(raw, "unrealized_pnl", None) or getattr(raw, "unrealizedPnl", None)
        ),
        risk_amount=_finite(getattr(raw, "risk_amount", None) or getattr(raw, "riskAmount", None)),
    )


def build_auto_portfolio_snapshot(
    *,
    account_id: str,
    capital: Any = None,
    cash: Any = None,
    equity: Any = None,
    buying_power: Any = None,
    positions: Any = (),
    open_orders: Any = (),
    order_book_measurement: Any = None,
    daily_pnl: Any = None,
    realized_pnl: Any = None,
    unrealized_pnl: Any = None,
    risk_used: Any = None,
    risk_budget: Any = None,
    risk_measurement: Any = None,
    drawdown_pct: Any = None,
    active_strategies: Any = (),
    market_regime: Any = None,
    last_reconciliation: Any = RECON_UNKNOWN,
    data_freshness: Any = DATA_UNKNOWN,
    as_of: str = "",
) -> AutoPortfolioSnapshot:
    """Construye la foto canónica, normalizando inputs y derivando la exposición.

    - Posiciones inválidas (sin id o sin cantidad finita) se descartan (fail-closed).
    - ``open_orders`` se normaliza a tupla de ``OpenOrder``. La ``order_book_measurement``
      se deriva del agregado (``summarize_open_orders``) salvo que el llamante la afirme
      explícitamente; un libro vacío es ``COMPLETE`` (no hay pendientes que cuantificar).
    - ``risk_used`` se suma desde los ``risk_amount`` de las posiciones si no se aporta
      explícitamente (la foto no inventa riesgo: ausente ⇒ ``None``, no 0) y su
      ``risk_measurement`` declara si TODAS las posiciones aportaron su riesgo
      (V2.40.4: ``COMPLETE``/``PARTIAL``/``UNKNOWN``; nunca un suelo disfrazado de total).
    - ``exposure`` se deriva con ``aggregate_exposure`` (con su propio ``measurement``).
    - ``active_strategies`` se normaliza a tuple de str no vacíos (orden estable, sin
      duplicados).
    """
    pos_tuple = tuple(
        p for p in (_coerce_position(p) for p in (positions or ())) if p is not None
    )

    explicit_used = _non_negative(risk_used)
    measurable = [p for p in pos_tuple if p.quantity > 0]
    declared = [p for p in measurable if p.risk_amount is not None]

    used = explicit_used
    if used is None and declared:
        used = _round4(sum(_non_negative(p.risk_amount) or 0.0 for p in declared))

    # Un ``risk_used`` explícito es una AFIRMACIÓN del llamante ⇒ medido. Derivado, el
    # estado es el de las posiciones: todas declaran ⇒ COMPLETE; unas sí y otras no ⇒
    # PARTIAL; ninguna ⇒ UNKNOWN. Sin posiciones no hay nada que medir ⇒ COMPLETE.
    derived_measurement = (
        MEASUREMENT_COMPLETE
        if explicit_used is not None
        else measurement_from_counts(
            valued=len(declared), unvalued=len(measurable) - len(declared)
        )
    )
    resolved_measurement = coerce_measurement(risk_measurement) or derived_measurement

    strategies = tuple(dict.fromkeys(str(s).strip() for s in (active_strategies or ()) if str(s).strip()))

    orders_tuple = tuple(
        o for o in (coerce_open_order(raw) for raw in (open_orders or ())) if o is not None
    )
    resolved_order_book = coerce_measurement(order_book_measurement) or summarize_open_orders(
        orders_tuple, equity=_finite(equity)
    ).measurement

    return AutoPortfolioSnapshot(
        account_id=str(account_id).strip(),
        capital=_finite(capital),
        cash=_finite(cash),
        equity=_finite(equity),
        buying_power=_finite(buying_power),
        positions=pos_tuple,
        open_orders=orders_tuple,
        order_book_measurement=resolved_order_book,
        daily_pnl=_finite(daily_pnl),
        realized_pnl=_finite(realized_pnl),
        unrealized_pnl=_finite(unrealized_pnl),
        risk_used=used,
        risk_budget=_non_negative(risk_budget),
        risk_measurement=resolved_measurement,
        exposure=aggregate_exposure(pos_tuple, equity=_finite(equity)),
        drawdown_pct=_finite(drawdown_pct),
        active_strategies=strategies,
        market_regime=str(market_regime).strip() if market_regime else None,
        last_reconciliation=str(last_reconciliation or RECON_UNKNOWN),
        data_freshness=str(data_freshness or DATA_UNKNOWN),
        as_of=as_of,
    )
