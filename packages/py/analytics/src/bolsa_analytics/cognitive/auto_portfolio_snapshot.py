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
    """Desglose de exposición en % de equity (total, por sector, por activo)."""

    total_pct: float | None
    by_sector: dict[str, float] = field(default_factory=dict)
    by_asset: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalPct": self.total_pct,
            "bySector": dict(self.by_sector),
            "byAsset": dict(self.by_asset),
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
    """
    values: list[tuple[str, float, str]] = []
    for pos in positions:
        mv = _safe_market_value(pos.market_value)
        if mv is None:
            continue
        sector = pos.sector if pos.sector and str(pos.sector).strip() else UNKNOWN_SECTOR
        values.append((str(pos.instrument_id), mv, str(sector)))

    if not values:
        return ExposureBreakdown(total_pct=None)

    denominator = _safe_market_value(equity)
    if denominator is None:
        denominator = sum(mv for _, mv, _ in values)
    if denominator is None or denominator <= 0:
        return ExposureBreakdown(total_pct=None)

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
    open_orders: int = 0
    daily_pnl: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    risk_used: float | None = None
    risk_budget: float | None = None
    exposure: ExposureBreakdown = field(default_factory=lambda: ExposureBreakdown(total_pct=None))
    drawdown_pct: float | None = None
    active_strategies: tuple[str, ...] = ()
    market_regime: str | None = None
    last_reconciliation: str = RECON_UNKNOWN
    data_freshness: str = DATA_UNKNOWN
    as_of: str = ""

    @property
    def risk_remaining(self) -> float | None:
        """Riesgo monetario aún disponible (``budget - used``). ``None`` si no hay budget.

        Nunca negativo: un riesgo usado por encima del presupuesto se clampa a 0.
        """
        budget = _non_negative(self.risk_budget)
        if budget is None:
            return None
        used = _non_negative(self.risk_used) or 0.0
        return _round4(max(0.0, budget - used))

    @property
    def data_is_fresh(self) -> bool:
        """True solo si la frescura de datos es explícitamente ``fresh`` (fail-closed)."""
        return self.data_freshness == DATA_FRESH

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "capital": self.capital,
            "cash": self.cash,
            "equity": self.equity,
            "buyingPower": self.buying_power,
            "positions": [p.to_dict() for p in self.positions],
            "openOrders": self.open_orders,
            "dailyPnl": self.daily_pnl,
            "realizedPnl": self.realized_pnl,
            "unrealizedPnl": self.unrealized_pnl,
            "riskUsed": self.risk_used,
            "riskBudget": self.risk_budget,
            "riskRemaining": self.risk_remaining,
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
    open_orders: Any = 0,
    daily_pnl: Any = None,
    realized_pnl: Any = None,
    unrealized_pnl: Any = None,
    risk_used: Any = None,
    risk_budget: Any = None,
    drawdown_pct: Any = None,
    active_strategies: Any = (),
    market_regime: Any = None,
    last_reconciliation: Any = RECON_UNKNOWN,
    data_freshness: Any = DATA_UNKNOWN,
    as_of: str = "",
) -> AutoPortfolioSnapshot:
    """Construye la foto canónica, normalizando inputs y derivando la exposición.

    - Posiciones inválidas (sin id o sin cantidad finita) se descartan (fail-closed).
    - ``risk_used`` se suma desde los ``risk_amount`` de las posiciones si no se aporta
      explícitamente (la foto no inventa riesgo: ausente ⇒ ``None``, no 0).
    - ``exposure`` se deriva con ``aggregate_exposure``.
    - ``active_strategies`` se normaliza a tuple de str no vacíos (orden estable, sin
      duplicados).
    """
    pos_tuple = tuple(
        p for p in (_coerce_position(p) for p in (positions or ())) if p is not None
    )

    used = _non_negative(risk_used)
    if used is None and pos_tuple:
        total_risk = sum(
            _non_negative(p.risk_amount) or 0.0 for p in pos_tuple if p.risk_amount is not None
        )
        used = _round4(total_risk) if any(p.risk_amount is not None for p in pos_tuple) else None

    strategies = tuple(dict.fromkeys(str(s).strip() for s in (active_strategies or ()) if str(s).strip()))

    return AutoPortfolioSnapshot(
        account_id=str(account_id).strip(),
        capital=_finite(capital),
        cash=_finite(cash),
        equity=_finite(equity),
        buying_power=_finite(buying_power),
        positions=pos_tuple,
        open_orders=max(0, int(open_orders or 0)),
        daily_pnl=_finite(daily_pnl),
        realized_pnl=_finite(realized_pnl),
        unrealized_pnl=_finite(unrealized_pnl),
        risk_used=used,
        risk_budget=_non_negative(risk_budget),
        exposure=aggregate_exposure(pos_tuple, equity=_finite(equity)),
        drawdown_pct=_finite(drawdown_pct),
        active_strategies=strategies,
        market_regime=str(market_regime).strip() if market_regime else None,
        last_reconciliation=str(last_reconciliation or RECON_UNKNOWN),
        data_freshness=str(data_freshness or DATA_UNKNOWN),
        as_of=as_of,
    )
