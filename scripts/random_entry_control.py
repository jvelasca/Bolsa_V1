#!/usr/bin/env python
"""Control de ENTRADAS ALEATORIAS con la geometría de AUTO (plantilla ``moderate``).

Pregunta que responde: la señal de entrada de AUTO, ¿aporta algo sobre elegir
instrumentos al azar con la MISMA geometría de salida, el MISMO dimensionado y el MISMO
replay? Si las entradas reales caen dentro de la distribución aleatoria, la señal de
entrada no aporta nada medible; si caen por debajo, es peor que el azar.

Geometría replicada del motor (leída del código, no de memoria):

* ``auto_v2_entry.V2Tunables`` — ``atr_multiplier=1.5``, ``target1_r=1.0``,
  ``target2_r=2.0``, ``max_risk_per_trade_pct=1.0``, ``max_position_pct=20``,
  ``max_sector_pct=40``, ``risk_budget_pct=6.0``, ``top_n=5``,
  ``max_entry_gap_atr=1.0``, ATR de 14 sesiones (``AtrService.period``).
* ``trading-policy-templates.ts`` / ``exit-policy.ts`` (``moderate``) — T1 reduce 30 %,
  T2 reduce 30 % de lo RESTANTE, trailing 1,0 R, ``maxHoldingPeriodDays=45``,
  ``maxOpenPositions=12``.

Ejecución: decisión con el cierre de ``t``, entrada en la apertura de ``t+1``; veto si
``|open(t+1) − close(t)| > 1,0 × ATR14(t)``. Sin anticipación.

Uso::

    python scripts/random_entry_control.py --selftest
    python scripts/random_entry_control.py --start 2022-01-27 --end 2026-10-26 \
        --seeds 100 --entries-csv entradas_auto.csv

Modos de entrada (``--mode`` o la presencia de ``--entries-csv``):

* ``random``   — entradas aleatorias uniformes; nº de candidatos/día calibrado para
                 producir ~ las mismas entradas que AUTO en la ventana.
* ``momentum`` — momentum 12-1, quintil superior, sin reentrar en lo ya abierto.
* ``csv``      — las entradas REALES de AUTO (``date,yahoo_symbol``, fecha = ejecución).

Control adicional: ``--exit-mode time-only`` quita stop y objetivos y sale a los 45 días,
para aislar cuánto pesa la geometría de salida frente a la entrada.

Modelos de gestión (``--exit-mode``):

* ``policy`` (alias ``geometry``) — el modelo SIMPLIFICADO con el que se midió el primer
  control: pico = máximo INTRADÍA, trailing armado en T1 y breakeven forzado en la entrada
  al tocar T1. Corta ganadores antes de tiempo.
* ``structural`` — el modelo que el ledger de AUTO demuestra: pico marcado con el CIERRE
  del día (``markAtExitR``/``mfeR``), trailing armado desde el primer día a
  ``pico − trail_r × riesgo`` (que nace igual al stop inicial y solo sube al subir el
  pico, o sea: breakeven automático cuando el pico supera +1 R, sin regla aparte) y sin
  breakeven forzado. Los cinco ejes son calibrables por separado
  (``--stop-trigger``, ``--watermark``, ``--arm``, ``--breakeven``, ``--partials``) y
  ``--calibrate`` barre contra los 192 ciclos reales del ledger.

Resultado medido de la calibración (2026-11-09, in-sample): el sesgo de +0,16 R/ciclo
**no era de geometría**. Los ganadores se reproducen casi exactos (sesgo −0,06 R) y todo
el residuo vive en los perdedores (+0,27 R), concentrado en los ciclos donde el motor
REAL tocó el stop y **no lo ejecutó** (``stopFiredNotFilled``, +0,35 R por ciclo). Eso
es arrastre de EJECUCIÓN, no una regla de salida: modelarlo sería modelar un fallo. El
residuo se declara en cada JSON (``fidelity.decomposition``) y no se disimula.

Lo que este simulador NO modela (se declara, no se disimula):
* el ``OpportunityRanker`` / ``min_edge`` (las entradas aleatorias no pasan por el ranker);
* divisa (las series se tratan en su propia moneda, sin convertir);
* sub-barros intradía: stop y objetivos se evalúan sobre el rango D1.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Parámetros de la geometría de AUTO (ver docstring) ────────────────────────────────
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
TARGET1_R = 1.0
TARGET2_R = 2.0
T1_REDUCE = 0.30
T2_REDUCE = 0.30
TRAIL_R = 1.0
MAX_HOLDING_DAYS = 45
RISK_PER_TRADE = 0.01
MAX_POSITION_PCT = 0.20
MAX_SECTOR_PCT = 0.40
RISK_BUDGET_PCT = 0.06
MAX_NEW_PER_DAY = 5
MAX_OPEN_POSITIONS = 12
MAX_ENTRY_GAP_ATR = 1.0
DEFAULT_COST_BPS = 12.7
INITIAL_EQUITY = 100_000.0

#: Presets de gestión. ``policy`` es el modelo simplificado del primer control (queda
#: reproducible: sin él no se puede comparar contra la medición anterior); ``structural``
#: es el que reproduce el ratchet REAL de AUTO (pico al cierre, trail 1 R, sin breakeven
#: forzado: la subida a breakeven sale sola del trail cuando el pico pasa de +1 R).
EXIT_PRESETS: dict[str, dict[str, str]] = {
    "policy": {
        "watermark": "high",
        "breakeven": "t1",
        "arm": "t1",
        "partials": "t1t2",
        "stopTrigger": "close",
    },
    "structural": {
        "watermark": "close",
        "breakeven": "none",
        "arm": "always",
        "partials": "t1t2",
        "stopTrigger": "touch",
    },
}
#: ``geometry`` era el nombre histórico del preset ``policy`` (compatibilidad de CLI).
EXIT_ALIASES = {"geometry": "policy"}

WATERMARK_CHOICES = ("high", "close")
BREAKEVEN_CHOICES = ("none", "t1")
ARM_CHOICES = ("t1", "always")
PARTIALS_CHOICES = ("none", "t1", "t1t2")
STOP_TRIGGER_CHOICES = ("close", "touch")


# ── Carga de datos ───────────────────────────────────────────────────────────────────
def _normalized_url(raw: str) -> str:
    url = raw.strip().strip('"').split("?")[0]
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def _database_url(explicit: str | None) -> str:
    if explicit:
        return _normalized_url(explicit)
    env = os.environ.get("DATABASE_URL")
    if env:
        return _normalized_url(env)
    dotenv = Path(__file__).resolve().parents[1] / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return _normalized_url(line.split("=", 1)[1])
    raise RuntimeError("Falta DATABASE_URL (entorno o .env).")


def load_prices(
    database_url: str, start: str, end: str, warmup_days: int = 420
) -> tuple[dict[str, list[tuple]], dict[str, str], list]:
    """Barras D1 por ``yahoo_symbol`` + sector por símbolo (SOLO lectura).

    Devuelve ``series[symbol] = [(day_ordinal, open, high, low, close), ...]`` ordenado,
    ``sectors[symbol]`` y el calendario global (lista de ``date``) con warm-up.
    """
    from sqlalchemy import create_engine, text

    warmup = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    query = text(
        """
        select coalesce(i.yahoo_symbol, i.symbol) as symbol,
               b.timestamp::date as day,
               b.open::float8 as open, b.high::float8 as high,
               b.low::float8 as low, b.close::float8 as close,
               i.sector as sector
        from ohlcv_bars b
        join instruments i on i.id = b.instrument_id
        where b.timeframe::text = '1d'
          and i.is_active
          and b.timestamp >= cast(:warmup as timestamptz)
          and b.timestamp <= cast(:end as timestamptz)
        order by 1, 2
        """
    )
    with create_engine(database_url).connect() as conn:
        frame = pd.read_sql(query, conn, params={"warmup": warmup, "end": end})

    frame["day"] = pd.to_datetime(frame["day"])
    frame = frame.drop_duplicates(["symbol", "day"], keep="last")

    series: dict[str, list[tuple]] = {}
    sectors: dict[str, str] = {}
    days: set = set()
    for symbol, group in frame.groupby("symbol"):
        group = group.sort_values("day")
        sector = group["sector"].dropna()
        sectors[str(symbol)] = str(sector.iloc[0]) if len(sector) else "UNKNOWN"
        rows: list[tuple] = []
        for row in group.itertuples(index=False):
            o, h, low, c = float(row.open), float(row.high), float(row.low), float(row.close)
            if not all(math.isfinite(v) and v > 0 for v in (o, h, low, c)):
                continue
            day = row.day.date()
            days.add(day)
            rows.append((day, o, h, low, c))
        if rows:
            series[str(symbol)] = rows
    return series, sectors, sorted(days)


def atr_series(bars: list[tuple], period: int = ATR_PERIOD) -> dict:
    """ATR de Wilder (idéntico a ``compute_atr``: semilla SMA y suavizado recursivo)."""
    out: dict = {}
    atr: float | None = None
    prev_close: float | None = None
    trs: list[float] = []
    for index, (day, _o, high, low, close) in enumerate(bars):
        if prev_close is None:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(true_range)
        prev_close = close
        if index + 1 < period:
            continue
        if atr is None:
            atr = sum(trs[index - period + 1 : index + 1]) / period
        else:
            atr = (atr * (period - 1) + true_range) / period
        out[day] = atr
    return out


def momentum_series(bars: list[tuple], lookback: int = 252, skip: int = 21) -> dict:
    """Momentum 12-1: ``close[t-21] / close[t-252] − 1`` sobre la serie propia."""
    closes = [row[4] for row in bars]
    out: dict = {}
    for index, (day, *_rest) in enumerate(bars):
        if index - skip < 0 or index - lookback < 0:
            continue
        base = closes[index - lookback]
        if base <= 0:
            continue
        out[day] = closes[index - skip] / base - 1.0
    return out


# ── Motor ───────────────────────────────────────────────────────────────────────────
@dataclass
class Position:
    symbol: str
    sector: str
    entry_day: Any
    entry_index: int
    entry_price: float
    initial_qty: float
    qty: float
    risk_per_share: float
    stop: float
    target1: float
    target2: float
    t1_done: bool = False
    t2_done: bool = False
    trail_stop: float | None = None
    high_water: float = 0.0
    realized_r: float = 0.0
    friction_cost: float = 0.0
    pending_fraction: float = 0.0
    pending_reason: str = ""
    exit_day: Any = None
    exit_reason: str = ""
    closed: bool = False


@dataclass
class Pending:
    symbol: str
    sector: str
    decision_close: float
    atr: float
    qty: float
    risk_per_share: float
    reserved_risk: float
    reserved_notional: float


@dataclass
class Result:
    mode: str
    net_pct: float
    cagr_pct: float
    max_dd_pct: float
    sharpe: float
    cycles: int
    expectancy_r: float
    net_expectancy_r: float
    hit_rate: float
    payoff: float
    avg_exposure_pct: float
    entries: int
    gap_vetoes: int
    open_at_end: int
    skipped: dict = field(default_factory=dict)
    equity: list[float] = field(default_factory=list)


class Simulation:
    """Un libro, una geometría, distintas reglas de ENTRADA."""

    def __init__(
        self,
        *,
        series: dict[str, list[tuple]],
        sectors: dict[str, str],
        calendar: list,
        start,
        end,
        universe: list[str],
        cost_bps: float,
        exit_mode: str = "policy",
        initial_equity: float = INITIAL_EQUITY,
        max_holding_days: int = MAX_HOLDING_DAYS,
        trail_r: float = TRAIL_R,
        watermark: str = "high",
        breakeven: str = "t1",
        arm: str = "t1",
        partials: str = "t1t2",
        stop_trigger: str = "close",
        check_accounting: bool = False,
    ) -> None:
        self.series_raw = series
        self.sectors = sectors
        self.calendar = calendar
        self.start = start
        self.end = end
        self.universe = [s for s in universe if s in series]
        self.cost = cost_bps / 1e4
        self.exit_mode = EXIT_ALIASES.get(exit_mode, exit_mode)
        self.initial_equity = initial_equity
        self.max_holding_days = max_holding_days
        self.trail_r = trail_r
        self.watermark = watermark
        self.breakeven = breakeven
        self.arm = arm
        self.partials = partials
        self.stop_trigger = stop_trigger
        self.check_accounting = check_accounting

        self.index_of = {day: i for i, day in enumerate(calendar)}
        self.bars: dict[str, dict] = {}
        self.atr: dict[str, dict] = {}
        self.momentum: dict[str, dict] = {}
        for symbol in self.universe:
            rows = series[symbol]
            self.bars[symbol] = {row[0]: (row[1], row[2], row[3], row[4]) for row in rows}
            self.atr[symbol] = atr_series(rows)
            self.momentum[symbol] = momentum_series(rows)

        self.start_index = self.index_of[start]
        self.end_index = self.index_of[end]
        self.initial_close = {
            symbol: self._last_close_before(symbol, start) for symbol in self.universe
        }
        # ATR y cierre "as-of" por índice de calendario: un valor que no cotiza el día de
        # decisión (fiesta en su mercado) usa su último dato, como hace el motor.
        self.asof: dict[str, dict[int, tuple[float, float]]] = {}
        for symbol in self.universe:
            table: dict[int, tuple[float, float]] = {}
            last_close = None
            last_atr = None
            own_atr = self.atr[symbol]
            own_bars = self.bars[symbol]
            for index, day in enumerate(calendar):
                bar = own_bars.get(day)
                if bar is not None:
                    last_close = bar[3]
                atr_value = own_atr.get(day)
                if atr_value is not None:
                    last_atr = atr_value
                if last_close is not None and last_atr is not None:
                    table[index] = (last_close, last_atr)
            self.asof[symbol] = table

    # -- utilidades de datos ---------------------------------------------------------
    def _last_close_before(self, symbol: str, day) -> float | None:
        rows = self.series_raw[symbol]
        last = None
        for row in rows:
            if row[0] >= day:
                break
            last = row[4]
        return last

    def _bar(self, symbol: str, day) -> tuple | None:
        return self.bars[symbol].get(day)

    def _days_held(self, position: Position, day) -> int:
        return (day - position.entry_day).days

    # -- coste -----------------------------------------------------------------------
    def _sell(self, position: Position, qty: float, price: float) -> float:
        """Vende ``qty`` y devuelve la caja neta (descontando fricción)."""
        gross = qty * price
        cost = gross * self.cost
        position.friction_cost += cost
        position.qty -= qty
        if position.qty <= 1e-9:
            position.qty = 0.0
        return gross - cost

    def _close_all(self, position: Position, price: float) -> tuple[float, float]:
        """Cierra el resto ANTES de tocar ``qty`` (si no, el R final se pierde).

        Devuelve ``(caja neta, riesgo liberado)``.
        """
        qty = position.qty
        if qty <= 0:
            return 0.0, 0.0
        final_r = self._final_r(position, price)
        cash_delta = self._sell(position, qty, price)
        position.realized_r = final_r
        return cash_delta, position.risk_per_share * qty

    def _book_r(self, position: Position, qty: float, price: float) -> None:
        fraction = qty / position.initial_qty
        position.realized_r += (price - position.entry_price) / position.risk_per_share * fraction

    # -- bucle ----------------------------------------------------------------------
    def run(
        self,
        *,
        mode: str,
        entries: dict | None = None,
        rng: np.random.Generator | None = None,
        lam: float = 0.0,
        momentum_quantile: float = 0.20,
        seed_label: str = "",
    ) -> Result:
        """Un pase completo del libro.

        Convención de ejecución, la MISMA en todos los modos (la que el ledger de AUTO
        demuestra: en 90 de 96 ciclos el stop se llenó a la apertura siguiente):
        se decide y se evalúa al CIERRE de ``t`` y se ejecuta en la APERTURA de ``t+1``.
        """
        cash = self.initial_equity
        positions: list[Position] = []
        pending: list[Pending] = []
        last_close: dict[str, float] = {}
        closed_r: list[float] = []
        closed_friction_r: list[float] = []
        self.trades: list[dict] = []
        equity_curve: list[float] = []
        exposure_sum = 0.0
        exposure_days = 0
        entries_taken = 0
        gap_vetoes = 0
        skipped: dict[str, int] = {}

        def note(reason: str, count: int = 1) -> None:
            skipped[reason] = skipped.get(reason, 0) + count

        def decide(index: int, day, next_day, equity: float) -> None:
            """Encola las entradas que se ejecutarán en la apertura de ``next_day``."""
            nonlocal pending
            # lo que de verdad ocupa cartera mañana: lo que no esté pendiente de salir
            live = [p for p in positions if p.pending_fraction < 1.0 - 1e-9]
            open_risk = sum(p.risk_per_share * p.qty for p in live)
            open_notional: dict[str, float] = {}
            for position in live:
                open_notional[position.sector] = open_notional.get(position.sector, 0.0) + (
                    position.qty * last_close.get(position.symbol, position.entry_price)
                )
            free_slots = MAX_OPEN_POSITIONS - len(live)
            if free_slots <= 0:
                note("sin_hueco", 1)
                return
            candidates = self._candidates(
                mode=mode,
                entries=entries,
                rng=rng,
                lam=lam,
                momentum_quantile=momentum_quantile,
                day=day,
                next_day=next_day,
                open_positions=live,
                note=note,
            )
            if not candidates:
                return
            reserved_risk = 0.0
            sector_notional = dict(open_notional)
            taken = 0
            for symbol in candidates:
                if taken >= MAX_NEW_PER_DAY:
                    note("tope_5_dia", 1)
                    continue
                if taken >= free_slots:
                    note("sin_hueco", 1)
                    continue
                bar_next = self._bar(symbol, next_day)
                asof = self.asof.get(symbol, {}).get(index)
                if bar_next is None:
                    note("sin_barra", 1)
                    continue
                if asof is None:
                    note("sin_atr", 1)
                    continue
                price_ref, atr = asof
                if atr <= 0:
                    note("sin_atr", 1)
                    continue
                risk_per_share = ATR_MULTIPLIER * atr + 2.0 * self.cost * price_ref
                if risk_per_share <= 0:
                    note("sin_atr", 1)
                    continue
                qty = RISK_PER_TRADE * equity / risk_per_share
                qty = min(qty, MAX_POSITION_PCT * equity / price_ref)
                remaining_risk = RISK_BUDGET_PCT * equity - open_risk - reserved_risk
                if remaining_risk <= 0:
                    note("riesgo_abierto_6pct", 1)
                    continue
                qty = min(qty, remaining_risk / risk_per_share)
                sector = self.sectors.get(symbol, "UNKNOWN")
                sector_cap = MAX_SECTOR_PCT * equity - sector_notional.get(sector, 0.0)
                if sector_cap <= 0:
                    note("sector_40pct", 1)
                    continue
                qty = min(qty, sector_cap / price_ref)
                if qty * price_ref < 1.0:
                    note("qty_nula", 1)
                    continue
                reserved = qty * risk_per_share
                pending.append(
                    Pending(
                        symbol=symbol,
                        sector=sector,
                        decision_close=price_ref,
                        atr=atr,
                        qty=qty,
                        risk_per_share=risk_per_share,
                        reserved_risk=reserved,
                        reserved_notional=qty * price_ref,
                    )
                )
                reserved_risk += reserved
                sector_notional[sector] = sector_notional.get(sector, 0.0) + qty * price_ref
                taken += 1

        # decisión del día ANTERIOR al inicio de la ventana: permite entrar el primer día
        if self.start_index > 0:
            pre_day = self.calendar[self.start_index - 1]
            for position in positions:
                bar = self._bar(position.symbol, pre_day)
                if bar is not None:
                    last_close[position.symbol] = bar[3]
            decide(self.start_index - 1, pre_day, self.calendar[self.start_index], self.initial_equity)

        for index in range(self.start_index, self.end_index + 1):
            day = self.calendar[index]

            # ── APERTURA: primero salidas decididas ayer, después entradas ──────────
            survivors = []
            for position in positions:
                if position.pending_fraction <= 0:
                    survivors.append(position)
                    continue
                bar = self._bar(position.symbol, day)
                if bar is None:
                    survivors.append(position)  # sin barra no se puede ejecutar: se reintenta
                    continue
                open_px = bar[0]
                fraction = min(position.pending_fraction, 1.0)
                if fraction >= 1.0 - 1e-9:
                    cash_delta, _released = self._close_all(position, open_px)
                    cash += cash_delta
                    closed_r.append(position.realized_r)
                    closed_friction_r.append(position.friction_cost / self._risk_amount(position))
                    self.trades.append(
                        {
                            "symbol": position.symbol,
                            "entry_day": str(position.entry_day),
                            "exit_day": str(day),
                            "reason": position.pending_reason,
                            "r": position.realized_r,
                            "friction_r": position.friction_cost / self._risk_amount(position),
                            "entry_price": position.entry_price,
                            "risk_per_share": position.risk_per_share,
                            "risk_pct": 100.0 * position.risk_per_share / position.entry_price,
                            "mfe_high_r": (
                                (position.high_water - position.entry_price) / position.risk_per_share
                            ),
                            "stop_at_exit_r": (
                                max(
                                    position.stop,
                                    position.trail_stop if position.trail_stop is not None else position.stop,
                                )
                                - position.entry_price
                            )
                            / position.risk_per_share,
                        }
                    )
                    continue
                qty = position.qty * fraction
                cash += self._sell(position, qty, open_px)
                self._book_r(position, qty, open_px)
                position.pending_fraction = 0.0
                survivors.append(position)
            positions = survivors

            for item in pending:
                bar = self._bar(item.symbol, day)
                if bar is None:
                    continue
                open_px = bar[0]
                if abs(open_px - item.decision_close) > MAX_ENTRY_GAP_ATR * item.atr:
                    gap_vetoes += 1
                    continue
                cash -= item.qty * open_px * (1.0 + self.cost)
                risk = ATR_MULTIPLIER * item.atr
                positions.append(
                    Position(
                        symbol=item.symbol,
                        sector=item.sector,
                        entry_day=day,
                        entry_index=index,
                        entry_price=open_px,
                        initial_qty=item.qty,
                        qty=item.qty,
                        risk_per_share=max(risk, 1e-9),
                        stop=open_px - risk,
                        target1=open_px + TARGET1_R * risk,
                        target2=open_px + TARGET2_R * risk,
                        high_water=open_px,
                        friction_cost=item.qty * open_px * self.cost,
                    )
                )
                entries_taken += 1
            pending = []

            # ── CIERRE: marcas, gestión y decisión de mañana ────────────────────────
            for symbol in self.universe:
                bar = self._bar(symbol, day)
                if bar is not None:
                    last_close[symbol] = bar[3]

            for position in positions:
                bar = self._bar(position.symbol, day)
                if bar is None:
                    continue
                _open_px, high, low, close = bar
                # Pico del trail: ``close`` = la marca que el motor persiste (``markAtExitR``,
                # ``mfeR`` del ledger están medidos al cierre); ``high`` = máximo intradía,
                # que sobreestima el pico que el motor llega a ver.
                mark = close if self.watermark == "close" else high
                position.high_water = max(position.high_water, mark)
                if position.pending_fraction > 0:
                    continue
                held = self._days_held(position, day)
                if self.exit_mode == "time-only":
                    if held >= self.max_holding_days:
                        position.pending_fraction = 1.0
                        position.pending_reason = "time"
                    continue

                stop_px = position.stop
                if position.trail_stop is not None:
                    stop_px = max(stop_px, position.trail_stop)
                if self.breakeven == "t1" and position.t1_done:
                    stop_px = max(stop_px, position.entry_price)  # breakeven forzado
                # Disparo del stop: ``touch`` = el mínimo del día perfora el nivel (lo que
                # hace el motor real: el nivel vive en el mercado y se ejecuta a la apertura
                # siguiente); ``close`` = solo si el CIERRE queda por debajo (modelo
                # simplificado del primer control, que subestima las pérdidas).
                triggered = low <= stop_px if self.stop_trigger == "touch" else close <= stop_px
                if triggered:
                    position.pending_fraction = 1.0
                    position.pending_reason = "stop"
                    continue
                if held >= self.max_holding_days:
                    position.pending_fraction = 1.0
                    position.pending_reason = "time"
                    continue
                # T1/T2: el toque se marca SIEMPRE (arma el trail y queda en el registro);
                # la reducción parcial solo si la política de parciales la incluye.
                if not position.t1_done and close >= position.target1:
                    position.t1_done = True
                    if self.partials in ("t1", "t1t2"):
                        position.pending_fraction = T1_REDUCE
                elif position.t1_done and not position.t2_done and close >= position.target2:
                    position.t2_done = True
                    if self.partials == "t1t2":
                        position.pending_fraction = T2_REDUCE
                armed = self.arm == "always" or position.t1_done
                if armed:
                    candidate = position.high_water - self.trail_r * position.risk_per_share
                    if position.trail_stop is None or candidate > position.trail_stop:
                        position.trail_stop = candidate

            invested = sum(p.qty * last_close.get(p.symbol, p.entry_price) for p in positions)
            equity = cash + invested
            equity_curve.append(equity)
            exposure_sum += invested / equity if equity > 0 else 0.0
            exposure_days += 1
            if self.check_accounting:
                if equity <= 0:
                    raise AssertionError(f"equity no positiva el {day}: {equity}")

            if index >= self.end_index:
                break
            decide(index, day, self.calendar[index + 1], equity)

        # métricas
        eq = pd.Series(equity_curve, index=pd.to_datetime([self.calendar[i] for i in range(self.start_index, self.start_index + len(equity_curve))]))
        returns = eq.pct_change().dropna()
        years = max(len(eq) / 252.0, 1e-9)
        drawdown = (eq / eq.cummax() - 1.0).min() if len(eq) else 0.0
        sd = returns.std()
        expectancy = float(np.mean(closed_r)) if closed_r else float("nan")
        net_expectancy = (
            float(np.mean(np.array(closed_r) - np.array(closed_friction_r))) if closed_r else float("nan")
        )
        wins = sum(1 for r in closed_r if r > 0)
        losses = [r for r in closed_r if r <= 0]
        gains = [r for r in closed_r if r > 0]
        payoff = float(np.mean(gains) / abs(np.mean(losses))) if gains and losses else float("nan")
        return Result(
            mode=f"{mode}{seed_label}",
            net_pct=100.0 * (eq.iloc[-1] / self.initial_equity - 1.0) if len(eq) else float("nan"),
            cagr_pct=100.0 * ((eq.iloc[-1] / self.initial_equity) ** (1.0 / years) - 1.0) if len(eq) else float("nan"),
            max_dd_pct=-100.0 * float(drawdown),
            sharpe=float(returns.mean() / sd * math.sqrt(252)) if sd and sd > 0 else float("nan"),
            cycles=len(closed_r),
            expectancy_r=expectancy,
            net_expectancy_r=net_expectancy,
            hit_rate=100.0 * wins / len(closed_r) if closed_r else float("nan"),
            payoff=payoff,
            avg_exposure_pct=100.0 * exposure_sum / max(exposure_days, 1),
            entries=entries_taken,
            gap_vetoes=gap_vetoes,
            open_at_end=len(positions),
            skipped=dict(skipped),
            equity=[float(v) for v in eq],
        )

    # -- helpers de contabilidad ----------------------------------------------------
    def _risk_amount(self, position: Position) -> float:
        amount = position.risk_per_share * position.initial_qty
        return amount if amount > 0 else 1e-9

    def _final_r(self, position: Position, exit_px: float) -> float:
        """R total del ciclo: parciales ya acumulados + lo que quedaba al precio de salida."""
        remaining_fraction = position.qty / position.initial_qty
        if remaining_fraction <= 1e-9:
            return position.realized_r
        return position.realized_r + (
            (exit_px - position.entry_price) / position.risk_per_share * remaining_fraction
        )

    # -- candidatos -----------------------------------------------------------------
    def _candidates(
        self,
        *,
        mode: str,
        entries: dict | None,
        rng: np.random.Generator | None,
        lam: float,
        momentum_quantile: float,
        day,
        next_day,
        open_positions: list[Position],
        note=None,
    ) -> list[str]:
        held = {position.symbol for position in open_positions}
        note = note or (lambda *args, **kwargs: None)
        if mode == "csv":
            wanted = list((entries or {}).get(next_day, ()))
            out: list[str] = []
            for symbol in wanted:
                if symbol in held:
                    note("ya_en_cartera")
                    continue
                if symbol in out:
                    note("duplicado_dia")
                    continue
                if symbol not in self.bars:
                    note("sin_serie")
                    continue
                out.append(symbol)
            return out

        eligible = [
            symbol
            for symbol in self.universe
            if symbol not in held and self._bar(symbol, day) is not None and day in self.atr.get(symbol, {})
        ]
        if not eligible:
            return []

        if mode == "momentum":
            scored = [
                (self.momentum[symbol][day], symbol)
                for symbol in eligible
                if day in self.momentum.get(symbol, {})
            ]
            if not scored:
                return []
            scored.sort(reverse=True)
            keep = max(1, int(len(scored) * momentum_quantile))
            return [symbol for _score, symbol in scored[:keep]]

        # random
        if rng is None:
            return []
        draws = int(rng.poisson(lam))
        if draws <= 0:
            return []
        draws = min(draws, len(eligible))
        chosen = rng.choice(np.array(eligible, dtype=object), size=draws, replace=False)
        # orden aleatorio: el tope de 5 entradas/día no debe favorecer alfabéticamente
        order = rng.permutation(len(chosen))
        return [str(chosen[i]) for i in order]


# ── Modos y calibración ─────────────────────────────────────────────────────────────
def load_entries_csv(path: Path) -> dict:
    out: dict = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "date" not in reader.fieldnames or "yahoo_symbol" not in reader.fieldnames:
            raise SystemExit(f"{path}: se esperan las columnas date,yahoo_symbol")
        for row in reader:
            try:
                day = pd.Timestamp(str(row["date"]).strip()).date()
            except Exception:  # noqa: BLE001
                raise SystemExit(f"{path}: fecha inválida {row['date']!r}") from None
            symbol = str(row["yahoo_symbol"]).strip()
            out.setdefault(day, []).append(symbol)
    return out


# ── Ledger real y calibración del modelo de salida ──────────────────────────────────
def _load_exporter() -> Any:
    """Carga ``export_auto_entries.py`` (hermano) para reutilizar su lectura del ledger.

    Se reutiliza a propósito: la clave de deduplicación (``symbol``, ``entryDay``,
    ``entryPrice``, ``exitDay``) y el mapa ``instruments.id → yahoo_symbol`` tienen que ser
    EXACTAMENTE los mismos que produjeron ``entradas_auto.csv``; duplicarlos aquí abriría
    la puerta a que el CSV y la calibración discrepen.
    """
    import importlib.util

    path = Path(__file__).with_name("export_auto_entries.py")
    spec = importlib.util.spec_from_file_location("export_auto_entries", path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_real_cycles(ledger_path: Path, database_url: str, start, end) -> dict:
    """Ciclos REALES de AUTO por ``(yahoo_symbol, entryDay)`` con su ``realizedR``.

    La clave lleva el ticker (no el ``instruments.id``) para poder cruzarla con los ciclos
    del simulador, que trabaja en el espacio de ``yahoo_symbol``. Un mismo par puede
    repetirse (reentradas); se guarda una lista y se consume una por ciclo simulado.
    """
    exporter = _load_exporter()
    cycles = exporter.load_ledger(ledger_path)
    kept, in_window, dropped = exporter.select_entries(cycles, str(start), str(end))
    ids = {str(c.get("symbol")) for c in kept if c.get("symbol")}
    symbol_map = exporter.load_symbol_map(database_url, ids)
    real: dict = {}
    skipped = 0
    for cycle in kept:
        raw_id = str(cycle.get("symbol"))
        symbol = symbol_map.get(raw_id)
        realized = cycle.get("realizedR")
        if symbol is None or realized is None:
            skipped += 1
            continue
        key = (symbol, str(cycle.get("entryDay")))
        real.setdefault(key, []).append(
            {
                "realizedR": float(realized),
                "mfeR": float(cycle["mfeR"]) if cycle.get("mfeR") is not None else None,
                "exitDay": str(cycle.get("exitDay")),
                "exitReason": cycle.get("exitReason"),
                "exitMechanism": cycle.get("exitMechanism"),
                "breakevenReached": bool(cycle.get("breakevenReached")),
                # Campos de EJECUCIÓN (no de geometría): explican por qué el motor real a
                # veces pierde más de 1 R aunque el stop nunca se movió. Se cargan para
                # poder DESCOMPONER el residuo en vez de esconderlo en la media.
                "stopFiredNotFilled": bool(cycle.get("stopFiredNotFilled")),
                "touchBeforeExit": cycle.get("touchBeforeExit"),
                "stopTouchDays": cycle.get("stopTouchDays"),
                "timelineDays": cycle.get("timelineDays"),
                "entryPrice": cycle.get("entryPrice"),
                "initialStop": cycle.get("initialStop"),
                "currentStopAtExitR": cycle.get("currentStopAtExitR"),
            }
        )
    return {
        "byKey": real,
        "cycles": len(kept),
        "inWindow": in_window,
        "duplicates": dropped,
        "skipped": skipped,
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return float("nan")
    ax = np.asarray(xs, dtype=float)
    ay = np.asarray(ys, dtype=float)
    if ax.std() <= 1e-12 or ay.std() <= 1e-12:
        return float("nan")
    return float(np.corrcoef(ax, ay)[0, 1])


def _match_rows(trades: list[dict], real: dict) -> dict:
    """Cruza los ciclos simulados con los reales y calcula el ajuste ciclo a ciclo."""
    pools = {key: list(rows) for key, rows in real["byKey"].items()}
    pairs: list[dict] = []
    unmatched_sim = 0
    for trade in trades:
        key = (str(trade["symbol"]), str(trade["entry_day"]))
        pool = pools.get(key)
        if not pool:
            unmatched_sim += 1
            continue
        truth = pool.pop(0)
        pairs.append(
            {
                "symbol": key[0],
                "entryDay": key[1],
                "simR": float(trade["r"]),
                "realR": truth["realizedR"],
                "mfeR": truth["mfeR"],
                "reason": trade["reason"],
                "frictionR": float(trade["friction_r"]),
                "realExitReason": truth["exitReason"],
                "stopFiredNotFilled": truth["stopFiredNotFilled"],
                "touchBeforeExit": truth["touchBeforeExit"],
                "riskPctSim": float(trade.get("risk_pct", float("nan"))),
                "realRiskPct": (
                    100.0
                    * (float(truth["entryPrice"]) - float(truth["initialStop"]))
                    / float(truth["entryPrice"])
                    if truth["entryPrice"] and truth["initialStop"]
                    else None
                ),
            }
        )
    unmatched_real = sum(len(v) for v in pools.values())
    sim_r = [p["simR"] for p in pairs]
    real_r = [p["realR"] for p in pairs]
    diffs = [s - t for s, t in zip(sim_r, real_r, strict=True)]

    def bucket(label: str, subset: list[dict]) -> dict:
        if not subset:
            return {"label": label, "n": 0, "bias": None, "rmse": None, "meanReal": None, "meanSim": None}
        ds = [p["simR"] - p["realR"] for p in subset]
        return {
            "label": label,
            "n": len(subset),
            "bias": float(np.mean(ds)),
            "rmse": float(np.sqrt(np.mean(np.square(ds)))),
            "meanReal": float(np.mean([p["realR"] for p in subset])),
            "meanSim": float(np.mean([p["simR"] for p in subset])),
        }

    decomposition = [
        bucket("todos", pairs),
        bucket("real ganador (R>0)", [p for p in pairs if p["realR"] > 0]),
        bucket("real perdedor (R<=0)", [p for p in pairs if p["realR"] <= 0]),
        bucket("stop disparado sin fill", [p for p in pairs if p["stopFiredNotFilled"]]),
        bucket("sin stop disparado-sin-fill", [p for p in pairs if not p["stopFiredNotFilled"]]),
        bucket(
            "tocado y no cruzado al cierre",
            [p for p in pairs if p["touchBeforeExit"] is False],
        ),
        bucket(
            "sin toque previo declarado",
            [p for p in pairs if p["touchBeforeExit"] is None],
        ),
        bucket("salida por tiempo", [p for p in pairs if p["realExitReason"] == "time_exit"]),
        bucket("salida por tesis", [p for p in pairs if p["realExitReason"] == "thesis_exit"]),
    ]
    risk = [
        (p["riskPctSim"], p["realRiskPct"])
        for p in pairs
        if p["realRiskPct"] is not None and math.isfinite(p["riskPctSim"])
    ]

    return {
        "pairs": pairs,
        "unmatchedSim": unmatched_sim,
        "unmatchedReal": unmatched_real,
        "bias": float(np.mean(diffs)) if diffs else float("nan"),
        "rmse": float(np.sqrt(np.mean(np.square(diffs)))) if diffs else float("nan"),
        "corr": _pearson(sim_r, real_r),
        "signAgreement": (
            float(np.mean([(s > 0) == (t > 0) for s, t in zip(sim_r, real_r, strict=True)]))
            if pairs
            else float("nan")
        ),
        "simExpectancy": float(np.mean(sim_r)) if sim_r else float("nan"),
        "realExpectancy": float(np.mean(real_r)) if real_r else float("nan"),
        "decomposition": decomposition,
        "riskPct": {
            "simMedian": float(np.median([r[0] for r in risk])) if risk else None,
            "realMedian": float(np.median([r[1] for r in risk])) if risk else None,
            "simMinusRealMedian": (
                float(np.median([s - t for s, t in risk])) if risk else None
            ),
        },
    }


def _match_trades(sim: Simulation, entries: dict, real: dict) -> dict:
    """Corre el modo CSV y devuelve el cruce ciclo a ciclo contra el ledger real.

    Los ciclos reales sin pareja (o al revés) se declaran: si el simulador saltó una
    entrada, el sesgo agregado no es comparable ciclo a ciclo.
    """
    result = sim.run(mode="csv", entries=entries)
    metrics = _match_rows(sim.trades, real)
    return {"result": result, **metrics}


def calibrate_exit_model(
    sim: Simulation,
    *,
    entries: dict,
    real: dict,
    trail_rs: list[float],
) -> dict:
    """Barrido escalonado del modelo de salida contra los ciclos REALES del ledger.

    Tres etapas (el espacio completo son 108 combinaciones y cada pasada cuesta un replay
    entero, así que se hace búsqueda escalonada y se declara como tal):

    1. ``watermark × breakeven × arm`` (8) con ``trail_r`` del preset y parciales T1/T2.
    2. ``trail_r`` sobre el mejor de (1).
    3. ``partials`` sobre el mejor de (2).

    Criterio de selección: menor RMSE ciclo a ciclo. El sesgo se reporta aparte porque
    puede compensarse entre ganadores y perdedores y un RMSE bajo con sesgo alto no es
    un ajuste bueno.
    """
    tried: dict[tuple, dict] = {}
    order: list[dict] = []

    def evaluate(
        stop_trigger: str,
        watermark: str,
        breakeven: str,
        arm: str,
        trail_r: float,
        partials: str,
    ) -> dict:
        key = (stop_trigger, watermark, breakeven, arm, round(trail_r, 6), partials)
        if key in tried:
            return tried[key]
        sim.stop_trigger = stop_trigger
        sim.watermark = watermark
        sim.breakeven = breakeven
        sim.arm = arm
        sim.trail_r = trail_r
        sim.partials = partials
        metrics = _match_trades(sim, entries, real)
        row = {
            "stopTrigger": stop_trigger,
            "watermark": watermark,
            "breakeven": breakeven,
            "arm": arm,
            "trailR": trail_r,
            "partials": partials,
            "bias": metrics["bias"],
            "rmse": metrics["rmse"],
            "corr": metrics["corr"],
            "signAgreement": metrics["signAgreement"],
            "simExpectancy": metrics["simExpectancy"],
            "realExpectancy": metrics["realExpectancy"],
            "pairs": len(metrics["pairs"]),
            "unmatchedSim": metrics["unmatchedSim"],
            "unmatchedReal": metrics["unmatchedReal"],
        }
        tried[key] = row
        order.append(row)
        print(
            f"  stop={stop_trigger:5s} · {watermark:5s} · be={breakeven:4s} · arm={arm:6s} "
            f"· trail={trail_r:<5.2f} · parciales={partials:4s} → sesgo {row['bias']:+.3f} R "
            f"· RMSE {row['rmse']:.3f} · corr {row['corr']:+.3f} · "
            f"signo {row['signAgreement'] * 100:.0f}% ({row['pairs']} ciclos)",
            flush=True,
        )
        return row

    def best_of(rows: list[dict]) -> dict:
        usable = [r for r in rows if math.isfinite(r["rmse"])]
        return min(usable or rows, key=lambda r: (r["rmse"], abs(r["bias"])))

    # Etapa 0: el disparo del stop. Es el eje que separa «el nivel vive en el mercado»
    # (toca el mínimo y se ejecuta a la apertura siguiente) de «solo cuenta el cierre».
    stage0 = [
        evaluate(trigger, sim.watermark, sim.breakeven, sim.arm, sim.trail_r, sim.partials)
        for trigger in STOP_TRIGGER_CHOICES
    ]
    winner0 = best_of(stage0)

    stage1 = [
        evaluate(
            winner0["stopTrigger"], watermark, breakeven, arm, winner0["trailR"], winner0["partials"]
        )
        for watermark in WATERMARK_CHOICES
        for breakeven in BREAKEVEN_CHOICES
        for arm in ARM_CHOICES
    ]
    winner1 = best_of([winner0, *stage1])
    stage2 = [
        evaluate(
            winner1["stopTrigger"],
            winner1["watermark"],
            winner1["breakeven"],
            winner1["arm"],
            trail_r,
            winner1["partials"],
        )
        for trail_r in trail_rs
    ]
    winner2 = best_of([winner1, *stage2])
    stage3 = [
        evaluate(
            winner2["stopTrigger"],
            winner2["watermark"],
            winner2["breakeven"],
            winner2["arm"],
            winner2["trailR"],
            partials,
        )
        for partials in PARTIALS_CHOICES
    ]
    winner3 = best_of([winner2, *stage3])

    # deja el simulador en la variante ganadora (la que se usará después para el control)
    sim.stop_trigger = winner3["stopTrigger"]
    sim.watermark = winner3["watermark"]
    sim.breakeven = winner3["breakeven"]
    sim.arm = winner3["arm"]
    sim.trail_r = winner3["trailR"]
    sim.partials = winner3["partials"]

    return {
        "selection": "rmse",
        "inSample": True,
        "caveat": (
            "Calibración IN-SAMPLE sobre los mismos ciclos que después se comparan: el nivel "
            "absoluto queda REPRODUCIDO, no PREDICHO. La geometría pasa a ser compartida por "
            "RANDOM/CSV/MOMENTUM, así que la comparación relativa entre ramas sigue siendo "
            "válida; el nivel absoluto de RANDOM no."
        ),
        "variants": order,
        "winner": winner3,
        "stage0Winner": winner0,
        "stage1Winner": winner1,
        "stage2Winner": winner2,
    }


def calibrate_lambda(
    sim: Simulation,
    *,
    target_entries: int,
    seed: int,
    momentum_quantile: float,
) -> tuple[float, float]:
    """Ajusta ``lambda`` para que RANDOM produzca ~ ``target_entries`` entradas.

    Una pasada mide la tasa real; se escala y se repite como mucho 3 veces. Determinista.
    """
    decision_days = max(sim.end_index - sim.start_index, 1)
    lam = target_entries / decision_days
    actual = float(target_entries)
    for _ in range(3):
        rng = np.random.default_rng(seed)
        result = sim.run(mode="random", rng=rng, lam=lam, momentum_quantile=momentum_quantile)
        actual = float(result.entries)
        if actual <= 0:
            lam *= 2.0
            continue
        ratio = target_entries / actual
        if abs(ratio - 1.0) <= 0.05:
            break
        lam *= ratio
    return lam, actual


def summarize(rows: list[Result]) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "net_pct": r.net_pct,
                "cagr_pct": r.cagr_pct,
                "max_dd_pct": r.max_dd_pct,
                "sharpe": r.sharpe,
                "cycles": r.cycles,
                "expectancy_r": r.expectancy_r,
                "net_expectancy_r": r.net_expectancy_r,
                "hit_rate": r.hit_rate,
                "payoff": r.payoff,
                "exposure_pct": r.avg_exposure_pct,
                "entries": r.entries,
                "gap_vetoes": r.gap_vetoes,
            }
            for r in rows
        ]
    )
    return frame


def fmt_frame(frame: pd.DataFrame) -> str:
    return frame.round(2).to_string()


# ── Autoprueba ──────────────────────────────────────────────────────────────────────
def synthetic_universe(n_symbols: int = 30, days: int = 1400, seed: int = 7):
    rng = np.random.default_rng(seed)
    calendar = list(pd.bdate_range("2019-01-02", periods=days).date)
    series: dict[str, list[tuple]] = {}
    sectors: dict[str, str] = {}
    for k in range(n_symbols):
        symbol = f"S{k:02d}"
        rets = rng.normal(0.0, 0.016, size=days)  # sin edge
        closes = 100.0 * np.cumprod(1.0 + rets)
        rows = []
        for i, day in enumerate(calendar):
            close = float(closes[i])
            open_px = float(closes[i - 1] * (1.0 + rng.normal(0, 0.004))) if i else close
            high = max(open_px, close) * (1.0 + abs(rng.normal(0, 0.006)))
            low = min(open_px, close) * (1.0 - abs(rng.normal(0, 0.006)))
            rows.append((day, open_px, high, low, close))
        series[symbol] = rows
        sectors[symbol] = f"sector{k % 4}"
    return series, sectors, calendar


def run_selftest(cost_bps: float) -> int:
    series, sectors, calendar = synthetic_universe()
    universe = list(series)
    start, end = calendar[400], calendar[-1]
    sim = Simulation(
        series=series,
        sectors=sectors,
        calendar=calendar,
        start=start,
        end=end,
        universe=universe,
        cost_bps=cost_bps,
        check_accounting=True,
    )
    lam, actual = calibrate_lambda(sim, target_entries=200, seed=1234, momentum_quantile=0.2)
    print(f"[selftest] lambda={lam:.3f} → entradas calibradas={actual:.0f} (objetivo 200)")

    first = sim.run(mode="random", rng=np.random.default_rng(99), lam=lam)
    second = sim.run(mode="random", rng=np.random.default_rng(99), lam=lam)
    print(
        f"[selftest] determinismo: net {first.net_pct:.4f} vs {second.net_pct:.4f} "
        f"| equity idéntica={first.equity == second.equity}"
    )
    print(
        f"[selftest] sin edge: expectancy bruta {first.expectancy_r:+.4f} R "
        f"| neta {first.net_expectancy_r:+.4f} R | ciclos {first.cycles} | hit {first.hit_rate:.1f}%"
    )
    print(
        f"[selftest] contabilidad: equity final {first.equity[-1]:,.0f} "
        f"(caja + marcas, sin descuadre: no saltó la aserción)"
    )

    ok = True
    if first.equity != second.equity:
        ok = False
        print("[selftest] FALLO: la misma semilla no reproduce la misma curva")
    if not (abs(first.expectancy_r) < 0.15):
        ok = False
        print("[selftest] FALLO: con paseo aleatorio la expectancy bruta debería rondar 0")
    if not (first.net_expectancy_r < 0):
        ok = False
        print("[selftest] FALLO: la expectancy neta debería ser negativa (fricción)")
    print("[selftest] " + ("OK" if ok else "FALLÓ"))
    return 0 if ok else 1


def run_structural_selftest(cost_bps: float) -> int:
    """El preset ``structural`` debe ser determinista y no inventar edge.

    No se exige que su expectancy sea idéntica a la del preset ``policy`` (son modelos de
    gestión distintos y sobre ruido puro la diferencia es ruido), solo que (a) no fabrique
    ganancia sistemática, (b) la fricción siga mordiendo y (c) la misma semilla repita.
    """
    series, sectors, calendar = synthetic_universe(seed=11)
    universe = list(series)
    start, end = calendar[400], calendar[-1]
    preset = EXIT_PRESETS["structural"]
    sim = Simulation(
        series=series,
        sectors=sectors,
        calendar=calendar,
        start=start,
        end=end,
        universe=universe,
        cost_bps=cost_bps,
        exit_mode="structural",
        watermark=preset["watermark"],
        breakeven=preset["breakeven"],
        arm=preset["arm"],
        partials=preset["partials"],
        stop_trigger=preset["stopTrigger"],
        check_accounting=True,
    )
    lam, actual = calibrate_lambda(sim, target_entries=200, seed=1234, momentum_quantile=0.2)
    first = sim.run(mode="random", rng=np.random.default_rng(99), lam=lam)
    second = sim.run(mode="random", rng=np.random.default_rng(99), lam=lam)
    print(
        f"[selftest structural] lambda={lam:.3f} → entradas {actual:.0f} · "
        f"bruta {first.expectancy_r:+.4f} R · neta {first.net_expectancy_r:+.4f} R · "
        f"ciclos {first.cycles} · hit {first.hit_rate:.1f}%"
    )
    print(
        f"[selftest structural] determinismo: net {first.net_pct:.4f} vs {second.net_pct:.4f} "
        f"| equity idéntica={first.equity == second.equity}"
    )
    ok = True
    if first.equity != second.equity:
        ok = False
        print("[selftest structural] FALLO: la misma semilla no reproduce la misma curva")
    if not (abs(first.expectancy_r) < 0.20):
        ok = False
        print("[selftest structural] FALLO: con paseo aleatorio la expectancy bruta debería rondar 0")
    if not (first.net_expectancy_r < 0):
        ok = False
        print("[selftest structural] FALLO: la expectancy neta debería ser negativa (fricción)")
    print("[selftest structural] " + ("OK" if ok else "FALLÓ"))
    return 0 if ok else 1


# ── CLI ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2022-01-27", help="primer día de la ventana (marca y entradas)")
    ap.add_argument("--end", default="2026-10-26", help="último día de la ventana")
    ap.add_argument("--seeds", type=int, default=100, help="semillas del modo RANDOM")
    ap.add_argument("--entries-csv", default=None, help="CSV date,yahoo_symbol con las entradas reales")
    ap.add_argument("--mode", default=None, choices=("random", "momentum", "csv"))
    ap.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    ap.add_argument("--entries-target", type=int, default=192, help="entradas que debe producir RANDOM")
    ap.add_argument("--momentum-quantile", type=float, default=0.20)
    ap.add_argument(
        "--exit-mode",
        default="policy",
        choices=("policy", "structural", "geometry", "time-only"),
        help="preset de gestión: policy (simplificado), structural (ratchet real), time-only",
    )
    ap.add_argument(
        "--watermark",
        default=None,
        choices=WATERMARK_CHOICES,
        help="pico del trail: 'close' (marca real del motor) o 'high' (intradía)",
    )
    ap.add_argument(
        "--breakeven",
        default=None,
        choices=BREAKEVEN_CHOICES,
        help="'t1' = breakeven forzado en la entrada al tocar T1 (modelo simplificado)",
    )
    ap.add_argument(
        "--arm",
        default=None,
        choices=ARM_CHOICES,
        help="cuándo se arma el trail: 't1' (tras el primer objetivo) o 'always'",
    )
    ap.add_argument(
        "--partials",
        default=None,
        choices=PARTIALS_CHOICES,
        help="parciales de la plantilla: 'none', 't1' (30%) o 't1t2' (30% + 30% del resto)",
    )
    ap.add_argument(
        "--stop-trigger",
        default=None,
        choices=STOP_TRIGGER_CHOICES,
        help="'touch' = el mínimo del día perfora el nivel (motor real); 'close' = solo el cierre",
    )
    ap.add_argument("--max-holding-days", type=int, default=MAX_HOLDING_DAYS)
    ap.add_argument("--trail-r", type=float, default=TRAIL_R, help="distancia del trailing en R")
    ap.add_argument("--universe", default="csv", choices=("csv", "all"), help="'csv' = nombres de AUTO")
    ap.add_argument("--database-url", default=None)
    ap.add_argument("--seed-base", type=int, default=20260101)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--dump-cycles", default=None, help="CSV con los ciclos del modo CSV")
    ap.add_argument("--fidelity-out", default=None, help="CSV con el cruce ciclo a ciclo sim/real")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument(
        "--ledger",
        default="operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json",
        help="ledger de ciclos reales (para --calibrate y la fidelidad ciclo a ciclo)",
    )
    ap.add_argument(
        "--calibrate",
        action="store_true",
        help="barrido del modelo de salida contra los ciclos reales del ledger",
    )
    ap.add_argument(
        "--calibrate-trail-rs",
        default="0.5,0.75,1.0,1.25,1.5,2.0",
        help="valores de trail_r del barrido (coma)",
    )
    ap.add_argument(
        "--calibration-out",
        default="operability_runs/dia-d-auto/calibracion_estructural.json",
        help="JSON con la tabla del barrido y la variante ganadora",
    )
    a = ap.parse_args(argv)

    if a.selftest:
        policy_code = run_selftest(a.cost_bps)
        structural_code = run_structural_selftest(a.cost_bps)
        return 0 if (policy_code == 0 and structural_code == 0) else 1

    start = pd.Timestamp(a.start).date()
    end = pd.Timestamp(a.end).date()
    entries = load_entries_csv(Path(a.entries_csv)) if a.entries_csv else None
    mode = a.mode or ("csv" if entries is not None else "random")
    if mode == "csv" and entries is None:
        print("# BLOQUEO: --mode csv exige --entries-csv", file=sys.stderr)
        return 2

    series, sectors, calendar = load_prices(_database_url(a.database_url), a.start, a.end)
    if start not in calendar:
        print(f"# BLOQUEO: {start} no es día con barras", file=sys.stderr)
        return 2
    if end not in calendar:
        print(f"# BLOQUEO: {end} no es día con barras", file=sys.stderr)
        return 2

    csv_symbols = sorted({s for symbols in (entries or {}).values() for s in symbols})
    if a.universe == "csv":
        if not csv_symbols:
            print("# BLOQUEO: --universe csv sin --entries-csv no tiene universo", file=sys.stderr)
            return 2
        universe = [s for s in csv_symbols if s in series]
        missing = sorted(set(csv_symbols) - set(series))
        if missing:
            print(f"# BLOQUEO: símbolos sin barras en la BD: {missing}", file=sys.stderr)
            return 2
    else:
        universe = sorted(series)

    # descarta series con historia insuficiente para ATR (evita depender del filtro implícito)
    universe = [s for s in universe if len(series[s]) >= ATR_PERIOD + 20]

    # preset del modelo de salida + overrides explícitos del operador
    preset_name = EXIT_ALIASES.get(a.exit_mode, a.exit_mode)
    preset = EXIT_PRESETS.get(preset_name, EXIT_PRESETS["policy"])
    watermark = a.watermark or preset["watermark"]
    breakeven = a.breakeven or preset["breakeven"]
    arm = a.arm or preset["arm"]
    partials = a.partials or preset["partials"]
    stop_trigger = a.stop_trigger or preset["stopTrigger"]

    sim = Simulation(
        series=series,
        sectors=sectors,
        calendar=calendar,
        start=start,
        end=end,
        universe=universe,
        cost_bps=a.cost_bps,
        exit_mode=preset_name,
        max_holding_days=a.max_holding_days,
        trail_r=a.trail_r,
        watermark=watermark,
        breakeven=breakeven,
        arm=arm,
        partials=partials,
        stop_trigger=stop_trigger,
    )

    print(
        f"Ventana {start} → {end} | {len(universe)} símbolos | coste {a.cost_bps} bps/lado | "
        f"salida {preset_name}"
    )

    if entries is not None:
        unknown_days = sorted({d for d in entries if d not in calendar})
        if unknown_days:
            print(
                f"# BLOQUEO: {len(unknown_days)} fechas del CSV sin barra en el calendario "
                f"({unknown_days[:3]})",
                file=sys.stderr,
            )
            return 2
        in_window = sum(1 for d in entries if start <= d <= end)
        print(f"CSV        {in_window} días con entrada en ventana · {len(csv_symbols)} símbolos")
        print(f"Geometría  trail {a.trail_r}R · máx {a.max_holding_days} días · coste {a.cost_bps} bps")

    results: list[Result] = []
    csv_trades: list[dict] = []
    real: dict | None = None
    calibration: dict | None = None
    fidelity: dict | None = None

    if entries is not None and (a.calibrate or a.ledger):
        ledger_path = Path(a.ledger)
        if not ledger_path.is_absolute():
            ledger_path = Path(__file__).resolve().parents[1] / ledger_path
        if not ledger_path.exists():
            print(f"# BLOQUEO: no existe el ledger {ledger_path}", file=sys.stderr)
            return 2
        real = load_real_cycles(ledger_path, _database_url(a.database_url), start, end)
        print(
            f"Ledger     {ledger_path.name} · {real['cycles']} ciclos · {real['inWindow']} en ventana "
            f"· {real['duplicates']} duplicados exactos · {real['skipped']} sin realizedR/símbolo"
        )

    if a.calibrate:
        if entries is None or real is None:
            print("# BLOQUEO: --calibrate exige --entries-csv y un ledger de ciclos", file=sys.stderr)
            return 2
        trail_rs = [float(v) for v in a.calibrate_trail_rs.split(",") if v.strip()]
        print("\nCalibración del modelo de salida (IN-SAMPLE sobre los ciclos del ledger):")
        calibration = calibrate_exit_model(sim, entries=entries, real=real, trail_rs=trail_rs)
        winner = calibration["winner"]
        print(
            f"\nGanador    stop={winner['stopTrigger']} · watermark={winner['watermark']} · "
            f"breakeven={winner['breakeven']} · arm={winner['arm']} · trail={winner['trailR']}R · "
            f"parciales={winner['partials']}"
        )
        print(
            f"           sesgo {winner['bias']:+.3f} R/ciclo · RMSE {winner['rmse']:.3f} · "
            f"corr {winner['corr']:+.3f} · signo {winner['signAgreement'] * 100:.0f}% "
            f"({winner['pairs']} ciclos cruzados)"
        )
        out_path = Path(a.calibration_out)
        if not out_path.is_absolute():
            out_path = Path(__file__).resolve().parents[1] / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "window": {"start": str(start), "end": str(end)},
                    "costBps": a.cost_bps,
                    "ledger": str(ledger_path),
                    "trailRs": trail_rs,
                    **calibration,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"Calibración {out_path}")

    if entries is not None:
        scheduled = sum(len(v) for v in entries.values())
        results.append(sim.run(mode="csv", entries=entries))
        csv_trades = list(sim.trades)
        first = results[0]
        print(
            f"CSV        {first.entries} de {scheduled} entradas · veto hueco {first.gap_vetoes} · "
            f"saltadas {dict(sorted(first.skipped.items())) or '{}'}"
        )
        if real is not None:
            fidelity = _match_rows(csv_trades, real)
            print(
                f"Fidelidad  {len(fidelity['pairs'])} ciclos cruzados · sesgo {fidelity['bias']:+.3f} R/ciclo "
                f"· RMSE {fidelity['rmse']:.3f} · corr {fidelity['corr']:+.3f} · "
                f"signo {fidelity['signAgreement'] * 100:.0f}% · "
                f"sim {fidelity['simExpectancy']:+.3f} R vs real {fidelity['realExpectancy']:+.3f} R"
            )
            if fidelity["unmatchedSim"] or fidelity["unmatchedReal"]:
                print(
                    f"           sin pareja: simulados {fidelity['unmatchedSim']} · "
                    f"reales {fidelity['unmatchedReal']} (declarado, no imputado)"
                )
            print("Descomposición del residuo (sim − real, R/ciclo):")
            for row in fidelity["decomposition"]:
                if not row["n"]:
                    continue
                print(
                    f"  {row['label']:31s} n={row['n']:3d} · sesgo {row['bias']:+.3f} · "
                    f"RMSE {row['rmse']:.3f} · sim {row['meanSim']:+.3f} vs real {row['meanReal']:+.3f}"
                )
            risk = fidelity["riskPct"]
            if risk["simMedian"] is not None:
                print(
                    f"  riesgo por operación (mediana): sim {risk['simMedian']:.2f}% vs "
                    f"real {risk['realMedian']:.2f}% del precio (Δ {risk['simMinusRealMedian']:+.2f} p.p.)"
                )

    if mode == "csv" and (entries is not None) and a.seeds <= 0:
        pass
    else:
        if a.seeds > 0:
            lam, actual = calibrate_lambda(
                sim, target_entries=a.entries_target, seed=a.seed_base, momentum_quantile=a.momentum_quantile
            )
            print(
                f"RANDOM     lambda={lam:.3f} · entradas/día objetivo {a.entries_target} "
                f"· calibración medida {actual:.0f}"
            )
            for k in range(a.seeds):
                rng = np.random.default_rng(a.seed_base + k)
                results.append(sim.run(mode="random", rng=rng, lam=lam, seed_label=f"#{k}"))
            results.append(sim.run(mode="momentum", momentum_quantile=a.momentum_quantile))
        elif entries is None:
            print("# BLOQUEO: sin CSV y sin semillas no hay nada que medir", file=sys.stderr)
            return 2

    print()
    random_rows = [r for r in results if r.mode.startswith("random")]
    csv_row = next((r for r in results if r.mode == "csv"), None)
    momentum_row = next((r for r in results if r.mode == "momentum"), None)
    if random_rows:
        rnd = summarize(random_rows)
        arms: dict[str, pd.Series] = {
            "RANDOM mediana": rnd.median(),
            "RANDOM p5": rnd.quantile(0.05),
            "RANDOM p95": rnd.quantile(0.95),
        }
        if csv_row is not None:
            arms["CSV (AUTO)"] = summarize([csv_row]).iloc[0]
        if momentum_row is not None:
            arms["MOMENTUM"] = summarize([momentum_row]).iloc[0]
        table = pd.DataFrame(arms).T
        print(fmt_frame(table))
        print()
        if csv_row is not None:
            pct_net = 100.0 * float((rnd["net_pct"] < csv_row.net_pct).mean())
            pct_r = 100.0 * float((rnd["expectancy_r"] < csv_row.expectancy_r).mean())
            print(
                f"CSV (AUTO) percentil en RANDOM: neto {pct_net:.0f}% · expectancy {pct_r:.0f}% "
                f"({len(random_rows)} semillas)"
            )
            if fidelity is not None:
                print(
                    f"Fidelidad vs ledger de AUTO: expectancy simulada {csv_row.expectancy_r:+.3f} R "
                    f"vs {fidelity['realExpectancy']:+.3f} R del ledger "
                    f"(sesgo {fidelity['bias']:+.3f} R por ciclo)"
                )
            else:
                print(
                    f"Fidelidad vs ledger de AUTO: expectancy simulada {csv_row.expectancy_r:+.3f} R "
                    f"vs -0.204 R del ledger (sesgo {csv_row.expectancy_r + 0.204:+.3f} R por ciclo)"
                )
            if csv_row.skipped:
                detail = ", ".join(f"{k}={v}" for k, v in sorted(csv_row.skipped.items()))
                print(
                    f"CSV entradas: {csv_row.entries} ejecutadas · {csv_row.gap_vetoes} vetadas por "
                    f"hueco · {detail}"
                )
        if momentum_row is not None:
            pct_m = 100.0 * float((rnd["net_pct"] < momentum_row.net_pct).mean())
            print(f"MOMENTUM percentil en RANDOM (neto): {pct_m:.0f}%")
    else:
        table = summarize(results)
        table.index = ["CSV (AUTO)" if r.mode == "csv" else "MOMENTUM" if r.mode == "momentum" else r.mode for r in results]
        print(fmt_frame(table))

    if a.dump_cycles and csv_trades:
        pd.DataFrame(csv_trades).to_csv(a.dump_cycles, index=False)
        print(f"\nciclos CSV {a.dump_cycles}")

    if a.fidelity_out and fidelity is not None:
        out = Path(a.fidelity_out)
        if not out.is_absolute():
            out = Path(__file__).resolve().parents[1] / out
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(fidelity["pairs"]).to_csv(out, index=False)
        print(f"cruce sim/real {out}")

    if a.json_out:
        payload = {
            "window": {"start": str(start), "end": str(end)},
            "costBps": a.cost_bps,
            "exitMode": preset_name,
            "exitModel": {
                "watermark": sim.watermark,
                "breakeven": sim.breakeven,
                "arm": sim.arm,
                "partials": sim.partials,
                "stopTrigger": sim.stop_trigger,
                "trailR": sim.trail_r,
                "maxHoldingDays": sim.max_holding_days,
            },
            "universe": universe,
            "calibration": (
                {
                    "selection": calibration["selection"],
                    "inSample": calibration["inSample"],
                    "caveat": calibration["caveat"],
                    "winner": calibration["winner"],
                    "variants": calibration["variants"],
                }
                if calibration is not None
                else None
            ),
            "fidelity": (
                {
                    "pairs": len(fidelity["pairs"]),
                    "bias": fidelity["bias"],
                    "rmse": fidelity["rmse"],
                    "corr": fidelity["corr"],
                    "signAgreement": fidelity["signAgreement"],
                    "simExpectancy": fidelity["simExpectancy"],
                    "realExpectancy": fidelity["realExpectancy"],
                    "unmatchedSim": fidelity["unmatchedSim"],
                    "unmatchedReal": fidelity["unmatchedReal"],
                    "decomposition": fidelity["decomposition"],
                    "riskPct": fidelity["riskPct"],
                }
                if fidelity is not None
                else None
            ),
            "results": [
                {
                    k: v
                    for k, v in r.__dict__.items()
                    if k != "equity"
                }
                | {"equityFinal": r.equity[-1] if r.equity else None}
                for r in results
            ],
        }
        Path(a.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\nJSON       {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
