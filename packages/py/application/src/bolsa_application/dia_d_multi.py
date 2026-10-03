"""V2.88.41 · DÍA-D AUTO — ATRIBUCIÓN MULTIRREGIMEN (pura, sin I/O).

Qué es
------
El agregado longitudinal (``dia_d_longitudinal``) mide *cuánto* rinde **una** ventana OOS
(p. ej. el año natural 2022) y la atribución (``dia_d_attribution``) descompone esa MISMA
muestra por dimensión. Este módulo añade la base **multirregimen**: pliega las corridas de
VARIOS años (una por año, con universo point-in-time) y descompone la expectativa por

* **año** — ``byYear`` (una fila por ejercicio medido);
* **régimen** — ``byRegime`` (agregado trial del día de decisión) y ``byOperationalRegime``
  (su mapa operativo);
* **resultado** — cada cubo publica la severidad de MAE por POBLACIÓN (ALL/WINNERS/LOSERS);
* **excursión** — cada cubo publica la captura de MFE (``capture_study``);
* y la celda **año × régimen** — ``byYearByRegime`` (sólo celdas medidas).

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None`` / ``NOT_MEASURED``; **nunca** se rellena con ``0``.
* La unidad es el **ciclo**; la atribución temporal es por **``entryDay``** (D34-02).
* Un año sin universo PIT elegible o sin barras se declara en ``coverage.yearsNotMeasured``;
  un cubo sin ciclos medibles no aparece.
* Se **reutiliza** ``payoff_decomposition``/``capture_study``/``mae_severity``/
  ``concentration`` de ``dia_d_attribution`` (no se duplican umbrales ni veredictos).
* La capa es **advisory y read-only**: **no** cambia el motor, los umbrales, ``TOP_N`` ni la
  allocation, y **no** escribe en PostgreSQL.
* El desglose es **descriptivo**, no causal: ``CONFIRMED`` sigue reservado a evidencia PAPER.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from bolsa_application.dia_d_attribution import (
    SIN_REGIMEN,
    capture_study,
    concentration,
    cycle_key,
    index_excursions,
    mae_severity,
    payoff_decomposition,
    regime_key_reader,
)
from bolsa_application.dia_d_auto import finite_number, normalize_day
from bolsa_application.dia_d_auto_feedback import build_value_scorecard
from bolsa_application.dia_d_longitudinal import Excursion

#: Versión del esquema del artefacto multirregimen. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-multi-v1"

#: Tipo del artefacto (una atribución, no una comparación declarado/ejecutado).
KIND = "DIA_D_AUTO_MULTI_ATTRIBUTION"

#: Cubos declarados para una etiqueta ausente (nunca se adivina la dimensión).
SIN_YEAR = "sin_ejercicio"
SIN_OPERATIONAL = "sin_regimen_operativo"

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Atribucion DESCRIPTIVA, no causal: descompone la muestra medida, no explica el mercado.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. La media de una muestra vacia es None.",
    "La unidad es el CICLO; la atribucion temporal es por entryDay (dia de decision).",
    "El regimen es el agregado trial por dia (census_operable_days) y el operativo su map; la "
    "lectura multirregimen es DESCRIPTIVA y depende de la disponibilidad real de barras por ano.",
    "El sector es el del catalogo ACTUAL (no point-in-time); aqui no se atribuye por sector.",
    "MAE/MFE son extremos ENTRE DIAS (barras D1); el dia de entrada puede incluir excursion previa al fill.",
    "La captura es capturedR/MFE con capturedR=max(realizedR,0): vive en [0,+inf) y NO cambia de signo.",
    "La severidad de MAE se publica por POBLACION (ALL/WINNERS/LOSERS): la fraccion de TODOS los "
    "ciclos con MAE < -1R NO es la de PERDEDORES (un ganador puede sufrirla).",
    "CONFIRMED sigue reservado a evidencia PAPER y NO se emite al observar el replay.",
    "Un ano sin universo PIT elegible o sin barras se declara en coverage.yearsNotMeasured; no se inventa.",
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


def _year_of(day: Any) -> str:
    """Año (``YYYY``) de un día ISO; ``""`` si no es legible (nunca se adivina)."""
    normalized = normalize_day(day)
    year = normalized[:4]
    return year if len(year) == 4 and year.isdigit() else ""


def _excursion_values(row: Any) -> tuple[float | None, float | None]:
    """MAE/MFE (R) de una excursión (``Excursion`` o su ``to_dict``); ``None`` si no es medible."""
    if isinstance(row, Excursion):
        return finite_number(row.mae_r), finite_number(row.mfe_r)
    if isinstance(row, Mapping):
        return finite_number(row.get("maeR")), finite_number(row.get("mfeR"))
    return None, None


# ── Lectores de dimensión ────────────────────────────────────────────────────────


def year_key_reader() -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión AÑO: ``YYYY`` del ``entryDay`` o ``""`` (cae en su cubo)."""

    def _read(trip: Mapping[str, Any]) -> str:
        return _year_of(trip.get("entryDay"))

    return _read


def operational_regime_key_reader(
    operational_by_day: Mapping[str, Any],
) -> Callable[[Mapping[str, Any]], str]:
    """Lector de la dimensión RÉGIMEN OPERATIVO: mapa del ``entryDay`` o ``""``."""
    table = operational_by_day or {}

    def _read(trip: Mapping[str, Any]) -> str:
        day = normalize_day(trip.get("entryDay"))
        return _label(table.get(day) if day else None, "")

    return _read


# ── Agregación de un cubo (payoff + excursión + captura + severidad por población) ─


def _summarize(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    indexed: Mapping[tuple[str, str, str], Any],
) -> dict[str, Any]:
    """Resumen de UN cubo: payoff, excursión media, captura de MFE y severidad por población.

    ``cycles`` es la muestra MEDIBLE (``realizedR`` finito); un cubo sin ella no se emite.
    Se reutilizan ``payoff_decomposition``/``capture_study``/``mae_severity``: no se duplican
    umbrales (``-1R``/``-1.25R``/``-1.5R``) ni definiciones.
    """
    trips = list(round_trips or ())
    decomposition = payoff_decomposition(trips)
    values = [
        value for trip in trips if (value := finite_number(trip.get("realizedR"))) is not None
    ]
    maes: list[float] = []
    mfes: list[float] = []
    measured = 0
    unmeasured = 0
    for trip in trips:
        mae, mfe = _excursion_values(indexed.get(cycle_key(trip)))
        if mae is not None and mfe is not None:
            maes.append(mae)
            mfes.append(mfe)
            measured += 1
        else:
            unmeasured += 1
    return {
        "cycles": len(values),
        "expectancyR": decomposition["expectancyR"],
        "hitRate": decomposition["winRate"],
        "medianR": _median(values),
        "realizedRTotal": sum(values) if values else None,
        "meanMaeR": _mean(maes),
        "meanMfeR": _mean(mfes),
        "excursionsMeasured": measured,
        "excursionsUnmeasured": unmeasured,
        "capture": capture_study(trips, excursions_by_cycle=indexed),
        "maeSeverity": mae_severity(trips, excursions_by_cycle=indexed),
    }


def _group_by(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    fallback: str,
) -> dict[str, list[Mapping[str, Any]]]:
    """Agrupa los ciclos por etiqueta; una etiqueta ausente cae en su cubo ``fallback``."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for trip in round_trips or ():
        label = _label(key_fn(trip), fallback)
        grouped.setdefault(label, []).append(trip)
    return grouped


def _dimension(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    fallback: str,
    indexed: Mapping[tuple[str, str, str], Any],
) -> list[dict[str, Any]]:
    """Buckets deterministas (orden por etiqueta); un cubo sin ciclos medibles no aparece."""
    grouped = _group_by(round_trips, key_fn=key_fn, fallback=fallback)
    rows: list[dict[str, Any]] = []
    for label in sorted(grouped):
        summary = _summarize(grouped[label], indexed=indexed)
        if summary["cycles"] <= 0:
            continue
        rows.append({"label": label, **summary})
    return rows


def _matrix(
    round_trips: Sequence[Mapping[str, Any]],
    *,
    indexed: Mapping[tuple[str, str, str], Any],
    regime_by_day: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Celdas AÑO × RÉGIMEN medidas (una fila por celda; una celda vacía no se emite)."""
    table = regime_by_day or {}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for trip in round_trips or ():
        year = _year_of(trip.get("entryDay")) or SIN_YEAR
        day = normalize_day(trip.get("entryDay"))
        regime = _label(table.get(day) if day else None, SIN_REGIMEN)
        grouped.setdefault((year, regime), []).append(trip)
    rows: list[dict[str, Any]] = []
    for year, regime in sorted(grouped):
        summary = _summarize(grouped[(year, regime)], indexed=indexed)
        if summary["cycles"] <= 0:
            continue
        rows.append({"year": year, "regime": regime, **summary})
    return rows


def _rename(rows: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    """Reetiqueta ``label`` con el nombre de la dimensión (``year``/``regime``)."""
    return [
        {key: row.get("label"), **{name: value for name, value in row.items() if name != "label"}}
        for row in rows
    ]


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_dia_d_multi_artifact(
    *,
    years: Sequence[Any],
    windows: Sequence[Mapping[str, Any]],
    round_trips: Sequence[Mapping[str, Any]],
    excursions_rows: Sequence[Excursion | Mapping[str, Any]] = (),
    regime_by_day: Mapping[str, Any] | None = None,
    operational_regime_by_day: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    top_k: int = 5,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico de la atribución multirregimen (puro y determinista: sin reloj).

    ``windows`` declara, por año, la ventana pedida/efectiva y si se midió (``measured``) o el
    ``reason`` del hueco. Reutiliza ``build_value_scorecard`` para el veredicto/``evidenceQuality``
    global y ``excursions(...)`` para MAE/MFE (no duplica umbrales ni recálculos).
    """
    ordered_trips = sorted(
        (dict(trip) for trip in round_trips or ()),
        key=lambda trip: (
            str(trip.get("entryDay") or ""),
            str(trip.get("symbol") or ""),
            str(trip.get("exitDay") or ""),
        ),
    )
    index = index_excursions(excursions_rows)
    window_rows = sorted((dict(window) for window in windows or ()), key=lambda w: str(w.get("year")))
    requested = list(dict.fromkeys(str(year) for year in years))
    measured = {str(window.get("year")) for window in window_rows if window.get("measured")}
    no_medido: dict[str, str] = {
        str(window.get("year")): _label(window.get("reason"), "no_medido")
        for window in window_rows
        if not window.get("measured")
    }
    # Un año pedido sin ventana declarada no puede quedar fuera de la cobertura (fail-closed).
    for year in requested:
        if year not in measured and year not in no_medido:
            no_medido[year] = "sin_ventana_declarada"
    not_measured = [
        {"year": year, "reason": reason} for year, reason in sorted(no_medido.items())
    ]

    days: list[Any] = []
    for window in window_rows:
        days.extend(window.get("days") or ())
    unique_days = sorted({day for raw in days if (day := normalize_day(raw))})

    window_scorecard = build_value_scorecard("WINDOW", round_trips=ordered_trips, days=unique_days)

    by_year = _dimension(
        ordered_trips, key_fn=year_key_reader(), fallback=SIN_YEAR, indexed=index
    )
    # Un año MEDIDO puede no aportar ni un ciclo: se declara aparte (no se confunde con el hueco
    # de cobertura, que es un año que ni se pudo correr).
    years_with_cycles = {str(row["label"]) for row in by_year}
    years_empty = [
        year for year in requested if year in measured and year not in years_with_cycles
    ]
    by_regime = _dimension(
        ordered_trips,
        key_fn=regime_key_reader(regime_by_day or {}),
        fallback=SIN_REGIMEN,
        indexed=index,
    )
    by_operational = _dimension(
        ordered_trips,
        key_fn=operational_regime_key_reader(operational_regime_by_day or {}),
        fallback=SIN_OPERATIONAL,
        indexed=index,
    )
    matrix = _matrix(ordered_trips, indexed=index, regime_by_day=regime_by_day or {})

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "basis": "entryDay",
        "coverage": {
            "yearsRequested": requested,
            "yearsMeasured": [year for year in requested if year in measured],
            "yearsEmpty": years_empty,
            "yearsNotMeasured": not_measured,
        },
        "windows": window_rows,
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
        "capture": capture_study(ordered_trips, excursions_by_cycle=index),
        "maeSeverity": mae_severity(ordered_trips, excursions_by_cycle=index),
        "concentration": concentration(ordered_trips, top_k=top_k),
        "byYear": _rename(by_year, "year"),
        "byRegime": _rename(by_regime, "regime"),
        "byOperationalRegime": _rename(by_operational, "regime"),
        "byYearByRegime": matrix,
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "DEFAULT_LIMITS",
    "KIND",
    "SCHEMA_VERSION",
    "SIN_OPERATIONAL",
    "SIN_YEAR",
    "build_dia_d_multi_artifact",
    "operational_regime_key_reader",
    "year_key_reader",
]
