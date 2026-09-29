"""AUTO-MATERIAL-14 (v2.86) — Replay OOS de viabilidad del motor AUTO.

Fase de **INVESTIGACIÓN** (`v2.86`), **aditiva**: no modifica ninguna pieza congelada
(``auto_simulation_worker.py``, ``auto_v2_entry.py``, ``sim_durable_store.py``,
``market_operability.py``). Este módulo es PURO salvo ``make_as_of_bar_loader``, que solo
lee barras.

Qué aporta
----------

* ``make_as_of_bar_loader`` — proveedor de barras **acotado a ``as_of``** (misma forma que
  ``make_bar_snapshot_loader``) para que ``DiscoveryRegimeSource``/``AtrSource`` vean SOLO
  barras ``timestamp <= as_of``. Sin lookahead.
* ``step_day_clock`` — reloj de **un día por tick** (D1) sobre el seam ``Clock`` que ya
  aceptan ``AutoSimulationWorker``/``AutoSimRuntime``.
* ``make_day_price_script`` — precio histórico por ``(symbol, tick)``: el tick ``n`` opera
  al **open del día ``days[n-1]``**. Ese es el instante honesto del walk-forward: la
  decisión se toma con las barras COMPLETAS hasta el día anterior y se ejecuta al open del
  día siguiente, sin que ninguna barra posterior entre en la decisión.
* ``census_operable_days`` — censo read-only: por cada día ``D``, régimen del watch con
  barras ``<= D`` (reutiliza el MISMO ``classify_market_regime`` +
  ``aggregate_trial_regime`` que usa el motor).
* ``score_replay`` — puntuación OOS: empareja fills buy/sell por símbolo y mide el R
  realizado contra el stop con el que el motor nació la posición.
* ``snapshot_book``/``tally_releases``/``declare_horizon`` (``v2.87``) — instrumentación del
  **libro de compromisos** (reserva → fill → liberación) y del **horizonte**: publican
  cuánto capital sigue comprometido, cómo se retiró y, si el replay se corta, por qué. Un
  libro que no se puede medir se declara ``UNKNOWN``; una truncación sin causa se declara
  ``undeclared_truncation``. Nada de eso se rellena con un valor plausible.

Límites declarados (no se disfrazan)
------------------------------------

* **NO sustituye la ventana PAPER.** El cubo de calendario sale del **reloj de pared**
  (``sim_fill_finance_context.created_at`` es ``datetime.now(UTC)`` en el camino vivo), así
  que un replay no fabrica cubos durables. Es evidencia de investigación.
* **NO cierra ``P3-2``/``P3-3``**: son evidencia de una clase distinta.
* **Aproximación D1 declarada**: un día = un tick. Todo hueco se publica como ``None``/
  ``n/d``, nunca como un ``0`` inventado.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from bolsa_analytics.cognitive.market_regime_gate import (
    map_trial_regime,
    regime_allows_entry_for,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.auto_v2_entry import aggregate_trial_regime
from bolsa_application.discovery_market_regime import (
    MATH_VERSION_MARKET_REGIME_V0,
    classify_market_regime,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DEAD_TAIL_REASON",
    "HORIZON_STALLED_BOOK",
    "HORIZON_UNDECLARED",
    "STALL_OPERABLE_DAYS",
    "BookSnapshot",
    "CensusDay",
    "CensusReport",
    "Clock",
    "Horizon",
    "OpenPosition",
    "ReleaseTally",
    "ReplayCursor",
    "ReplayFill",
    "ReplayTick",
    "RoundTrip",
    "ScoreReport",
    "bar_day",
    "book_is_declared_complete",
    "census_operable_days",
    "clamp_bars_as_of",
    "close_tick",
    "count_release_reasons",
    "count_releases",
    "declare_book_measurement",
    "declare_horizon",
    "declare_stall",
    "make_as_of_bar_loader",
    "make_day_price_script",
    "operable_days_without_activity",
    "release_deltas",
    "score_replay",
    "snapshot_book",
    "step_day_clock",
    "tally_releases",
]

#: Reloj inyectable: cada llamada devuelve el instante simulado (una llamada = un tick).
Clock = Callable[[], datetime]

#: Precio histórico por ``(símbolo, tick)`` — misma firma que ``PriceScript`` del worker.
DayPriceScript = Callable[[str, int], float]

#: Etiquetas de régimen de barras que NO bloquean un long (para el censo por símbolo).
_LONG_FRIENDLY_TRIAL: frozenset[str] = frozenset({"trend_up", "range", "high_vol", "low_vol"})


# ── Barras acotadas a ``as_of`` (no lookahead) ────────────────────────────────────


def bar_day(bar: Any) -> str:
    """Día ISO (``YYYY-MM-DD``) de una barra (``OhlcvBar`` o ``Mapping``); ``""`` si no hay."""
    if isinstance(bar, Mapping):
        raw = bar.get("timestamp") or bar.get("date")
    else:
        raw = getattr(bar, "timestamp", None) or getattr(bar, "date", None)
    text = str(raw or "").strip()
    return text[:10] if text else ""


def _resolve_as_of(as_of: str | datetime | Callable[[], Any] | None) -> str:
    """Normaliza ``as_of`` (str/datetime/provider) al día ISO ``YYYY-MM-DD``."""
    value = as_of() if callable(as_of) else as_of
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value or "").strip()[:10]


def clamp_bars_as_of(bars: Sequence[Any] | None, as_of: Any) -> list[Any]:
    """Devuelve SOLO las barras con día ``<= as_of`` (guardia de NO lookahead).

    Es la guardia en CLIENTE, independiente de que el repositorio soporte ``date_to``: una
    barra sin fecha legible se DESCARTA (fail-closed), nunca se asume que es del pasado.
    Sin ``as_of`` resoluble devuelve ``[]`` (sin fecha límite no hay ventana segura).
    """
    limit = _resolve_as_of(as_of)
    if not limit:
        return []
    return [bar for bar in (bars or []) if (day := bar_day(bar)) and day <= limit]


def make_as_of_bar_loader(
    ohlcv: Any,
    symbols: Sequence[str],
    as_of: str | datetime | Callable[[], Any] | None,
    *,
    timeframe: Any = None,
    limit: int | None = 10_000,
) -> Callable[[], Awaitable[dict[str, list[Any]]]]:
    """``refresh()`` async que precarga ``{symbol: [bars <= as_of]}`` (no lookahead).

    Misma FORMA que ``make_bar_snapshot_loader`` (devuelve un ``refresh()`` async que el
    worker invoca una vez por tick), pero acotando cada símbolo a ``timestamp <= as_of``.
    ``as_of`` acepta un ``str``, un ``datetime`` o un **provider** (``Callable[[], ...]``),
    de modo que el harness mueve la barra temporal entre ticks sin recomponer el loader.

    El repositorio real soporta ``date_to`` y lo usamos (menos filas en vuelo); un port de
    test que no lo soporte cae al camino sin filtro y la guardia en cliente hace el trabajo.
    Un fallo por símbolo se ignora (ese símbolo se queda sin barras ⇒ fail-closed), nunca
    aborta el refresco.
    """
    from bolsa_domain.value_objects.timeframe import TimeFrame  # noqa: PLC0415

    effective_timeframe = timeframe if timeframe is not None else TimeFrame.D1
    watch = tuple(str(s) for s in symbols)

    async def refresh() -> dict[str, list[Any]]:
        day = _resolve_as_of(as_of)
        snapshot: dict[str, list[Any]] = {}
        if not day:
            return snapshot
        for symbol in watch:
            try:
                try:
                    bars = await ohlcv.get_bars(
                        symbol,
                        timeframe=effective_timeframe,
                        limit=limit,
                        date_to=day,
                    )
                except TypeError:
                    # Port sin ``date_to`` (firma reducida): se pide sin filtro y la guardia
                    # en cliente acota. No se degrada el invariante, solo se lee de más.
                    bars = await ohlcv.get_bars(symbol, timeframe=effective_timeframe, limit=limit)
            except Exception:  # noqa: BLE001 — sin barras ⇒ ese símbolo no decide (fail-closed).
                logger.debug("replay as_of: no bars for %s", symbol, exc_info=True)
                continue
            clamped = clamp_bars_as_of(bars, day)
            if clamped:
                snapshot[str(symbol)] = clamped
        return snapshot

    return refresh


# ── Reloj de un día por tick y precio histórico ───────────────────────────────────


def step_day_clock(start: datetime | None = None) -> tuple[datetime, Clock]:
    """``(inicio, clock)``: cada llamada de ``clock()`` avanza **un día** simulado (D1).

    Espeja ``step_minute_clock`` del worker, pero en la unidad del replay: un tick = un día.
    """
    cur: dict[str, datetime] = {"now": start if start is not None else datetime.now(UTC)}

    def clock() -> datetime:
        cur["now"] = cur["now"] + timedelta(days=1)
        return cur["now"]

    return cur["now"], clock


def make_day_price_script(
    opens_by_symbol: Mapping[str, Mapping[str, Any]],
    days: Sequence[str],
) -> DayPriceScript:
    """``price_script(symbol, tick)`` = open del día ``days[tick]`` (sin lookahead).

    El worker llama ``price_script(symbol, self._minute)`` y ``self._minute`` vale ``1`` en
    el PRIMER turno (``auto_turn`` hace ``_advance()`` antes de decidir). Con ``days`` = los
    días de negociación ordenados, el tick ``t`` opera al **open de ``days[t]``** mientras la
    decisión usa las barras completas hasta ``days[t-1]``: exactamente "abrir al open del día
    siguiente" a la última barra completa, sin lookahead.

    Un día/tick fuera de rango o un precio no finito/``<= 0`` devuelven ``0.0``: el motor lo
    lee como "sin precio" y queda fail-closed (nunca se inventa un precio para poder abrir).
    """
    calendar = tuple(str(day)[:10] for day in days)
    table: dict[str, dict[str, float]] = {}
    for symbol, by_day in opens_by_symbol.items():
        clean: dict[str, float] = {}
        for day, raw in (by_day or {}).items():
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value != value or value in (float("inf"), float("-inf")) or value <= 0:
                continue
            clean[str(day)[:10]] = value
        table[str(symbol)] = clean

    def _price(symbol: str, tick: int) -> float:
        try:
            index = int(tick)
        except (TypeError, ValueError):
            return 0.0
        if index < 0 or index >= len(calendar):
            return 0.0
        return table.get(str(symbol), {}).get(calendar[index], 0.0)

    return _price


class ReplayCursor:
    """Cursor de la ventana de replay: **una sola autoridad** del tick ⇄ día simulado.

    El harness fija ``index`` antes de cada ``auto_turn`` y las tres vistas se derivan de él:

    * ``as_of()`` → día ANTERIOR (barras visibles para clasificar régimen/ATR);
    * ``clock()`` → día simulado (``_time`` del worker);
    * ``price_script(symbol, tick)`` → open del día simulado (ejecución), **ignorando** el
      ``tick`` que pasa el worker.

    Ignorar el ``tick`` es deliberado: acoplar el precio al contador PRIVADO ``_minute`` (que
    arranca en 0 y avanza con cada ``_advance``) haría que un cambio interno del worker
    desalineara precio y fecha sin que ningún test lo notara. Con el cursor, la ventana es la
    que manda y el "abrir al open del día siguiente" queda garantizado por construcción.
    """

    __slots__ = ("_days", "_price", "_index")

    def __init__(
        self,
        days: Sequence[str],
        opens_by_symbol: Mapping[str, Mapping[str, Any]],
        *,
        start_index: int = 0,
    ) -> None:
        self._days = tuple(str(day)[:10] for day in days)
        if not self._days:
            raise ValueError("ReplayCursor exige al menos un día")
        self._price = make_day_price_script(opens_by_symbol, self._days)
        self._index = min(max(int(start_index), 0), len(self._days) - 1)

    @property
    def days(self) -> tuple[str, ...]:
        return self._days

    @property
    def index(self) -> int:
        return self._index

    def set_index(self, index: int) -> None:
        self._index = min(max(int(index), 0), len(self._days) - 1)

    def current_day(self) -> str:
        return self._days[self._index]

    def as_of(self) -> str:
        """Día anterior: la última barra COMPLETA que la decisión puede ver."""
        return self._days[self._index - 1] if self._index > 0 else ""

    def clock(self) -> datetime:
        return datetime.fromisoformat(f"{self.current_day()}T00:00:00+00:00")

    def price_script(self, symbol: str, _tick: int = 0) -> float:
        """Precio del día simulado (el ``tick`` del worker se ignora: manda el cursor)."""
        return self._price(str(symbol), self._index)


# ── Paso 0 · Censo de días operables (read-only) ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class CensusDay:
    """Régimen del watch en un día ``D`` con barras ``timestamp <= D`` (sin lookahead)."""

    day: str
    regimes: Mapping[str, str]
    counts: Mapping[str, int]
    aggregate: str
    operational: str
    entries_allowed_long: bool
    operable_symbols: int
    measured_symbols: int
    watch: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "regimes": dict(self.regimes),
            "counts": dict(self.counts),
            "aggregate": self.aggregate,
            "operational": self.operational,
            "entriesAllowedLong": bool(self.entries_allowed_long),
            "operableSymbols": int(self.operable_symbols),
            "measuredSymbols": int(self.measured_symbols),
            "watch": int(self.watch),
        }


@dataclass(frozen=True, slots=True)
class CensusReport:
    """Censo de operabilidad: nº de días operables, racha máxima y distribución."""

    days: tuple[CensusDay, ...]
    operable_days: int
    max_operable_streak: int
    aggregate_counts: Mapping[str, int]
    watch: int

    def operable_by_operational(self) -> dict[str, int]:
        """Días operables por eje operativo: evita leer ``318`` como si fuesen ``trend_up``.

        El gate de régimen NO veta ``HIGH_VOLATILITY``, así que un día ``high_vol`` cuenta
        como operable por este eje. El desglose lo declara en vez de esconderlo.
        """
        counts: dict[str, int] = {}
        for row in self.days:
            if not row.entries_allowed_long:
                continue
            key = row.operational or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": [day.to_dict() for day in self.days],
            "totalDays": len(self.days),
            "operableDays": int(self.operable_days),
            "operableByOperational": self.operable_by_operational(),
            "maxOperableStreak": int(self.max_operable_streak),
            "aggregateCounts": dict(self.aggregate_counts),
            "watch": int(self.watch),
        }


def _regime_counts(regimes: Mapping[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in regimes.values():
        key = str(label or "sin_regimen")
        counts[key] = counts.get(key, 0) + 1
    return counts


def census_operable_days(
    bars_by_symbol: Mapping[str, Sequence[Any]],
    days: Sequence[str],
    *,
    math_version: str = MATH_VERSION_MARKET_REGIME_V0,
) -> CensusReport:
    """Clasifica, día a día, el régimen del watch con barras ``<= D`` (reutiliza el motor).

    ``bars_by_symbol`` son las barras COMPLETAS del símbolo (pasado y futuro); para cada día
    ``D`` de ``days`` se acotan a ``<= D`` antes de clasificar, de modo que un día nunca ve
    una barra posterior. El agregado usa ``aggregate_trial_regime`` (el MISMO veredicto más
    conservador que usa el motor) y la operabilidad se decide con
    ``regime_allows_entry_for`` (el MISMO gate direccional del hot path).
    """
    watch = tuple(str(s) for s in bars_by_symbol)
    ordered_days = tuple(str(d)[:10] for d in days if str(d or "").strip())
    rows: list[CensusDay] = []
    for day in ordered_days:
        regimes: dict[str, str] = {}
        for symbol in sorted(watch):
            bars = clamp_bars_as_of(bars_by_symbol.get(symbol), day)
            label = classify_market_regime(list(bars), math_version=math_version) if bars else ""
            if label:
                regimes[symbol] = label
        aggregate = aggregate_trial_regime(regimes.values())
        operational = map_trial_regime(aggregate)
        measured = len(regimes)
        operable = sum(1 for label in regimes.values() if label in _LONG_FRIENDLY_TRIAL)
        rows.append(
            CensusDay(
                day=day,
                regimes=regimes,
                counts=_regime_counts(regimes),
                aggregate=aggregate,
                operational=operational,
                entries_allowed_long=bool(regime_allows_entry_for(operational, "long")),
                operable_symbols=operable,
                measured_symbols=measured,
                watch=len(watch),
            )
        )

    streak = 0
    best = 0
    for row in rows:
        streak = streak + 1 if row.entries_allowed_long else 0
        best = max(best, streak)
    aggregate_counts: dict[str, int] = {}
    for row in rows:
        key = row.aggregate or "sin_regimen"
        aggregate_counts[key] = aggregate_counts.get(key, 0) + 1

    return CensusReport(
        days=tuple(rows),
        operable_days=sum(1 for row in rows if row.entries_allowed_long),
        max_operable_streak=best,
        aggregate_counts=aggregate_counts,
        watch=len(watch),
    )


# ── Paso 3 · Puntuación OOS contra barras futuras conocidas ───────────────────────


@dataclass(frozen=True, slots=True)
class ReplayFill:
    """Fill del replay (entrada o salida) con su precio simulado."""

    day: str
    symbol: str
    side: str  # "buy" | "sell"
    quantity: float
    price: float
    strategy_version: str | None = None
    cycle_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayTick:
    """Foto de un tick (un día) del replay, ya materializada (el scorer es PURO)."""

    day: str
    regime: str | None
    prices: Mapping[str, float]
    open_positions: Mapping[str, float]
    entry_prices: Mapping[str, float]
    stops: Mapping[str, float]
    fill_rows: tuple[ReplayFill, ...] = ()
    proposals: int = 0
    vetoes: int = 0
    orders: int = 0
    fills: int = 0


@dataclass(frozen=True, slots=True)
class RoundTrip:
    """Operación cerrada del replay con su R realizado (denominador = riesgo al nacer)."""

    symbol: str
    entry_day: str
    exit_day: str
    entry_price: float
    exit_price: float
    stop: float
    realized_r: float
    strategy_version: str | None = None
    cycle_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entryDay": self.entry_day,
            "exitDay": self.exit_day,
            "entryPrice": self.entry_price,
            "exitPrice": self.exit_price,
            "stop": self.stop,
            "realizedR": self.realized_r,
            "strategyVersion": self.strategy_version,
            "cycleId": self.cycle_id,
        }


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """Posición viva al final del replay: R NO realizado (se declara como hueco medido)."""

    symbol: str
    entry_day: str
    entry_price: float
    stop: float
    last_price: float
    quantity: float
    unrealized_r: float | None
    strategy_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entryDay": self.entry_day,
            "entryPrice": self.entry_price,
            "stop": self.stop,
            "lastPrice": self.last_price,
            "quantity": self.quantity,
            "unrealizedR": self.unrealized_r,
            "strategyVersion": self.strategy_version,
        }


@dataclass(frozen=True, slots=True)
class ScoreReport:
    """Puntuación OOS: R realizado, acierto de signo y distribución (huecos declarados)."""

    round_trips: tuple[RoundTrip, ...]
    open_positions: tuple[OpenPosition, ...]
    unmeasured: tuple[str, ...]

    @property
    def realized_count(self) -> int:
        return len(self.round_trips)

    @property
    def realized_r_total(self) -> float:
        return sum(trip.realized_r for trip in self.round_trips)

    @property
    def mean_r(self) -> float | None:
        return _mean([trip.realized_r for trip in self.round_trips])

    @property
    def median_r(self) -> float | None:
        return _median([trip.realized_r for trip in self.round_trips])

    @property
    def positive_share(self) -> float | None:
        values = [trip.realized_r for trip in self.round_trips]
        if not values:
            return None
        return sum(1 for value in values if value > 0) / len(values)

    def by_version(self) -> dict[str, dict[str, Any]]:
        return _bucket(self.round_trips, lambda trip: str(trip.strategy_version or "sin_version"))

    def by_day(self) -> dict[str, dict[str, Any]]:
        return _bucket(self.round_trips, lambda trip: trip.exit_day)

    def by_year(self) -> dict[str, dict[str, Any]]:
        """Bucket por AÑO de salida: es lo que permite leer si la muestra es multianual.

        El v2.86 se truncaba a un único episodio (2022); con el ciclo durable completo el
        horizonte debería repartirse entre años, y este bucket lo publica o lo desmiente.
        Un día ilegible cae en ``sin_fecha`` (nunca se adivina el año).
        """
        return _bucket(self.round_trips, lambda trip: _year_of(trip.exit_day))

    def to_dict(self) -> dict[str, Any]:
        reasons: dict[str, int] = {}
        for gap in self.unmeasured:
            reason = gap.rsplit(":", 1)[-1]
            reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "realizedCount": self.realized_count,
            "realizedRTotal": self.realized_r_total,
            "meanR": self.mean_r,
            "medianR": self.median_r,
            "positiveShare": self.positive_share,
            "roundTrips": [trip.to_dict() for trip in self.round_trips],
            "openPositions": [pos.to_dict() for pos in self.open_positions],
            "byVersion": self.by_version(),
            "byDay": self.by_day(),
            "byYear": self.by_year(),
            "unmeasured": list(self.unmeasured),
            "unmeasuredCount": len(self.unmeasured),
            "unmeasuredReasons": reasons,
        }


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _year_of(day: Any) -> str:
    """Año (``YYYY``) de un día ISO; ``sin_fecha`` si no es una fecha legible.

    Un día malformado NO se adivina: cae en su propio bucket declarado, del mismo modo que
    ``by_version`` usa ``sin_version``. Inventar un año movería la muestra de año.
    """
    text = str(day or "").strip()
    year = text[:4]
    return year if len(year) == 4 and year.isdigit() else "sin_fecha"


def _opt_float(value: Any) -> float | None:
    """``Decimal``/``str``/``int`` → ``float`` finito; ``None`` si no es cuantificable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _bucket(
    trips: Sequence[RoundTrip], key: Callable[[RoundTrip], str]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for trip in trips:
        grouped.setdefault(key(trip), []).append(trip.realized_r)
    out: dict[str, dict[str, Any]] = {}
    for label, values in grouped.items():
        out[label] = {
            "count": len(values),
            "meanR": _mean(values),
            "medianR": _median(values),
            "positiveShare": (
                sum(1 for value in values if value > 0) / len(values) if values else None
            ),
        }
    return out


def _realized_r(*, entry: float, exit_price: float, stop: float) -> float | None:
    """R realizado de un long: ``(exit − entry) / (entry − stop)``. Hueco si no es medible."""
    risk = entry - stop
    if risk != risk or risk <= 0 or exit_price != exit_price:
        return None
    return (exit_price - entry) / risk


def score_replay(ticks: Sequence[ReplayTick]) -> ScoreReport:
    """Puntúa el replay contra los fills ya materializados (PURO, sin mirar el futuro).

    **Unidad = el CICLO de la posición, no el fill.** El motor liquida en fills PARCIALES
    (varias filas por entrada y por salida), así que contar una ida y vuelta por cada fila
    repetiría la misma R ``k`` veces e inflaría el censo. Aquí se agrega por símbolo:

    * la ENTRADA toma el precio medio ponderado de sus ``buy`` y el **stop del tick en que
      nació** la posición (el denominador de R, que no se re-media);
    * la SALIDA toma el precio medio ponderado de los ``sell``;
    * cuando la posición queda a CERO se emite **una** ``RoundTrip``; mientras queda viva,
      sigue abierta (y al final se publica como ``OpenPosition`` con su R NO realizado).

    Huecos declarados (``unmeasured``): una salida sin entrada previa, o un ciclo cuyo stop
    no era medible al nacer (``entry == stop``), NO producen R. Se declara; nunca se rellena
    con un ``0``.
    """
    entry_ctx: dict[str, dict[str, Any]] = {}
    round_trips: list[RoundTrip] = []
    unmeasured: list[str] = []
    last_tick = ticks[-1] if ticks else None

    for tick in ticks:
        for row in tick.fill_rows:
            symbol = row.symbol
            if row.side == "buy":
                ctx = entry_ctx.get(symbol)
                if ctx is None:
                    entry_ctx[symbol] = {
                        "entry_day": tick.day,
                        "buy_qty": float(row.quantity),
                        "buy_notional": float(row.quantity) * float(row.price),
                        "stop": float(tick.stops.get(symbol, 0.0) or 0.0),
                        "strategy_version": row.strategy_version,
                        "cycle_id": row.cycle_id,
                    }
                else:
                    ctx["buy_qty"] = float(ctx["buy_qty"]) + float(row.quantity)
                    ctx["buy_notional"] = float(ctx["buy_notional"]) + float(row.quantity) * float(
                        row.price
                    )
                continue

            # side == "sell"
            ctx = entry_ctx.get(symbol)
            if ctx is None:
                unmeasured.append(f"{tick.day}:{symbol}:salida_sin_entrada")
                continue
            ctx["sell_qty"] = float(ctx.get("sell_qty", 0.0)) + float(row.quantity)
            ctx["sell_notional"] = float(ctx.get("sell_notional", 0.0)) + float(
                row.quantity
            ) * float(row.price)
            remaining = float(ctx["buy_qty"]) - float(ctx["sell_qty"])
            if remaining > 1e-9:
                continue  # posición viva por el resto: aún no hay ida y vuelta cerrada.

            entry_price = float(ctx["buy_notional"]) / float(ctx["buy_qty"])
            exit_price = float(ctx["sell_notional"]) / float(ctx["sell_qty"])
            stop = float(ctx["stop"])
            realized = _realized_r(entry=entry_price, exit_price=exit_price, stop=stop)
            if realized is None:
                unmeasured.append(f"{tick.day}:{symbol}:riesgo_no_medible")
            else:
                round_trips.append(
                    RoundTrip(
                        symbol=symbol,
                        entry_day=str(ctx["entry_day"]),
                        exit_day=tick.day,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        stop=stop,
                        realized_r=realized,
                        strategy_version=ctx.get("strategy_version"),
                        cycle_id=ctx.get("cycle_id"),
                    )
                )
            entry_ctx.pop(symbol, None)

    open_positions: list[OpenPosition] = []
    if last_tick is not None:
        for symbol, ctx in sorted(entry_ctx.items()):
            quantity = float(ctx["buy_qty"]) - float(ctx.get("sell_qty", 0.0))
            if quantity <= 1e-9:
                continue
            entry_price = float(ctx["buy_notional"]) / float(ctx["buy_qty"])
            last_price = float(last_tick.prices.get(symbol, 0.0) or 0.0)
            unrealized = (
                _realized_r(entry=entry_price, exit_price=last_price, stop=float(ctx["stop"]))
                if last_price > 0
                else None
            )
            if unrealized is None and last_price > 0:
                unmeasured.append(f"{symbol}:abierta_riesgo_no_medible")
            open_positions.append(
                OpenPosition(
                    symbol=symbol,
                    entry_day=str(ctx["entry_day"]),
                    entry_price=entry_price,
                    stop=float(ctx["stop"]),
                    last_price=last_price,
                    quantity=quantity,
                    unrealized_r=unrealized,
                    strategy_version=ctx.get("strategy_version"),
                )
            )

    return ScoreReport(
        round_trips=tuple(round_trips),
        open_positions=tuple(open_positions),
        unmeasured=tuple(unmeasured),
    )


# ── Instrumentación del libro de compromisos (reserva → fill → liberación) ────────
#
# El replay de ``v2.86`` se truncó porque el libro de compromisos pendientes nunca se
# retiraba: una reserva aprobada cuya orden no llegaba a emitirse quedaba ``OPEN`` para
# siempre y agotaba el presupuesto de riesgo. Estos helpers NO tocan el motor: solo
# publican, tick a tick, cuánto capital sigue comprometido, cómo se retiró (por fill o
# por cancelación) y si la medición del libro se puede AFIRMAR. Un libro que no se puede
# medir se declara ``UNKNOWN``, jamás ``COMPLETE``.

#: Estado de una reserva VIVA (``portfolio_reservation.RESERVATION_OPEN``).
_RESERVATION_OPEN = "OPEN"

#: Estados de reserva YA liberada (``portfolio_reservation``): su cierre es una retirada.
_RELEASED_STATUSES: frozenset[str] = frozenset(
    {
        "RELEASED_BY_FILL",
        "RELEASED_BY_CANCEL",
        "RELEASED_BY_RESTART",
        "RELEASED_BY_ROLLBACK",
    }
)

#: Etiquetas válidas de ``MeasurementStatus``; cualquier otra cosa ⇒ ``UNKNOWN``.
_MEASUREMENT_LABELS: frozenset[str] = frozenset(
    {MEASUREMENT_COMPLETE, MEASUREMENT_PARTIAL, MEASUREMENT_UNKNOWN}
)

#: Motivo publicado cuando el horizonte queda corto y NINGUNA causa se declaró.
HORIZON_UNDECLARED = "undeclared_truncation"

#: Motivo publicado cuando el motor DEJÓ DE OPERAR con el libro todavía comprometido
#: (OBS-18: presupuesto agotado por compromisos que nadie retira). No es una medición
#: incompleta: es una corrida que recorrió todos los ticks sin ejercitar el horizonte.
HORIZON_STALLED_BOOK = "stalled_book"

#: Días OPERABLES consecutivos sin una sola orden/fill tras los cuales un libro que sigue
#: comprometiendo capital deja de ser "el motor eligió no operar" y se declara ESTANCAMIENTO.
#: Es un umbral de DECLARACIÓN, no un gate de comportamiento: la corrida nunca se corta por
#: él, solo deja de publicarse como completa. Un mes de días operables es holgadamente mayor
#: que cualquier hueco legítimo medido entre temporadas (el mayor del histórico es de 2025-04
#: a 2026-01, y en él el libro estaba LIMPIO: la condición exige las dos cosas).
STALL_OPERABLE_DAYS = 20

#: Motivo tipificado de retirada (OBS-18): la cola de un fill parcial cuyo orden ya no está
#: en vuelo. ``portfolio_reservation.RELEASE_REASON_DEAD_TAIL``; se duplica aquí para no
#: importar el paquete de analítica desde la capa de aplicación.
DEAD_TAIL_REASON = "tail_dead"


def operable_days_without_activity(
    operable_days: Sequence[bool] | None,
    *,
    last_active_index: int | None,
    end_index: int,
) -> int:
    """Días OPERABLES recorridos después del último día con actividad (aritmética del guardarraíl).

    ``operable_days`` es la operabilidad POR ÍNDICE de día (el censo es 1:1 con el calendario
    que el replay recorre) y ``end_index`` es exclusivo (los días efectivamente simulados).

    Dos decisiones fail-loud, explícitas:

    * un ``last_active_index is None`` (ni una sola orden en toda la corrida) cuenta desde el
      principio: la ausencia de actividad es TOTAL, no "desconocida";
    * un índice fuera del censo NO se cuenta como operable —no se puede AFIRMAR que ese día
      fuera operable—, así que un censo recortado **sub-declara** el estancamiento en vez de
      inventarlo. El precio es conocido y se prefiere: declarar de más convierte un hueco
      legítimo en un falso positivo; declarar de menos solo deja la puerta abierta al silencio
      que este guardarraíl existe para cerrar, y ese caso queda cubierto por el libro
      (``declare_stall`` exige ADEMÁS capital comprometido).
    """
    if last_active_index is None:
        start = 0
    else:
        start = max(0, int(last_active_index) + 1)
    flags = operable_days or ()
    return sum(1 for offset in range(start, max(0, int(end_index))) if _is_operable(flags, offset))


def _is_operable(operable_days: Sequence[bool], index: int) -> bool:
    """True solo si el censo DECLARA el día como operable; un índice sin censo no lo es."""
    if index < 0 or index >= len(operable_days):
        return False
    return bool(operable_days[index])


def declare_stall(
    *,
    operable_days_without_activity: int,
    live_reservations: int,
    reserved_risk: float | None,
    threshold: int = STALL_OPERABLE_DAYS,
) -> str | None:
    """Declara ``stalled_book`` si el libro compromete capital y el motor lleva N días sin operar.

    Fail-loud con dos condiciones EXPLÍCITAS, para no confundir "no quiso operar" con "no pudo":

    * el libro sigue comprometido (``live_reservations > 0`` o ``reserved_risk > 0``), y
    * pasaron ``threshold`` días operables consecutivos sin una sola orden ni fill.

    Un libro limpio con una temporada sin señales (o sin gate) NO es un estancamiento, y
    tampoco lo es un libro sucio en el último tick. ``reserved_risk`` ilegible se lee como
    "no puedo afirmar que esté limpio" y por tanto cuenta como comprometido (fail-closed).
    """
    days = max(0, int(operable_days_without_activity))
    if days < max(1, int(threshold)):
        return None
    risk = _opt_float(reserved_risk)
    committed = int(live_reservations) > 0 or risk is None or risk > 0.0
    return HORIZON_STALLED_BOOK if committed else None


def declare_book_measurement(measurement: Any) -> str:
    """Etiqueta de medición del libro, **fail-closed**: lo ilegible es ``UNKNOWN``.

    Un ``None``, un texto vacío o un valor que no sea ``COMPLETE``/``PARTIAL``/``UNKNOWN``
    NO se leen como ``COMPLETE``: "no sé medir el libro" y "el libro está entero" son cosas
    distintas y confundirlas es justo lo que autoriza a abrir contra un riesgo que no se
    conoce.
    """
    label = str(measurement or "").strip().upper()
    return label if label in _MEASUREMENT_LABELS else MEASUREMENT_UNKNOWN


def book_is_declared_complete(measurement: Any) -> bool:
    """True solo si la medición NORMALIZADA es ``COMPLETE`` (ver ``declare_book_measurement``)."""
    return declare_book_measurement(measurement) == MEASUREMENT_COMPLETE


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    """Foto del libro de compromisos de un tick, con su medición DECLARADA.

    ``reserved_cash``/``reserved_risk`` son la SUMA de lo cuantificable; si alguna reserva
    viva no declara sus dimensiones (``unquantified_reservations > 0``), la suma es un
    SUELO y la medición del libro lo refleja — nunca se presenta como el total exacto.
    """

    day: str
    live_reservations: int
    unquantified_reservations: int
    reserved_cash: float
    reserved_risk: float
    pending_orders: int
    measurement: str

    @property
    def is_measurable(self) -> bool:
        """True solo si el libro se puede afirmar entero (medición ``COMPLETE``)."""
        return self.measurement == MEASUREMENT_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "liveReservations": int(self.live_reservations),
            "unquantifiedReservations": int(self.unquantified_reservations),
            "reservedCash": float(self.reserved_cash),
            "reservedRisk": float(self.reserved_risk),
            "pendingOrders": int(self.pending_orders),
            "measurement": self.measurement,
            "measurable": bool(self.is_measurable),
        }


def snapshot_book(
    day: Any,
    *,
    reservations: Sequence[Any] | None = None,
    pending_orders: Sequence[Any] | None = None,
    measurement: Any = None,
) -> BookSnapshot:
    """Resume el libro de compromisos de un día: reservas vivas, capital, órdenes y medición.

    ``reservations`` son las reservas del libro (vivas y liberadas); solo las VIVAS cuentan
    para el capital comprometido del tick. ``pending_orders`` es el libro efectivo de
    órdenes pendientes (reservas proyectadas + trazas huérfanas) y ``measurement`` su
    medición, que se publica NORMALIZADA (fail-closed).
    """
    live = [row for row in (reservations or ()) if bool(getattr(row, "is_live", False))]
    cash = 0.0
    risk = 0.0
    unquantified = 0
    for row in live:
        cash_value = _opt_float(getattr(row, "reserved_cash", None))
        risk_value = _opt_float(getattr(row, "reserved_risk", None))
        if cash_value is not None:
            cash += cash_value
        if risk_value is not None:
            risk += risk_value
        if not bool(getattr(row, "is_quantified", False)):
            unquantified += 1
    return BookSnapshot(
        day=str(day or "").strip()[:10],
        live_reservations=len(live),
        unquantified_reservations=unquantified,
        reserved_cash=cash,
        reserved_risk=risk,
        pending_orders=len(tuple(pending_orders or ())),
        measurement=declare_book_measurement(measurement),
    )


@dataclass(frozen=True, slots=True)
class ReleaseTally:
    """Retiradas del libro, por estado DESTINO: acumulado del log y delta del tick."""

    total: Mapping[str, int]
    delta: Mapping[str, int]
    reasons: Mapping[str, int] = field(default_factory=dict)
    delta_reasons: Mapping[str, int] = field(default_factory=dict)

    @property
    def by_fill(self) -> int:
        return int(self.total.get("RELEASED_BY_FILL", 0))

    @property
    def by_cancel(self) -> int:
        """Retiradas por CANCELACIÓN acumuladas: la firma del compromiso huérfano."""
        return int(self.total.get("RELEASED_BY_CANCEL", 0))

    @property
    def by_dead_tail(self) -> int:
        """OBS-18 — colas de fill parcial retiradas porque su orden ya no estaba en vuelo.

        Se separa de ``by_cancel`` porque no son huérfanas: su fila SÍ registró fill parcial.
        Mezclarlas escondería el mecanismo (la cola que nadie retiraba) detrás del síntoma.
        """
        return int(self.reasons.get(DEAD_TAIL_REASON, 0))

    @property
    def delta_by_fill(self) -> int:
        return int(self.delta.get("RELEASED_BY_FILL", 0))

    @property
    def delta_by_cancel(self) -> int:
        """Retiradas por CANCELACIÓN de ESTE tick: el huérfano que se liberó ahora."""
        return int(self.delta.get("RELEASED_BY_CANCEL", 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": dict(self.total),
            "delta": dict(self.delta),
            "byFill": self.by_fill,
            "byCancel": self.by_cancel,
            "byDeadTail": self.by_dead_tail,
            "reasons": dict(self.reasons),
            "deltaByFill": self.delta_by_fill,
            "deltaByCancel": self.delta_by_cancel,
            "deltaReasons": dict(self.delta_reasons),
        }


def _release_status(row: Any) -> str:
    """Estado normalizado de una reserva (o de un evento del log); ``""`` si no lo declara."""
    if isinstance(row, Mapping):
        raw = row.get("status")
    else:
        raw = getattr(row, "status", None)
    return str(raw or "").strip().upper()


def _release_reason(row: Any) -> str:
    """Motivo normalizado de la retirada (``""`` si la fila no lo declara)."""
    if isinstance(row, Mapping):
        raw = row.get("reason") or row.get("release_reason")
    else:
        raw = getattr(row, "reason", None) or getattr(row, "release_reason", None)
    return str(raw or "").strip().lower()


def count_releases(reservations: Sequence[Any] | None) -> dict[str, int]:
    """Cuenta acumulada de retiradas por estado destino, sobre el libro completo."""
    counts: dict[str, int] = {}
    for row in reservations or ():
        status = _release_status(row)
        if status in _RELEASED_STATUSES:
            counts[status] = counts.get(status, 0) + 1
    return counts


def count_release_reasons(reservations: Sequence[Any] | None) -> dict[str, int]:
    """Cuenta acumulada de retiradas por MOTIVO declarado (OBS-18: ``tail_dead`` aparte)."""
    counts: dict[str, int] = {}
    for row in reservations or ():
        if _release_status(row) not in _RELEASED_STATUSES:
            continue
        reason = _release_reason(row)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def release_deltas(
    before: Sequence[Any] | None,
    after: Sequence[Any] | None,
) -> dict[str, int]:
    """Transiciones VIVO → liberado entre dos fotos del libro, por ``reservation_id``.

    Una reserva que NO estaba viva en ``before`` no se cuenta: solo la retirada de un
    compromiso que ANTES consumía presupuesto es una retirada. Así el conteo mide el ciclo
    real (alta → liberación), no el catálogo histórico de filas.
    """
    previous = {
        str(getattr(row, "reservation_id", "") or ""): _release_status(row)
        for row in (before or ())
    }
    counts: dict[str, int] = {}
    for row in after or ():
        key = str(getattr(row, "reservation_id", "") or "")
        status = _release_status(row)
        if not key or status not in _RELEASED_STATUSES:
            continue
        if previous.get(key) == _RESERVATION_OPEN:
            counts[status] = counts.get(status, 0) + 1
    return counts


def tally_releases(
    previous: Sequence[Any] | None,
    events: Sequence[Any] | None,
) -> ReleaseTally:
    """``ReleaseTally`` desde un **log append-only** de retiradas (reservas o eventos).

    ``previous`` es el PREFIJO ya contabilizado del log (basta su longitud): el delta son los
    eventos NUEVOS y el acumulado se recalcula del log completo. Es exacto por construcción y
    no depende de releer un libro con un tope que un replay largo podría agotar — que es
    precisamente cómo el conteo de retiradas se volvería un suelo silencioso.
    """
    log = tuple(events or ())
    already = max(0, min(len(previous or ()), len(log)))
    return ReleaseTally(
        total=count_releases(log),
        delta=count_releases(log[already:]),
        reasons=count_release_reasons(log),
        delta_reasons=count_release_reasons(log[already:]),
    )


@dataclass(frozen=True, slots=True)
class Horizon:
    """Cobertura declarada del replay: hasta dónde llegó y, si se cortó, POR QUÉ.

    Invariante fail-loud: un horizonte incompleto **siempre** lleva motivo. Si la corrida
    se queda corta sin que nadie declare una causa, se publica ``undeclared_truncation``
    en vez de dejar el hueco sin nombre (que es como una truncación se disfraza de ventana).
    """

    completed: bool
    last_day: str | None
    ticks: int
    total_ticks: int
    truncation_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": bool(self.completed),
            "lastDay": self.last_day,
            "ticks": int(self.ticks),
            "totalTicks": int(self.total_ticks),
            "truncationReason": self.truncation_reason,
        }


def declare_horizon(
    *,
    ticks: int,
    total_ticks: int,
    last_day: Any = None,
    truncation_reason: Any = None,
) -> Horizon:
    """Cierra el horizonte con motivo OBLIGATORIO cuando no cubre la ventana completa.

    ``completed`` exige las dos cosas: ninguna causa declarada y todos los ticks recorridos.
    Una causa declarada gana sobre el conteo (si el guardarraíl paró la corrida, manda la
    parada); un déficit de ticks sin causa se declara (``HORIZON_UNDECLARED``).
    """
    done_ticks = max(0, int(ticks))
    wanted = max(0, int(total_ticks))
    reason = str(truncation_reason or "").strip() or None
    if reason is None and done_ticks < wanted:
        reason = HORIZON_UNDECLARED
    return Horizon(
        completed=reason is None and done_ticks >= wanted,
        last_day=str(last_day or "").strip()[:10] or None,
        ticks=done_ticks,
        total_ticks=wanted,
        truncation_reason=reason,
    )


# ── Costura del cierre de tick (ciclo durable, v2.87) ────────────────────────────


async def close_tick(worker: Any, *, durable_cycle: bool = True) -> bool:
    """Cierra el ciclo DURABLE del tick sobre el worker congelado (costura de ``v2.87``).

    Invoca el método de PRODUCCIÓN ``_v2_reconcile_reservations(startup=False,
    attribute_fills=False)`` —el MISMO que el motor real corre al cerrar cada turno— al final
    de cada tick del replay. En el motor SIM la orden se liquida DENTRO del tick, así que la
    reserva que sigue viva al cierre y NUNCA se materializó es la de una orden que murió sin
    llenarse: retirarla (``RELEASED_BY_CANCEL``) es fiel, no un atajo.

    ``attribute_fills=False`` NO es cosmético: la regla 1 de la reconciliación reparte el
    histórico COMPLETO de fills ≥ ``created_at`` (``consumed`` se reinicia en cada llamada) y
    ``_release`` aplica ``released_qty`` como delta, así que la atribución **no es
    idempotente**. Al cerrar cada tick re-liberaría fills ya liberados por el camino caliente
    y DRENARÍA la cola VIVA de una orden parcialmente llenada — capital comprometido de
    verdad (fail-OPEN). La guardia de ``in_flight`` del propio método CONSERVA además la
    reserva cuyo fill esté capturado y sin aplicar.

    ``durable_cycle=False`` es el modo CONTROL: no toca el libro y deja la reserva huérfana
    viva (es el goteo que truncaba ``v2.86``, ahora medible). Devuelve ``True`` si reconcilió.

    ``only_ids`` acota el cierre a las reservas que el worker dio de alta
    (``_v2_owned_reservations``), igual que el motor real (OBS-14.b). En un proceso ÚNICO el
    huérfano del tick es del propio turno, así que el conjunto acota sin quitar nada: el
    cierre retira exactamente lo mismo que antes. Lo que deja de existir es la ventana en la
    que una sesión retiraba la reserva viva de OTRA —indistinguible de una orden muerta hasta
    que la otra emite y liquida— devolviendo al mercado capital que sí se materializó.

    Fail-loud: si la pieza congelada desaparece, NO se degrada en silencio — un replay que
    cree haber cerrado el ciclo sin cerrarlo publicaría un horizonte que miente.
    """
    if not durable_cycle:
        return False
    reconcile = getattr(worker, "_v2_reconcile_reservations", None)
    if not callable(reconcile):
        raise RuntimeError(
            "el worker no expone _v2_reconcile_reservations: sin la pieza de producción el "
            "cierre de tick no puede declararse hecho"
        )
    owned = getattr(worker, "_v2_owned_reservations", None)
    await reconcile(
        startup=False,
        attribute_fills=False,
        only_ids=frozenset(owned) if owned is not None else None,
    )
    return True


# ── Utilidades de agregación para el informe ──────────────────────────────────────


@dataclass(slots=True)
class ReplayTotals:
    """Totales del replay por día (funnel), sin inventar ceros."""

    decided: int = 0
    proposals: int = 0
    vetoes: int = 0
    orders: int = 0
    fills: int = 0
    ticks: int = 0
    per_day: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticks": self.ticks,
            "decided": self.decided,
            "proposals": self.proposals,
            "vetoes": self.vetoes,
            "orders": self.orders,
            "fills": self.fills,
            "perDay": list(self.per_day),
        }
