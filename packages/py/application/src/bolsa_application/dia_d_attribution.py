"""V2.88.39 · DÍA-D AUTO — ATRIBUCIÓN del resultado OOS por dimensión (pura, sin I/O).

Qué es
------
El agregado longitudinal (``dia_d_longitudinal``) mide *cuánto* rinde la ventana OOS: expectativa,
acierto, estabilidad y MAE/MFE. Este módulo (V2.91/``v2_92``) añade el eje **atribución**: *dónde*
y *cómo* se gana o se pierde ese R, sin ejecutar ventanas nuevas ni tocar el motor.

Descompone la esperanza de la MISMA muestra de ciclos por:

* **payoff** — ``expectancyR = winRate·avgWinR + (1 − winRate)·avgLossR`` (identidad auditable);
* **régimen** del día de decisión (el agregado trial que ya calcula ``census_operable_days``);
* **estrategia** (``strategyVersion`` que el scorer congela en el ciclo);
* **sector** (el del catálogo actual; declarado aproximado, no point-in-time);
* **activo** (símbolo);
* **excursión** — cuánto MFE favorable se dejó sobre la mesa (``capture``/``leftOnTable``) y
  cuántos perdedores atravesaron el stop (MAE peor que ``-1R``);
* **concentración** — si el signo de la ventana depende de unos pocos ciclos.

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None`` / ``NOT_MEASURED``; **nunca** se rellena con ``0``.
* La unidad es el **ciclo**; la atribución temporal es por **``entryDay``** (D34-02).
* Una etiqueta ausente (régimen/sector/estrategia/símbolo) cae en su cubo declarado ``sin_*``;
  no se adivina.
* La capa es **advisory y read-only**: **no** cambia el motor, los umbrales, ``TOP_N`` ni la
  allocation, y **no** escribe en PostgreSQL.
* El desglose es **descriptivo**, no causal: un cubo con muestra pequeña se declara, no se
  promociona. ``CONFIRMED`` sigue reservado a evidencia PAPER (no se emite).

Veredicto/``evidenceQuality``: se **reutiliza** ``build_value_scorecard`` (no se duplican
umbrales). MAE/MFE se reutilizan de ``dia_d_longitudinal`` (no se recalculan).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from bolsa_application.dia_d_auto import finite_number, normalize_day
from bolsa_application.dia_d_auto_feedback import build_value_scorecard
from bolsa_application.dia_d_longitudinal import Excursion, excursions

#: Versión del esquema del artefacto de atribución. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-attribution-v1"

#: Cubos declarados para una etiqueta ausente (nunca se adivina la dimensión).
SIN_REGIMEN = "sin_regimen"
SIN_SECTOR = "sin_sector"
SIN_VERSION = "sin_version"
SIN_SIMBOLO = "sin_simbolo"

#: Umbrales declarados del estudio de excursión/severidad (no son decisiones estadísticas, son
#: el suelo con el que se lee "el stop aguantó" o "se dejó premio en la mesa").
STOP_BREACH_THRESHOLDS: tuple[float, ...] = (-1.0, -1.25, -1.5)
#: MFE mínimo (en R) para considerar que un ciclo "dio premio" antes de cerrar.
REVERSAL_MFE_MIN_R = 1.0

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Atribucion DESCRIPTIVA, no causal: descompone la muestra medida, no explica el mercado.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. La media de una muestra vacia es None.",
    "La unidad es el CICLO; la atribucion temporal es por entryDay (dia de decision).",
    "El regimen es el agregado trial por dia (census_operable_days); una ventana de un solo "
    "regimen colapsa byRegime y NO se sobreinterpreta como multirregimen.",
    "El sector es el del catalogo ACTUAL (no point-in-time); su atribucion es aproximada y se declara.",
    "MAE/MFE son extremos ENTRE DIAS (barras D1); el dia de entrada puede incluir excursion previa al fill.",
    "CONFIRMED sigue reservado a evidencia PAPER y NO se emite al observar el replay.",
)


# ── Utilidades numéricas (None cuando no hay muestra; nunca 0) ───────────────────


def _mean(values: Sequence[float]) -> float | None:
    """Media de una muestra o ``None`` si está vacía (un vacío no es un ``0``)."""
    return sum(values) / len(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    """Mediana de una muestra o ``None`` si está vacía (determinista)."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _label(value: Any, fallback: str) -> str:
    """Etiqueta declarada de una dimensión: texto no vacío o el cubo ``fallback``."""
    text = str(value if value is not None else "").strip()
    return text or fallback


def _realized(round_trips: Sequence[Mapping[str, Any]]) -> list[float]:
    """``realizedR`` finitos de los ciclos (un valor ilegible se declara hueco, no cuenta)."""
    values: list[float] = []
    for trip in round_trips or ():
        value = finite_number(trip.get("realizedR"))
        if value is not None:
            values.append(value)
    return values


# ── Descomposición del payoff ────────────────────────────────────────────────────


def payoff_decomposition(round_trips: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Descompone ``expectancyR`` en ganancia media, pérdida media y tasa de acierto.

    Identidad verificable: ``expectancyR = winRate·avgWinR + (1 − winRate)·avgLossR``;
    ``identityGap`` publica el residuo (debe ser ~0 salvo redondeo) para que la cuenta sea
    auditable y no una caja negra. Sin muestra, todo extremo es ``None`` (nunca ``0``).
    """
    values = _realized(round_trips)
    n = len(values)
    if n == 0:
        return {
            "cycles": 0,
            "wins": 0,
            "losses": 0,
            "winRate": None,
            "avgWinR": None,
            "avgLossR": None,
            "payoffRatio": None,
            "expectancyR": None,
            "identityGap": None,
        }
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value <= 0]
    win_rate = len(wins) / n
    avg_win = _mean(wins)
    avg_loss = _mean(losses)
    payoff_ratio: float | None = None
    if avg_win is not None and avg_loss is not None and abs(avg_loss) > 0.0:
        payoff_ratio = avg_win / abs(avg_loss)
    expectancy = _mean(values)
    identity = win_rate * (avg_win or 0.0) + (1.0 - win_rate) * (avg_loss or 0.0)
    identity_gap = None if expectancy is None else expectancy - identity
    return {
        "cycles": n,
        "wins": len(wins),
        "losses": len(losses),
        "winRate": win_rate,
        "avgWinR": avg_win,
        "avgLossR": avg_loss,
        "payoffRatio": payoff_ratio,
        "expectancyR": expectancy,
        "identityGap": identity_gap,
    }


# ── Índice de excursiones (MAE/MFE) por ciclo ────────────────────────────────────


def cycle_key(round_trip: Mapping[str, Any]) -> tuple[str, str, str]:
    """Clave ``(symbol, entryDay, exitDay)`` normalizada de un ciclo (o de una excursión)."""
    return (
        str(round_trip.get("symbol") or "").strip(),
        normalize_day(round_trip.get("entryDay")) or "",
        normalize_day(round_trip.get("exitDay")) or "",
    )


def index_excursions(rows: Sequence[Excursion | Mapping[str, Any]]) -> dict[tuple[str, str, str], Any]:
    """``{(symbol, entryDay, exitDay): excursión}`` de la lista de ``excursions(...)``.

    El orden de ``excursions(...)`` ya es determinista; esta función sólo pliega por clave.
    """
    indexed: dict[tuple[str, str, str], Any] = {}
    for row in rows or ():
        record = row.to_dict() if isinstance(row, Excursion) else row
        indexed[cycle_key(record)] = row
    return indexed


#: Nombres del campo de excursión en la dataclass (``snake``) y en su ``to_dict`` (``camel``).
_EXCURSION_FIELDS: dict[str, tuple[str, str]] = {
    "mae": ("mae_r", "maeR"),
    "mfe": ("mfe_r", "mfeR"),
}


def _excursion_field(row: Any, name: str) -> float | None:
    """MAE/MFE (R) de una excursión (``Excursion`` o su ``to_dict``); ``None`` si no es medible."""
    attrs = _EXCURSION_FIELDS[name]
    if isinstance(row, Excursion):
        return finite_number(getattr(row, attrs[0], None))
    if isinstance(row, Mapping):
        for key in attrs:
            value = finite_number(row.get(key))
            if value is not None:
                return value
        return None
    return None


# ── Atribución por dimensión ─────────────────────────────────────────────────────


def attribute_by(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    excursions_by_cycle: Mapping[tuple[str, str, str], Any] | None = None,
) -> list[dict[str, Any]]:
    """Buckets deterministas (orden por etiqueta) de la muestra según ``key_fn``.

    Cada bucket publica los ciclos, la expectativa, el acierto, la mediana, el R total, la
    descomposición de payoff y —si hay excursiones medidas— media de MAE/MFE y cuántos ciclos
    quedaron sin excursión medible. Un cubo sin ciclos medibles no es una fila: no se inventa.
    """
    indexed = excursions_by_cycle or {}
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for trip in round_trips or ():
        grouped.setdefault(str(key_fn(trip) or "").strip() or SIN_REGIMEN, []).append(trip)

    out: list[dict[str, Any]] = []
    for label in sorted(grouped):
        trips = grouped[label]
        values = _realized(trips)
        if not values:
            continue
        maes: list[float] = []
        mfes: list[float] = []
        unmeasured = 0
        for trip in trips:
            row = indexed.get(cycle_key(trip))
            if row is None:
                unmeasured += 1
                continue
            mae = _excursion_field(row, "mae")
            mfe = _excursion_field(row, "mfe")
            if mae is None or mfe is None:
                unmeasured += 1
                continue
            maes.append(mae)
            mfes.append(mfe)
        decomposition = payoff_decomposition(trips)
        out.append(
            {
                "label": label,
                "cycles": len(values),
                "measuredCycles": len(values),
                "expectancyR": decomposition["expectancyR"],
                "hitRate": (sum(1 for value in values if value > 0) / len(values)),
                "medianR": _median(values),
                "realizedRTotal": sum(values),
                "payoff": decomposition,
                "meanMaeR": _mean(maes),
                "meanMfeR": _mean(mfes),
                "excursionsMeasured": len(maes),
                "excursionsUnmeasured": unmeasured,
            }
        )
    return out


def regime_key_reader(regime_by_day: Mapping[str, Any]) -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión RÉGIMEN: agregado del ``entryDay`` o ``sin_regimen``."""
    table = regime_by_day or {}

    def _read(trip: Mapping[str, Any]) -> str:
        day = normalize_day(trip.get("entryDay"))
        return _label(table.get(day) if day else None, SIN_REGIMEN)

    return _read


def strategy_key_reader() -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión ESTRATEGIA: ``strategyVersion`` o ``sin_version``."""

    def _read(trip: Mapping[str, Any]) -> str:
        return _label(trip.get("strategyVersion"), SIN_VERSION)

    return _read


def sector_key_reader(sector_by_symbol: Mapping[str, Any]) -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión SECTOR: el del catálogo (aproximado) o ``sin_sector``."""
    table = sector_by_symbol or {}

    def _read(trip: Mapping[str, Any]) -> str:
        symbol = str(trip.get("symbol") or "").strip()
        return _label(table.get(symbol) if symbol else None, SIN_SECTOR)

    return _read


def symbol_key_reader() -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión ACTIVO: el símbolo o ``sin_simbolo``."""

    def _read(trip: Mapping[str, Any]) -> str:
        return _label(trip.get("symbol"), SIN_SIMBOLO)

    return _read


# ── Estudio de excursión: captura de MFE y severidad de MAE ──────────────────────


def capture_study(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    excursions_by_cycle: Mapping[tuple[str, str, str], Any] | None = None,
    reversal_mfe_min_r: float = REVERSAL_MFE_MIN_R,
) -> dict[str, Any]:
    """Cuánto premio favorable (MFE) se capturó y cuánto se dejó sobre la mesa.

    Sólo entran ciclos con MFE positivo y medible (``mfeR > 0``): sin premio previo, la
    "captura" no está definida y se declara hueco (``None``). ``reversedCount`` cuenta los
    ciclos que llegaron a ``+reversal_mfe_min_r`` y aun así cerraron en ``<= 0`` (premio dado
    la vuelta). Muestra vacía ⇒ medias ``None``.
    """
    indexed = excursions_by_cycle or {}
    captures: list[float] = []
    left_on_table: list[float] = []
    reversed_count = 0
    measured = 0
    not_measured = 0
    for trip in round_trips or ():
        realized = finite_number(trip.get("realizedR"))
        row = indexed.get(cycle_key(trip))
        mfe = None
        if row is not None:
            mfe = _excursion_field(row, "mfe")
        if realized is None or mfe is None or mfe <= 0.0:
            not_measured += 1
            continue
        measured += 1
        captures.append(realized / mfe)
        left_on_table.append(mfe - realized)
        if mfe >= reversal_mfe_min_r and realized <= 0.0:
            reversed_count += 1
    return {
        "measuredCycles": measured,
        "notMeasuredCycles": not_measured,
        "meanCapture": _mean(captures),
        "medianCapture": _median(captures),
        "meanLeftOnTableR": _mean(left_on_table),
        "medianLeftOnTableR": _median(left_on_table),
        "reversedCount": reversed_count,
        "reversalMfeMinR": reversal_mfe_min_r,
    }


def mae_severity(
    excursion_rows: Sequence[Excursion | Mapping[str, Any]],
    *,
    thresholds: Sequence[float] = STOP_BREACH_THRESHOLDS,
) -> dict[str, Any]:
    """Cuántos perdedores atravesaron el stop (MAE peor que cada umbral, en R).

    Un MAE ``< -1R`` significa que la excursión adversa superó el riesgo declarado (stop no
    respetado / gap). Se publica el recuento y la fracción por umbral; sin muestra medida, la
    fracción es ``None`` (nunca ``0``). Los cubos de umbral son deterministas y ordenados.
    """
    maes: list[float] = []
    for row in excursion_rows or ():
        mae = _excursion_field(row, "mae")
        if mae is not None:
            maes.append(mae)
    measured = len(maes)
    breaches: dict[str, dict[str, Any]] = {}
    for threshold in sorted(set(float(t) for t in thresholds), reverse=True):
        count = sum(1 for mae in maes if mae < threshold)
        key = format(threshold, "+.2f")
        breaches[key] = {
            "thresholdR": threshold,
            "count": count,
            "share": (count / measured) if measured else None,
        }
    return {
        "measured": measured,
        "meanMaeR": _mean(maes),
        "minMaeR": min(maes) if maes else None,
        "breaches": breaches,
    }


# ── Concentración: ¿el signo depende de unos pocos ciclos? ───────────────────────


def concentration(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """Peso de los ``k`` mejores/peores ciclos y si el signo depende de uno solo.

    ``classification = "concentrated"`` cuando retirar el **único** peor ciclo voltea la
    expectativa a ``> 0`` (la ventana negativa descansa en un ciclo). En cualquier otro caso
    ``"broad"``. Orden determinista por ``(realizedR, symbol, entryDay)``. Muestra vacía ⇒
    extremos ``None``.
    """
    rows: list[tuple[float, str, str]] = []
    for trip in round_trips or ():
        value = finite_number(trip.get("realizedR"))
        if value is None:
            continue
        rows.append((value, str(trip.get("symbol") or ""), normalize_day(trip.get("entryDay")) or ""))
    if not rows:
        return {
            "cycles": 0,
            "topK": int(top_k),
            "worstContributionR": None,
            "bestContributionR": None,
            "realizedRTotal": None,
            "expectancyR": None,
            "expectancyWithoutWorstR": None,
            "signFlipsWithoutWorst": None,
            "classification": None,
        }
    rows.sort(key=lambda item: (item[0], item[1], item[2]))
    values = [value for value, _symbol, _day in rows]
    total = sum(values)
    expectancy = _mean(values)
    k = max(1, int(top_k))
    worst = values[:k]
    best = values[-k:]
    without_worst = values[1:]
    expectancy_without_worst = _mean(without_worst)
    sign_flips = (
        expectancy_without_worst is not None and expectancy is not None
        and expectancy_without_worst > 0.0 and expectancy <= 0.0
    )
    return {
        "cycles": len(values),
        "topK": k,
        "worstContributionR": sum(worst),
        "bestContributionR": sum(best),
        "realizedRTotal": total,
        "expectancyR": expectancy,
        "expectancyWithoutWorstR": expectancy_without_worst,
        "signFlipsWithoutWorst": bool(sign_flips),
        "classification": "concentrated" if sign_flips else "broad",
    }


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_dia_d_attribution_artifact(
    *,
    window_from: Any,
    window_to: Any,
    days: Sequence[Any],
    operable_days: int,
    round_trips: Sequence[Mapping[str, Any]],
    excursions_rows: Sequence[Excursion | Mapping[str, Any]] = (),
    regime_by_day: Mapping[str, Any] | None = None,
    sector_by_symbol: Mapping[str, Any] | None = None,
    watch: Sequence[Any] = (),
    watch_source: str = "catalog",
    universe_coverage: Mapping[str, Any] | None = None,
    probe: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    top_k: int = 5,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico de la atribución (puro y determinista: sin reloj ni aleatorios).

    Reutiliza ``build_value_scorecard`` para el veredicto/`evidenceQuality` de la ventana y
    ``excursions(...)`` para MAE/MFE (no duplica umbrales ni recálculos). El desglose por
    dimensión es descriptivo; los cubos sin muestra no aparecen.
    """
    unique_days = sorted({normalize_day(day) for day in days if normalize_day(day)})
    ordered_trips = sorted(
        (dict(trip) for trip in round_trips or ()),
        key=lambda trip: (
            str(trip.get("entryDay") or ""),
            str(trip.get("symbol") or ""),
            str(trip.get("exitDay") or ""),
        ),
    )
    index = index_excursions(excursions_rows)

    window_scorecard = build_value_scorecard("WINDOW", round_trips=ordered_trips, days=unique_days)

    by_regime = attribute_by(ordered_trips, key_fn=regime_key_reader(regime_by_day or {}), excursions_by_cycle=index)
    by_strategy = attribute_by(ordered_trips, key_fn=strategy_key_reader(), excursions_by_cycle=index)
    by_sector = attribute_by(ordered_trips, key_fn=sector_key_reader(sector_by_symbol or {}), excursions_by_cycle=index)
    by_symbol = attribute_by(ordered_trips, key_fn=symbol_key_reader(), excursions_by_cycle=index)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "DIA_D_AUTO_ATTRIBUTION",
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
        },
        "decomposition": payoff_decomposition(ordered_trips),
        "byRegime": by_regime,
        "byStrategy": by_strategy,
        "bySector": by_sector,
        "bySymbol": by_symbol,
        "capture": capture_study(ordered_trips, excursions_by_cycle=index),
        "maeSeverity": mae_severity(excursions_rows),
        "concentration": concentration(ordered_trips, top_k=top_k),
        "meta": {
            "watch": [str(symbol) for symbol in watch],
            "watchSource": str(watch_source),
            "survivorBiasRisk": str(watch_source) == "catalog",
            "sectorSource": "catalogo_actual",
            "regimeSource": "census_operable_days.aggregate",
            "universeCoverage": dict(universe_coverage or {}),
            **{str(key): value for key, value in (meta or {}).items()},
        },
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "DEFAULT_LIMITS",
    "REVERSAL_MFE_MIN_R",
    "SCHEMA_VERSION",
    "SIN_REGIMEN",
    "SIN_SECTOR",
    "SIN_SIMBOLO",
    "SIN_VERSION",
    "STOP_BREACH_THRESHOLDS",
    "attribute_by",
    "build_dia_d_attribution_artifact",
    "capture_study",
    "concentration",
    "cycle_key",
    "excursions",
    "index_excursions",
    "mae_severity",
    "payoff_decomposition",
    "regime_key_reader",
    "sector_key_reader",
    "strategy_key_reader",
    "symbol_key_reader",
]
