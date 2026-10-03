"""V2.88.38 · DÍA-D AUTO — agregación LONGITUDINAL OOS (pura, sin I/O).

Qué es
------
El sandbox DÍA-D (`v2_89`) produce la foto de un día; el feedback por valor (`v2_90`) pliega una
ventana corta ``D0..D1`` por instrumento. Este módulo añade el eje **longitudinal**: dado el
recorrido OOS de una ventana **larga** (p. ej. el año natural 2022 con el universo PIT), mide

* la **expectativa y el acierto** de la ventana (reutilizando ``build_value_scorecard``, sin
  duplicar umbrales ni veredictos), y
* la **estabilidad temporal** (series por año/trimestre/mes) y las **excursiones** MAE/MFE por
  ciclo, que el scorer congelado NO calcula.

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None`` / ``NOT_MEASURED``; **nunca** se rellena con ``0``.
* La unidad es el **ciclo** (no el fill); la atribución temporal es por **``entryDay``** (D34-02).
* La dirección de un ciclo se **infiere** de la geometría ``stop`` vs ``entry`` (long: ``stop <
  entry``; short: ``stop > entry``): el scorer NO serializa ``direction`` (para no mover el
  artefacto congelado de ``replay-repro``). Una geometría imposible (``stop == entry``) se declara
  hueco, nunca se asume larga.
* **MAE/MFE son entre DÍAS** (barras D1): el día de entrada puede incluir excursión previa al
  fill. Se declara; no se presenta como intradía.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.directional_geometry import risk_distance, signed_r
from bolsa_application.dia_d_auto import finite_number, normalize_day
from bolsa_application.dia_d_auto_feedback import build_value_scorecard
from bolsa_application.replay_oos import bar_day

#: Versión del esquema del artefacto longitudinal. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-longitudinal-v1"

LONG = "long"
SHORT = "short"

#: Periodos declarados para las series de estabilidad.
BUCKET_PERIODS: tuple[str, ...] = ("year", "quarter", "month")

#: Motivos declarados de una excursión no medida.
REASON_RISK_UNMEASURABLE = "riesgo_no_medible"
REASON_NO_BARS = "sin_barras_en_rango"
REASON_NO_DIRECTION = "direccion_no_inferible"

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. La media de una muestra vacia es None.",
    "La unidad es el CICLO (no el fill); la ventana se atribuye por entryDay (dia de decision).",
    "MAE/MFE son extremos ENTRE DIAS (barras D1); el dia de entrada puede incluir excursion previa "
    "al fill. No se presentan como intradia.",
    "La direccion se infiere de la geometria stop vs entry (long: stop<entry); el scorer no "
    "serializa direction para no mover el artefacto congelado de replay-repro.",
    "Los cubos de calendario del forward real no son reproducibles con reloj simulado.",
    "La estabilidad intra-ventana NO mide multirregimen si la ventana tiene un solo regimen.",
)


@dataclass(frozen=True, slots=True)
class Excursion:
    """Excursión adversa/favorable (en R) de un ciclo, medida desde barras D1."""

    symbol: str
    entry_day: str
    exit_day: str
    direction: str | None
    risk: float | None
    mae_r: float | None
    mfe_r: float | None
    measured: bool
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entryDay": self.entry_day,
            "exitDay": self.exit_day,
            "direction": self.direction,
            "risk": self.risk,
            "maeR": self.mae_r,
            "mfeR": self.mfe_r,
            "measured": self.measured,
            "reason": self.reason,
        }


def infer_direction(*, entry: Any, stop: Any) -> str | None:
    """Dirección inferida de la geometría ``stop`` vs ``entry``; ``None`` si es imposible.

    Long exige ``stop < entry`` y short ``stop > entry`` (misma casa que ``directional_geometry``).
    ``stop == entry`` no es "riesgo cero": es una geometría que no se puede medir ⇒ ``None``.
    """
    e = finite_number(entry)
    s = finite_number(stop)
    if e is None or s is None:
        return None
    if s < e:
        return LONG
    if s > e:
        return SHORT
    return None


def _high_low(bar: Any) -> tuple[float, float] | None:
    high = finite_number(getattr(bar, "high", None))
    low = finite_number(getattr(bar, "low", None))
    if high is None or low is None:
        return None
    return high, low


def _bars_by_day(bars: Sequence[Any]) -> dict[str, tuple[float, float]]:
    """``{día: (high, low)}`` de un símbolo; un día ilegible o sin OHLC se descarta (fail-closed)."""
    out: dict[str, tuple[float, float]] = {}
    for bar in bars or ():
        day = bar_day(bar)
        if not day:
            continue
        high_low = _high_low(bar)
        if high_low is None:
            continue
        out[day] = high_low
    return out


def excursion_for_cycle(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    round_trip: Mapping[str, Any],
) -> Excursion:
    """Excursión de UN ciclo: MAE/MFE en R desde las barras D1 entre ``entryDay`` y ``exitDay``.

    Devuelve un hueco declarado (``measured=False``) si falta la geometría, el riesgo o las
    barras del rango. Nunca inventa extremos.
    """
    symbol = str(round_trip.get("symbol") or "")
    entry_day = normalize_day(round_trip.get("entryDay")) or ""
    exit_day = normalize_day(round_trip.get("exitDay")) or ""
    entry_price = finite_number(round_trip.get("entryPrice"))
    stop = finite_number(round_trip.get("stop"))

    def _gap(reason: str, direction: str | None = None, risk: float | None = None) -> Excursion:
        return Excursion(
            symbol=symbol,
            entry_day=entry_day,
            exit_day=exit_day,
            direction=direction,
            risk=risk,
            mae_r=None,
            mfe_r=None,
            measured=False,
            reason=reason,
        )

    if not entry_day or not exit_day:
        return _gap(REASON_NO_BARS)
    direction = infer_direction(entry=entry_price, stop=stop)
    if direction is None:
        return _gap(REASON_NO_DIRECTION)
    risk = risk_distance(entry=entry_price, stop=stop, direction=direction)
    if risk is None:
        return _gap(REASON_RISK_UNMEASURABLE, direction=direction)

    table = _bars_by_day(bars_by_symbol.get(symbol, ()))
    window = [
        high_low
        for day, high_low in table.items()
        if entry_day <= day <= exit_day
    ]
    if not window:
        return _gap(REASON_NO_BARS, direction=direction, risk=risk)

    min_low = min(low for _high, low in window)
    max_high = max(high for high, _low in window)
    if direction == LONG:
        adverse_price, favorable_price = min_low, max_high
    else:
        adverse_price, favorable_price = max_high, min_low
    mae_r = signed_r(direction=direction, entry=entry_price, risk=risk, price=adverse_price)
    mfe_r = signed_r(direction=direction, entry=entry_price, risk=risk, price=favorable_price)
    if mae_r is None or mfe_r is None:
        return _gap(REASON_RISK_UNMEASURABLE, direction=direction, risk=risk)
    return Excursion(
        symbol=symbol,
        entry_day=entry_day,
        exit_day=exit_day,
        direction=direction,
        risk=risk,
        mae_r=mae_r,
        mfe_r=mfe_r,
        measured=True,
        reason=None,
    )


def excursions(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    round_trips: Sequence[Mapping[str, Any]],
) -> list[Excursion]:
    """Excursiones de TODOS los ciclos, en orden determinista (por símbolo y día de entrada)."""
    rows = [excursion_for_cycle(bars_by_symbol=bars_by_symbol, round_trip=trip) for trip in round_trips]
    rows.sort(key=lambda row: (row.entry_day, row.symbol, row.exit_day))
    return rows


def summarize_excursions(rows: Sequence[Excursion | Mapping[str, Any]]) -> dict[str, Any]:
    """Resumen de MAE/MFE: medias y extremos sobre los ciclos MEDIDOS, huecos por motivo."""
    measured: list[tuple[float, float]] = []
    reasons: dict[str, int] = {}
    unmeasured = 0
    for row in rows:
        record = row.to_dict() if isinstance(row, Excursion) else row
        mae = finite_number(record.get("maeR"))
        mfe = finite_number(record.get("mfeR"))
        if mae is not None and mfe is not None:
            measured.append((mae, mfe))
            continue
        unmeasured += 1
        reason = str(record.get("reason") or "").strip() or "sin_medir"
        reasons[reason] = reasons.get(reason, 0) + 1
    maes = [mae for mae, _mfe in measured]
    mfes = [mfe for _mae, mfe in measured]
    return {
        "measured": len(measured),
        "unmeasured": unmeasured,
        "unmeasuredReasons": reasons,
        "meanMaeR": (sum(maes) / len(maes)) if maes else None,
        "meanMfeR": (sum(mfes) / len(mfes)) if mfes else None,
        "minMaeR": min(maes) if maes else None,
        "maxMfeR": max(mfes) if mfes else None,
    }


def bucket_key(day: Any, period: str) -> str | None:
    """Clave de cubo temporal de un día ISO: ``YYYY`` / ``YYYY-Qn`` / ``YYYY-MM``; ``None`` ilegible.

    Un día malformado NO se adivina: devuelve ``None`` y el llamante declara el hueco.
    """
    normalized = normalize_day(day)
    if not normalized:
        return None
    year, _, rest = normalized.partition("-")
    if period == "year":
        return year
    month, _, _day = rest.partition("-")
    if not month:
        return None
    if period == "quarter":
        try:
            quarter = (int(month) - 1) // 3 + 1
        except ValueError:
            return None
        return f"{year}-Q{quarter}"
    return f"{year}-{month}"


def bucket_series(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    period: str,
) -> list[dict[str, Any]]:
    """Serie temporal de la ventana: por cubo, ciclos y R realizado (atribuido por ``entryDay``)."""
    if period not in BUCKET_PERIODS:
        raise ValueError(f"periodo no soportado: {period!r}")
    buckets: dict[str, list[float]] = {}
    for trip in round_trips or ():
        value = finite_number(trip.get("realizedR"))
        if value is None:
            continue
        key = bucket_key(trip.get("entryDay"), period)
        if key is None:
            continue
        buckets.setdefault(key, []).append(value)
    series: list[dict[str, Any]] = []
    for key in sorted(buckets):
        values = buckets[key]
        series.append(
            {
                "bucket": key,
                "cycles": len(values),
                "expectancyR": sum(values) / len(values),
                "realizedRTotal": sum(values),
                "hitRate": sum(1 for value in values if value > 0) / len(values),
            }
        )
    return series


def stability_summary(
    series: Sequence[Mapping[str, Any]],
    *,
    period: str,
) -> dict[str, Any]:
    """Dispersión de la expectativa entre cubos: ¿el edge aguanta o depende de un tramo?

    Un cubo sin ciclos no entra en la dispersión (no se rellena con ``0``). Si no hay ningún
    cubo medido, todo extremo es ``None``.
    """
    expectancies = [
        value
        for row in series
        if (value := finite_number(row.get("expectancyR"))) is not None
    ]
    positive = sum(1 for value in expectancies if value > 0)
    negative = sum(1 for value in expectancies if value < 0)
    flat = len(expectancies) - positive - negative
    return {
        "bucketPeriod": period,
        "buckets": len(series),
        "measuredBuckets": len(expectancies),
        "positiveBuckets": positive,
        "negativeBuckets": negative,
        "flatBuckets": flat,
        "minExpectancyR": min(expectancies) if expectancies else None,
        "maxExpectancyR": max(expectancies) if expectancies else None,
        "meanBucketR": (sum(expectancies) / len(expectancies)) if expectancies else None,
    }


def longest_operable_run(
    operable_days: Sequence[bool],
    *,
    start_index: int,
    end_index: int,
) -> tuple[int, int] | None:
    """Tramo contiguo más largo con ``operable_days[i] is True`` dentro de ``[start, end]``.

    Devuelve ``(inicio, fin)`` INCLUSIVOS o ``None`` si no hay ningún día operable. Se usa como
    plan B declarado (``windowFallback``) cuando la corrida larga trunca.
    """
    if not operable_days:
        return None
    lo = max(0, int(start_index))
    hi = min(len(operable_days) - 1, int(end_index))
    if lo > hi:
        return None
    best: tuple[int, int] | None = None
    run_start: int | None = None
    for index in range(lo, hi + 1):
        if bool(operable_days[index]):
            if run_start is None:
                run_start = index
            if best is None or (index - run_start) > (best[1] - best[0]):
                best = (run_start, index)
        else:
            run_start = None
    return best


def build_dia_d_longitudinal_artifact(
    *,
    window_from: Any,
    window_to: Any,
    days: Sequence[Any],
    operable_days: int,
    round_trips: Sequence[Mapping[str, Any]],
    open_positions: Sequence[Mapping[str, Any]] = (),
    unmeasured: Sequence[Any] = (),
    excursions_rows: Sequence[Excursion | Mapping[str, Any]] = (),
    regime_counts: Mapping[str, int] | None = None,
    watch: Sequence[Any] = (),
    watch_source: str = "catalog",
    universe_coverage: Mapping[str, Any] | None = None,
    probe: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    bucket_period: str = "month",
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico del estudio longitudinal (puro y determinista: sin reloj ni aleatorios).

    Reutiliza ``build_value_scorecard`` para el veredicto/`evidenceQuality` de la ventana y de cada
    valor (no se duplican umbrales). Añade las series de estabilidad y el resumen de MAE/MFE.
    """
    window_days = [normalize_day(day) for day in days if normalize_day(day)]
    unique_days = sorted(set(window_days))
    ordered_trips = sorted(
        (dict(trip) for trip in round_trips or ()),
        key=lambda trip: (
            str(trip.get("entryDay") or ""),
            str(trip.get("symbol") or ""),
            str(trip.get("exitDay") or ""),
        ),
    )

    window_scorecard = build_value_scorecard("WINDOW", round_trips=ordered_trips, days=unique_days)

    symbols = sorted({str(trip.get("symbol") or "") for trip in ordered_trips if trip.get("symbol")})
    values = [
        build_value_scorecard(
            symbol,
            round_trips=[trip for trip in ordered_trips if str(trip.get("symbol") or "") == symbol],
            days=unique_days,
        )
        for symbol in symbols
    ]

    series = bucket_series(ordered_trips, period=bucket_period)
    by_year = bucket_series(ordered_trips, period="year")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "DIA_D_AUTO_LONGITUDINAL",
        "readOnly": True,
        "basis": "entryDay",
        "window": {
            "from": normalize_day(window_from),
            "to": normalize_day(window_to),
            "days": unique_days,
            "daysTotal": len(unique_days),
            "operableDays": int(operable_days),
        },
        "probe": {str(key): value for key, value in (probe or {}).items()},
        "summary": {
            "verdict": window_scorecard["verdict"],
            "verdictReason": window_scorecard["verdictReason"],
            "evidenceQuality": window_scorecard["evidenceQuality"],
            "expectancyR": window_scorecard["expectancyR"],
            "hitRate": window_scorecard["hitRate"],
            "measuredCycles": window_scorecard["measuredCycles"],
            "realizedRTotal": window_scorecard["realizedRTotal"],
            "openPositions": len(open_positions or ()),
            "unmeasuredCount": len(unmeasured or ()),
            "regimeCounts": {str(key): int(value) for key, value in (regime_counts or {}).items()},
        },
        "stability": stability_summary(series, period=bucket_period),
        "series": series,
        "byYear": by_year,
        "excursions": summarize_excursions(excursions_rows),
        "values": values,
        "meta": {
            "watch": [str(symbol) for symbol in watch],
            "watchSource": str(watch_source),
            "survivorBiasRisk": str(watch_source) == "catalog",
            "universeCoverage": dict(universe_coverage or {}),
            **{str(key): value for key, value in (meta or {}).items()},
        },
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "BUCKET_PERIODS",
    "DEFAULT_LIMITS",
    "Excursion",
    "LONG",
    "REASON_NO_BARS",
    "REASON_NO_DIRECTION",
    "REASON_RISK_UNMEASURABLE",
    "SCHEMA_VERSION",
    "SHORT",
    "bucket_key",
    "bucket_series",
    "build_dia_d_longitudinal_artifact",
    "excursion_for_cycle",
    "excursions",
    "infer_direction",
    "longest_operable_run",
    "stability_summary",
    "summarize_excursions",
]
