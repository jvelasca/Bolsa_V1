"""`§8-a` — Reporte financiero OOS por `(estrategia × instrumento)`, coste-ajustado.

Origen: hueco **`§8` (Validación OOS por valor)** de la auditoría profundizada
(`auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md` §8). El scorer OOS del replay
AUTO (`replay_oos.ScoreReport`) mide **R** —múltiplos de riesgo— y es **coste-ciego**: no
hay retorno de dinero, ni drawdown, ni Sharpe, ni profit factor, ni dimensión
`(estrategia, instrumento)`. Ocupar el puesto #1 de Finalistas **no** demuestra
rentabilidad; este módulo produce la evidencia de **dinero** que faltaba.

Qué calcula (por grupo `(strategy_version, symbol)` y agregado):

* ``grossReturnPct`` / ``netReturnPct`` — retorno sobre el capital comprometido, bruto y
  **neto de costes** (``net ≤ gross`` por construcción).
* ``maxDrawdownPct`` — máxima caída de la curva de equity realizada (sobre el neto).
* ``hitRate`` — fracción de round-trips con PnL neto positivo.
* ``profitFactor`` — ganancias brutas / pérdidas brutas del **neto**; ``None`` (nunca
  ``∞``) cuando no hay pérdidas: ``inf`` no es JSON-serializable ni comparable.
* ``sharpe`` — media/desviación de los retornos por operación, **cuando proceda**
  (``n ≥ min_trades`` y desviación ``> 0``); en otro caso ``None``.
* ``commissionPaid`` / ``slippagePaid`` — coste **modelado** aplicado (overlay explícito).
* ``netReturnPctAtStress`` — el neto bajo costes escalados (sensibilidad a costes).
* ``trades`` — número de round-trips cerrados.

Diseño (alineado con el resto del proyecto):

* **Puro y determinista**: sin DB, red ni reloj. Entran filles, sale un reporte.
* **Fail-closed / honesto** (doctrina «Sin dato todavía», ``UNKNOWN ≠ 0``): con menos de
  ``min_trades`` round-trips cerrados **todos** los ratios del grupo son ``None`` y el
  grupo se declara en ``unmeasured`` — **nunca** se rellena con ``0``.
* **Nunca un punto donde sólo hay banda**: mientras la banda de ``K`` sorteos del venue
  cruce el cero (``v2.88.16.3``), el reporte declara ``pointCitable = False``. Un reporte
  financiero **no** puede presentar como propiedad del motor un punto que no lo es.
* **Costes explícitos, no dobles**: el overlay (``commission_bps`` + ``slippage_bps``) es
  el coste **modelado**. Los filles del SIM ya llevan **embebida** la fricción del venue
  (``applied_cost`` / ``reference_mid``): esa fricción **medida** se reporta aparte y **no**
  se suma aquí (evitar la doble contabilización).
* **Sold-out por round-trip FIFO**: los round-trips se cierran al vender contra lo abierto;
  el exceso de una venta se ignora (no se fabrica una venta en corto). Misma contabilidad
  que ``strategy_observed_metrics``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

__all__ = [
    "DEFAULT_COMMISSION_BPS",
    "DEFAULT_MIN_TRADES",
    "DEFAULT_SLIPPAGE_BPS",
    "DEFAULT_STRESS_MULTIPLIER",
    "GROUP_AGGREGATE_KEY",
    "CostOverlay",
    "GroupMetrics",
    "OosFill",
    "OosFinanceReport",
    "build_oos_finance_report",
]


#: Muestra mínima para que un ratio sea decisorio (misma doctrina que el observado de la
#: estrategia activa: por debajo, evidencia anecdótica ⇒ ``None``, jamás ``0``).
DEFAULT_MIN_TRADES = 10
#: Coste **modelado** por defecto (puntos básicos): comisión + deslizamiento.
DEFAULT_COMMISSION_BPS = 10.0
DEFAULT_SLIPPAGE_BPS = 5.0
#: Factor de estrés por defecto para la sensibilidad a costes (``2×`` los bps).
DEFAULT_STRESS_MULTIPLIER = 2.0
#: Clave reservada del grupo agregado (no colisiona con ``(version, symbol)`` reales).
GROUP_AGGREGATE_KEY = ("__ALL__", "__ALL__")

#: Razón declarada de ``pointCitable = False`` mientras no se cite la banda ``K``.
_POINT_CITABLE_REASON = (
    "El replay OOS es un sorteo del venue: la banda de K=12 sorteos cruza el cero "
    "(v2.88.16.3) ⇒ el punto NO es una propiedad del motor. Cítese la banda, no el punto."
)


@dataclass(frozen=True, slots=True)
class CostOverlay:
    """Coste **modelado** aplicado a cada round-trip (comisión + deslizamiento, en bps)."""

    commission_bps: float = DEFAULT_COMMISSION_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("los bps de coste no pueden ser negativos")

    def scaled(self, multiplier: float) -> CostOverlay:
        """Overlay con los bps multiplicados (para la sensibilidad a costes)."""
        if multiplier < 0:
            raise ValueError("el multiplicador de estrés no puede ser negativo")
        return CostOverlay(
            commission_bps=self.commission_bps * multiplier,
            slippage_bps=self.slippage_bps * multiplier,
        )

    def bps(self) -> float:
        """Bps totales por lado del round-trip (comisión + deslizamiento)."""
        return self.commission_bps + self.slippage_bps


@dataclass(frozen=True, slots=True)
class OosFill:
    """Fill OOS mínimo para reconstruir el dinero (no lleva R: lleva precio y cantidad)."""

    symbol: str
    strategy_version: str | None
    side: str  # "buy" | "sell"
    quantity: float
    price: float
    direction: str = "long"
    #: H1 — identidad EXACTA de la estrategia (``preset_key``). Clave ADITIVA de la unión con
    #: el TOP/feedback; ``None`` = hueco declarado (el fill no la declara), **nunca** ``""``.
    strategy_preset_key: str | None = None

    def key(self) -> tuple[str | None, str]:
        return (self.strategy_version, self.symbol)


@dataclass(frozen=True, slots=True)
class GroupMetrics:
    """Métricas financieras de un grupo `(estrategia, instrumento)` (o del agregado)."""

    trades: int
    committed_capital: float
    gross_return_pct: float | None
    net_return_pct: float | None
    net_return_pct_at_stress: float | None
    max_drawdown_pct: float | None
    hit_rate: float | None
    profit_factor: float | None
    sharpe: float | None
    commission_paid: float
    slippage_paid: float
    #: H1 — identidad EXACTA de la estrategia del grupo (``preset_key``); ``None`` en el
    #: agregado o cuando los filles no la declaran (hueco declarado, nunca fabricado).
    strategy_preset_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": self.trades,
            "committedCapital": round(self.committed_capital, 6),
            "grossReturnPct": _rounded(self.gross_return_pct),
            "netReturnPct": _rounded(self.net_return_pct),
            "netReturnPctAtStress": _rounded(self.net_return_pct_at_stress),
            "maxDrawdownPct": _rounded(self.max_drawdown_pct),
            "hitRate": _rounded(self.hit_rate),
            "profitFactor": _rounded(self.profit_factor),
            "sharpe": _rounded(self.sharpe),
            "commissionPaid": round(self.commission_paid, 6),
            "slippagePaid": round(self.slippage_paid, 6),
            "strategyPresetKey": self.strategy_preset_key,
        }


@dataclass(frozen=True, slots=True)
class OosFinanceReport:
    """Reporte financiero OOS reproducible, con huecos declarados y banda citada."""

    groups: tuple[tuple[tuple[str | None, str], GroupMetrics], ...]
    aggregate: GroupMetrics
    min_trades: int
    stress_multiplier: float
    unmeasured: tuple[str, ...]
    point_citable: bool
    point_citable_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "minTrades": self.min_trades,
            "stressMultiplier": self.stress_multiplier,
            "pointCitable": self.point_citable,
            "pointCitableReason": self.point_citable_reason,
            "unmeasured": list(self.unmeasured),
            "unmeasuredCount": len(self.unmeasured),
            "aggregate": self.aggregate.to_dict(),
            "groups": [
                {
                    "strategyVersion": key[0],
                    "symbol": key[1],
                    **metrics.to_dict(),
                }
                for key, metrics in self.groups
            ],
        }


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _round_trips(
    fills: Sequence[OosFill],
) -> tuple[list[float], list[float], float]:
    """Reconstruye round-trips FIFO.

    Devuelve ``(gross_pnls, entry_values, committed_capital)``: el PnL **bruto** de cada
    round-trip, el valor de entrada de cada uno (base del retorno y del Sharpe) y el
    capital comprometido total (denominador del retorno y del drawdown). El exceso de una
    venta sobre lo abierto se ignora (no se fabrica una venta en corto).
    """
    open_lots: deque[tuple[float, float]] = deque()  # (qty, price)
    gross_pnls: list[float] = []
    entry_values: list[float] = []
    committed_total = 0.0
    for fill in fills:
        qty = float(fill.quantity)
        price = float(fill.price)
        if qty <= 0 or price <= 0:
            continue
        if fill.side == "buy":
            open_lots.append((qty, price))
            continue
        # sell: realiza FIFO contra lo abierto.
        remaining = qty
        while remaining > 0 and open_lots:
            lot_qty, lot_price = open_lots[0]
            matched = min(remaining, lot_qty)
            gross_pnls.append((price - lot_price) * matched)
            entry_values.append(lot_price * matched)
            committed_total += lot_price * matched
            remaining -= matched
            if matched == lot_qty:
                open_lots.popleft()
            else:
                open_lots[0] = (lot_qty - matched, lot_price)
    return gross_pnls, entry_values, committed_total


def _costs_for(
    entry_values: Sequence[float], overlay: CostOverlay
) -> tuple[list[float], float, float]:
    """Coste modelado por round-trip (proporcional al valor de entrada) y su desglose.

    El coste se aplica **una vez** por round-trip, proporcional al **valor de entrada**
    (comisión y deslizamiento del capital ida — el modelo declarado, no la fricción del
    venue, que ya va embebida en el precio del fill).
    """
    rate = overlay.bps() / 10_000.0
    commission_rate = overlay.commission_bps / 10_000.0
    slippage_rate = overlay.slippage_bps / 10_000.0
    gross = sum(entry_values)
    costs = [value * rate for value in entry_values]
    return costs, gross * commission_rate, gross * slippage_rate


def _max_drawdown_pct(net_pnls: Sequence[float], committed_total: float) -> float | None:
    if not net_pnls or committed_total <= 0:
        return None
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in net_pnls:
        running += pnl
        peak = max(peak, running)
        dd = ((peak - running) / committed_total) * 100.0
        max_dd = max(max_dd, dd)
    return max_dd


def _profit_factor(net_pnls: Sequence[float]) -> float | None:
    gross_profit = sum(pnl for pnl in net_pnls if pnl > 0)
    gross_loss = -sum(pnl for pnl in net_pnls if pnl < 0)
    if gross_loss > 0:
        return gross_profit / gross_loss
    # Sin pérdidas el profit factor es indefinido (∞). ``None``, nunca ``inf``.
    return None


def _sharpe(
    net_pnls: Sequence[float], entry_values: Sequence[float], min_trades: int
) -> float | None:
    """Media/desviación de los retornos por operación, cuando proceda (n≥min, vol>0)."""
    returns = [
        pnl / value for pnl, value in zip(net_pnls, entry_values, strict=False) if value > 0
    ]
    if len(returns) < max(2, min_trades):
        return None
    vol = pstdev(returns)
    if vol <= 0:
        return None
    return mean(returns) / vol


def _metrics_from_trips(
    gross_pnls: Sequence[float],
    entry_values: Sequence[float],
    committed_total: float,
    overlay: CostOverlay,
    stress_overlay: CostOverlay,
    min_trades: int,
    strategy_preset_key: str | None = None,
) -> GroupMetrics:
    trades = len(gross_pnls)
    costs, commission_paid, slippage_paid = _costs_for(entry_values, overlay)
    stress_costs, _, _ = _costs_for(entry_values, stress_overlay)
    net_pnls = [gross - cost for gross, cost in zip(gross_pnls, costs, strict=False)]
    stress_pnls = [gross - cost for gross, cost in zip(gross_pnls, stress_costs, strict=False)]

    if trades < max(1, min_trades) or committed_total <= 0:
        # Fail-closed: muestra anecdótica ⇒ sin ratios (jamás un 0 que finja medición).
        return GroupMetrics(
            trades=trades,
            committed_capital=committed_total,
            gross_return_pct=None,
            net_return_pct=None,
            net_return_pct_at_stress=None,
            max_drawdown_pct=None,
            hit_rate=None,
            profit_factor=None,
            sharpe=None,
            commission_paid=commission_paid,
            slippage_paid=slippage_paid,
            strategy_preset_key=strategy_preset_key,
        )

    gross_total = sum(gross_pnls)
    net_total = sum(net_pnls)
    stress_total = sum(stress_pnls)
    wins = sum(1 for pnl in net_pnls if pnl > 0)
    return GroupMetrics(
        trades=trades,
        committed_capital=committed_total,
        gross_return_pct=(gross_total / committed_total) * 100.0,
        net_return_pct=(net_total / committed_total) * 100.0,
        net_return_pct_at_stress=(stress_total / committed_total) * 100.0,
        max_drawdown_pct=_max_drawdown_pct(net_pnls, committed_total),
        hit_rate=wins / trades,
        profit_factor=_profit_factor(net_pnls),
        sharpe=_sharpe(net_pnls, entry_values, min_trades),
        commission_paid=commission_paid,
        slippage_paid=slippage_paid,
        strategy_preset_key=strategy_preset_key,
    )


def build_oos_finance_report(
    fills: Iterable[OosFill],
    *,
    commission_bps: float = DEFAULT_COMMISSION_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    min_trades: int = DEFAULT_MIN_TRADES,
    stress_multiplier: float = DEFAULT_STRESS_MULTIPLIER,
) -> OosFinanceReport:
    """Construye el reporte financiero OOS por `(estrategia, instrumento)`.

    Determinista: los grupos salen ordenados por clave ``(strategy_version, symbol)`` y el
    agregado cubre **todos** los filles. Con menos de ``min_trades`` round-trips por grupo,
    ese grupo aparece en ``unmeasured`` con ratios ``None`` (nunca ``0``).
    """
    if min_trades < 1:
        raise ValueError("min_trades debe ser ≥ 1")
    overlay = CostOverlay(commission_bps=commission_bps, slippage_bps=slippage_bps)
    stress_overlay = overlay.scaled(stress_multiplier)

    buckets: dict[tuple[str | None, str], list[OosFill]] = {}
    for fill in fills:
        side = str(fill.side or "").strip().lower()
        if side not in {"buy", "sell"}:
            continue
        if float(fill.quantity) <= 0 or float(fill.price) <= 0:
            continue
        normalized = fill if side == fill.side else OosFill(
            symbol=fill.symbol,
            strategy_version=fill.strategy_version,
            side=side,
            quantity=fill.quantity,
            price=fill.price,
            direction=fill.direction,
            strategy_preset_key=fill.strategy_preset_key,
        )
        buckets.setdefault(normalized.key(), []).append(normalized)

    # FIFO **por grupo** (nunca mezclando símbolos): el agregado es la UNIÓN de los
    # round-trips de los grupos en orden estable, no un FIFO cruzado entre instrumentos.
    trip_map = {
        key: _round_trips(buckets[key]) for key in sorted(buckets, key=lambda k: (k[0] or "", k[1]))
    }
    # H1 — identidad EXACTA por grupo: el PRIMER ``preset_key`` NO vacío de sus filles (un
    # grupo sin identidad queda en ``None`` = hueco declarado, nunca fabricado).
    preset_by_key: dict[tuple[str | None, str], str | None] = {}
    for key, group_fills in buckets.items():
        preset = next(
            (
                str(fill.strategy_preset_key).strip()
                for fill in group_fills
                if fill.strategy_preset_key and str(fill.strategy_preset_key).strip()
            ),
            None,
        )
        preset_by_key[key] = preset
    groups = tuple(
        (
            key,
            _metrics_from_trips(
                *trip_map[key], overlay, stress_overlay, min_trades, preset_by_key.get(key)
            ),
        )
        for key in trip_map
    )
    agg_gross = [pnl for key in trip_map for pnl in trip_map[key][0]]
    agg_entries = [value for key in trip_map for value in trip_map[key][1]]
    agg_committed = sum(trip_map[key][2] for key in trip_map)
    aggregate = _metrics_from_trips(
        agg_gross, agg_entries, agg_committed, overlay, stress_overlay, min_trades
    )

    unmeasured: list[str] = []
    for key, metrics in groups:
        if metrics.trades < max(1, min_trades):
            unmeasured.append(
                f"{key[0] or '∅'}·{key[1]}: {metrics.trades} round-trips < min_trades "
                f"{min_trades} ⇒ ratios sin dato (Sin dato todavía)"
            )
        elif metrics.sharpe is None:
            unmeasured.append(
                f"{key[0] or '∅'}·{key[1]}: sharpe sin dato (varianza nula o muestra corta)"
            )
        elif metrics.profit_factor is None:
            unmeasured.append(
                f"{key[0] or '∅'}·{key[1]}: profit factor indefinido (sin pérdidas) ⇒ None"
            )
    if aggregate.trades < max(1, min_trades):
        unmeasured.append(
            f"AGREGADO: {aggregate.trades} round-trips < min_trades {min_trades} "
            "⇒ ratios sin dato (Sin dato todavía)"
        )

    return OosFinanceReport(
        groups=groups,
        aggregate=aggregate,
        min_trades=min_trades,
        stress_multiplier=stress_multiplier,
        unmeasured=tuple(unmeasured),
        point_citable=False,
        point_citable_reason=_POINT_CITABLE_REASON,
    )


def fills_from_replay(
    fill_rows: Iterable[Mapping[str, Any] | OosFill],
    *,
    symbol_key: str = "symbol",
    version_key: str = "strategyVersion",
    preset_key_key: str = "strategyPresetKey",
) -> list[OosFill]:
    """Adapta las filas de fill del replay (``ReplayFill.to_dict``) a ``OosFill``.

    Acepta diccionarios con las claves del replay (``symbol``/``side``/``quantity``/
    ``price``/``strategyVersion``/``direction``) o ``OosFill`` ya construidos. Los filles
    ilegibles se descartan (no deben romper el reporte). La identidad EXACTA
    (``strategyPresetKey``/``strategy_preset_key``, H1) se propaga si la fila la declara;
    ausente ⇒ ``None`` (hueco declarado, nunca ``""``).
    """
    out: list[OosFill] = []
    for row in fill_rows:
        if isinstance(row, OosFill):
            out.append(row)
            continue
        try:
            symbol = str(row[symbol_key])
            side = str(row["side"]).strip().lower()
            quantity = float(row["quantity"])
            price = float(row["price"])
        except (KeyError, TypeError, ValueError):
            continue
        version = row.get(version_key)
        preset = row.get(preset_key_key)
        if preset is None:
            preset = row.get("strategy_preset_key")
        preset_text = None if preset is None else str(preset).strip() or None
        out.append(
            OosFill(
                symbol=symbol,
                strategy_version=None if version is None else str(version),
                side=side,
                quantity=quantity,
                price=price,
                direction=str(row.get("direction", "long")),
                strategy_preset_key=preset_text,
            )
        )
    return out
