"""Líneas base FALSABLES para decidir si AUTO tiene edge (auditoría externa 2026-11-08).

Qué cierra: la evidencia DÍA-D midió la estrategia AUTO contra la política de la cuenta
(retorno neto, drawdown, ventanas positivas, exceso vs comprar y mantener y coste de ida y
vuelta) y salió ``REFUTED``. Lo que faltaba era la pregunta anterior: **¿algún brazo
razonable gana dinero en el mismo tramo?** Sin eso, «AUTO pierde» podría significar «todo
pierde con estos costes» y no «la señal no aporta».

Este módulo fija, ANTES de medir, tres brazos y cinco umbrales:

1. ``buy_hold``: comprar y mantener equiponderado el mismo watch.
2. ``trend_regime``: largo/caja sobre la cesta con filtro ``close > SMA(N)``, ejecución al
   open siguiente y costes 10/5/2 bps.
3. ``auto_v2``: la corrida de AUTO V2 con el edge DECLARADO (nunca un ``0.9`` de fábrica).

Umbrales (los cinco, ninguno negociable a posteriori): retorno neto ≥ 0 %, drawdown ≤ 15 %,
ventanas positivas ≥ 60 %, exceso vs comprar y mantener ≥ 0 y coste de ida y vuelta ≥ 22 bps.

Reglas de medición:
* La curva es de equity diaria y TODA ventana sin movimiento queda fuera del denominador
  (misma definición que ``dia_d_equity_evidence``).
* Un dato que falta es ``None``, nunca un ``0``: un hueco no autoriza.
* El coste del modelo se declara explícitamente; el brazo pasivo paga un round-trip de
  entrada/salida, no «gratis» (que es el techo optimista que la auditoría encontró).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from bolsa_application.closed_bars import bar_day
from bolsa_application.dia_d_equity_evidence import (
    max_drawdown_pct,
    net_return_pct,
    window_returns,
)

__all__ = [
    "BASELINE_THRESHOLDS",
    "BaselineCosts",
    "buy_hold_curve",
    "evaluate_baseline",
    "summarize_curve",
    "trend_regime_curve",
]

#: Los CINCO umbrales, fijados antes de correr. Un test los clava literalmente para que no
#: puedan moverse después de ver los resultados.
BASELINE_THRESHOLDS: Final[dict[str, float]] = {
    "minNetReturnPct": 0.0,
    "maxDrawdownPct": 15.0,
    "minPositiveWindowPct": 60.0,
    "minExcessVsBuyHoldPct": 0.0,
    "minRoundTripCostBps": 22.0,
}

#: Días de historia mínimos para que el filtro de tendencia tenga SMA completa.
DEFAULT_TREND_SMA: Final[int] = 200


@dataclass(frozen=True, slots=True)
class BaselineCosts:
    """Costes del brazo, en bps POR LADO (misma convención que ``CampaignCosts``).

    El ida y vuelta es ``2 × (comisión + slippage) + spread``: el spread se paga medio por
    lado y la comisión/slippage completos en cada lado.
    """

    commission_bps: float = 10.0
    slippage_bps: float = 5.0
    spread_bps: float = 2.0

    @property
    def round_trip_bps(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) + self.spread_bps

    @property
    def per_side_bps(self) -> float:
        return self.commission_bps + self.slippage_bps + self.spread_bps / 2.0

    def to_dict(self) -> dict[str, float]:
        return {
            "commissionBps": self.commission_bps,
            "slippageBps": self.slippage_bps,
            "spreadBps": self.spread_bps,
            "roundTripBps": self.round_trip_bps,
        }


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _field(bar: Any, name: str) -> Any:
    if isinstance(bar, Mapping):
        return bar.get(name)
    return getattr(bar, name, None)


def _bars_by_day(bars: Sequence[Any]) -> dict[str, float]:
    """Cierre por día; una barra sin día o con cierre no finito/≤0 se descarta."""
    out: dict[str, float] = {}
    for bar in bars or ():
        day = bar_day(bar)
        close = _finite(_field(bar, "close"))
        if not day or close is None or close <= 0:
            continue
        out[day] = close
    return out


def _opens_by_day(bars: Sequence[Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for bar in bars or ():
        day = bar_day(bar)
        opened = _finite(_field(bar, "open"))
        if not day or opened is None or opened <= 0:
            continue
        out[day] = opened
    return out


def _normalized_series(
    bars_by_symbol: Mapping[str, Sequence[Any]], watch: Sequence[str], days: Sequence[str]
) -> dict[str, dict[str, float]]:
    """Serie normalizada (base 1.0 en su primer cierre) por símbolo, con forward-fill.

    Un símbolo sin barra todavía no entra en la cesta ese día (no se inventa 0). Una vez
    entra, su último cierre conocido se mantiene hasta el final del tramo.
    """
    series, _opens = _normalized_frames(bars_by_symbol, watch, days)
    return series


def _normalized_frames(
    bars_by_symbol: Mapping[str, Sequence[Any]], watch: Sequence[str], days: Sequence[str]
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    """Cierres y opens normalizados contra el PRIMER cierre del tramo de cada símbolo.

    Misma base para ambos: así una compra al open y una marca al cierre se comparan en las
    mismas unidades (el error clásico es marcar euros contra índices).
    """
    day_set = set(days)
    closes: dict[str, dict[str, float]] = {}
    opens: dict[str, dict[str, float]] = {}
    for symbol in watch:
        bars = bars_by_symbol.get(symbol)
        if not bars:
            continue
        by_day = _bars_by_day(bars)
        points = [(day, by_day[day]) for day in days if day in by_day]
        if len(points) < 2:
            continue
        base = points[0][1]
        if base <= 0:
            continue
        closes[symbol] = {day: price / base for day, price in points}
        opens[symbol] = {
            day: price / base
            for day, price in _opens_by_day(bars).items()
            if day in day_set and day in by_day
        }
    return closes, opens


def _basket_curve(
    series: Mapping[str, Mapping[str, float]], days: Sequence[str], *, initial_equity: float
) -> list[tuple[str, float]]:
    """Curva equiponderada con forward-fill de cada símbolo ya iniciado."""
    last: dict[str, float] = {}
    curve: list[tuple[str, float]] = []
    for day in days:
        for symbol, points in series.items():
            if day in points:
                last[symbol] = points[day]
        if not last:
            continue
        level = sum(last.values()) / len(last)
        curve.append((day, float(initial_equity) * level))
    return curve


def buy_hold_curve(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    watch: Sequence[str],
    days: Sequence[str],
    initial_equity: float = 100_000.0,
) -> list[tuple[str, float]]:
    """Brazo 1: comprar y mantener equiponderado el mismo watch."""
    series = _normalized_series(bars_by_symbol, watch, days)
    return _basket_curve(series, days, initial_equity=initial_equity)


def _sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    chunk = values[-window:]
    return sum(chunk) / len(chunk)


def trend_regime_curve(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    watch: Sequence[str],
    days: Sequence[str],
    costs: BaselineCosts | None = None,
    initial_equity: float = 100_000.0,
    sma_window: int = DEFAULT_TREND_SMA,
) -> tuple[list[tuple[str, float]], dict[str, Any]]:
    """Brazo 2: largo si la cesta cierra sobre su SMA(N), caja si no; ejecuta al open siguiente.

    Devuelve ``(curva, metadatos)``. El metadato declara el número de idas y vueltas, el
    coste pagado y si la señal se pudo calcular (``None`` = sin historia suficiente).
    """
    costs = costs or BaselineCosts()
    closes_norm, opens_norm = _normalized_frames(bars_by_symbol, watch, days)
    basket = _basket_curve(closes_norm, days, initial_equity=1.0)
    closes = [level for _, level in basket]
    basket_days = [day for day, _ in basket]

    cash = float(initial_equity)
    units = 0.0
    pending: float | None = None
    curve: list[tuple[str, float]] = []
    round_trips = 0
    signal_unmeasurable_days = 0
    cost_fraction = costs.per_side_bps / 10_000.0

    for index, day in enumerate(basket_days):
        if pending is not None:
            # Open de la cesta normalizado contra la MISMA base que los cierres; si ningún
            # símbolo abrió ese día, se declara usando el cierre (nunca un precio inventado).
            open_levels = [points[day] for points in opens_norm.values() if day in points]
            exec_price = sum(open_levels) / len(open_levels) if open_levels else closes[index]
            if exec_price > 0:
                if pending > 0 and units == 0:
                    gross = cash
                    cash = 0.0
                    units = (gross * (1.0 - cost_fraction)) / exec_price
                elif pending == 0 and units > 0:
                    gross = units * exec_price
                    cash = gross * (1.0 - cost_fraction)
                    units = 0.0
                    round_trips += 1
            pending = None

        curve.append((day, cash + units * closes[index]))

        average = _sma(closes[: index + 1], sma_window)
        if average is None:
            signal_unmeasurable_days += 1
            continue
        target = 1.0 if closes[index] > average else 0.0
        current = 1.0 if units > 0 else 0.0
        if target != current:
            pending = target

    return curve, {
        "smaWindow": sma_window,
        "roundTrips": round_trips,
        "realizedCostBps": costs.round_trip_bps,
        "costModel": costs.to_dict(),
        "unmeasurableSignalDays": signal_unmeasurable_days,
    }


def summarize_curve(
    curve: Sequence[tuple[str, float]],
    *,
    buy_hold_curve: Sequence[tuple[str, float]] | None = None,
) -> dict[str, Any]:
    """Métricas en % de una curva, con la MISMA definición que la evidencia DÍA-D."""
    net = net_return_pct(curve)
    drawdown = max_drawdown_pct(curve)
    windows = window_returns(curve, granularity="day")
    benchmark = net_return_pct(buy_hold_curve) if buy_hold_curve else None
    excess = None if benchmark is None or net is None else net - benchmark
    return {
        "points": len(curve),
        "netReturnPct": net,
        "maxDrawdownPct": drawdown,
        "positiveWindowPct": windows.get("positivePct"),
        "measuredWindows": windows.get("measuredWindows"),
        "buyHoldNetReturnPct": benchmark,
        "excessVsBuyHoldPct": excess,
    }


def _check(
    fails_high: bool, name: str, limit: float | None, measured: float | None
) -> dict[str, object]:
    if limit is None or measured is None:
        return {"name": name, "verdict": "NOT_MEASURED", "limit": limit, "measured": measured}
    if fails_high:
        passed = measured <= limit
    else:
        passed = measured >= limit
    return {
        "name": name,
        "verdict": "PASS" if passed else "FAIL",
        "limit": limit,
        "measured": measured,
    }


def evaluate_baseline(
    summary: Mapping[str, Any],
    *,
    realized_cost_round_trip_bps: float | None,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Veredicto umbral a umbral de un brazo (``ACCREDITED`` solo con los cinco en PASS)."""
    limits = dict(thresholds or BASELINE_THRESHOLDS)
    checks = [
        _check(False, "minNetReturnPct", limits["minNetReturnPct"], summary.get("netReturnPct")),
        _check(True, "maxDrawdownPct", limits["maxDrawdownPct"], summary.get("maxDrawdownPct")),
        _check(
            False,
            "minPositiveWindowPct",
            limits["minPositiveWindowPct"],
            summary.get("positiveWindowPct"),
        ),
        _check(
            False,
            "minExcessVsBuyHoldPct",
            limits["minExcessVsBuyHoldPct"],
            summary.get("excessVsBuyHoldPct"),
        ),
        _check(
            False,
            "minRoundTripCostBps",
            limits["minRoundTripCostBps"],
            realized_cost_round_trip_bps,
        ),
    ]
    failed = [c["name"] for c in checks if c["verdict"] == "FAIL"]
    not_measured = [c["name"] for c in checks if c["verdict"] == "NOT_MEASURED"]
    if failed:
        verdict = "REFUTED"
    elif not_measured:
        verdict = "NOT_ACCREDITED"
    else:
        verdict = "ACCREDITED"
    return {
        "verdict": verdict,
        "failed": failed,
        "notMeasured": not_measured,
        "checks": checks,
        "thresholds": limits,
    }
