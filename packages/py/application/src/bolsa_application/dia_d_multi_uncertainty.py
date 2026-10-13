"""V2.88.42 · DÍA-D AUTO — DE PUNTO A BANDA: incertidumbre del SORTEO del venue (puro).

Qué es
------
La atribución multirregimen (``dia_d_multi``, ``dia-d-multi-v1``) publica por cubo (año,
régimen, año × régimen) una expectativa ``expectancyR`` y un R total como **puntos**. Este
módulo añade la **banda**: pliega ``K`` corridas del MISMO harness, cada una con el **sorteo
del venue** desplazado (``fill_seed(bar_tick + k, symbol)``; ``k = 0`` es la realización de
producción), y publica por cada cubo

* ``bands`` — ``min``/``median``/``max``/``mean``/``stdev`` de cada métrica (``expectancyR``,
  ``realizedRTotal``, ``hitRate``, ``meanMaeR``, ``meanMfeR``, ``captureMean``, ``reversedCount``,
  ``cycles``); ``None`` sin muestra, **nunca** ``0``;
* ``validity`` — bloque con **DOS etiquetas separadas** (H1): ``sensitivityBand`` (lo que los ``K``
  re-sorteos del venue SÍ miden: ``crossesZeroR`` y ``pointCitable`` acotado por
  ``pointCitableScope``) y ``statisticalConfidence`` (``NOT_MEASURED`` por defecto: re-sorteos del
  mismo dato **no** son observaciones independientes ⇒ jamás se infiere de ellas). Con menos de
  ``MIN_DRAWS_FOR_BAND`` sorteos **no** hay banda que cite un punto: se declara
  (``insufficient_draws``). ``statisticalConfidence`` solo pasa a ``MEASURED`` si el llamante
  declara ``design = "independent_sample"`` **y** aporta procedencia verificable (H1.1): sin
  evidencia queda ``NOT_MEASURED`` con ``missingProvenance``, y sin muestra efectiva queda
  ``NOT_MEASURED`` con reason ``no_effective_sample`` (la procedencia no crea la medición).

Por qué existe
--------------
El instrumento OOS de este repositorio **ya demostró** (``W3.3``, v2.88.16.3) que la realización
del venue mueve el resultado más que el efecto que se quiere medir: la banda de ``K = 12`` sorteos
cruzaba el cero (``σ(R) = 10.14``, IC95 ``±5.74``) y ``point_citable = False``. Citar un punto de
``v2.88.41`` sin su banda es citar un dado como si fuera una constante: el **determinismo no es
validez**. Esta capa mide ESE ruido; no decide.

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* Un cubo que no aparece en un sorteo baja ``drawsWithCell`` (no se inventa un valor).
* La capa es **advisory y read-only**: no cambia el motor, los umbrales, ``TOP_N`` ni la
  allocation; es un **observador** del mismo instrumento.
* La banda se cita **entera o no se cita**; el artefacto es **determinista** (sin reloj ni azar:
  las ``K`` semillas son una entrada declarada).
* La banda mide el **ruido del sorteo del venue** (mismo dato, misma estrategia), **no** la
  incertidumbre de muestreo del ciclo ni el futuro.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.dia_d_auto import finite_number

#: Versión del esquema del artefacto de banda. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-multi-band-v3"

#: Tipo del artefacto (una banda de la atribución, no una atribución).
KIND = "DIA_D_AUTO_MULTI_BAND"

#: Sorteos mínimos para afirmar una banda: con uno solo no hay dispersión que medir, y un
#: ``pointCitable`` con ``K = 1`` sería el error que ``W3.3`` documentó (citar un dado).
MIN_DRAWS_FOR_BAND = 2

#: Z del IC95 del criterio de citabilidad (el MISMO de ``W3.3``).
CI95_Z = 1.96

#: Diseño de la muestra: de dónde vienen los ``K`` sorteos. Se DECLARA; no se adivina (H1).
#: ``venue_draw`` = re-sorteos del MISMO dato (solo mide sensibilidad al azar del venue);
#: ``independent_sample`` = observaciones INDEPENDIENTES declaradas por el llamante.
DESIGN_VENUE_DRAW = "venue_draw"
DESIGN_INDEPENDENT = "independent_sample"

#: Alcance de ``pointCitable``: citabilidad DE LA BANDA DE SENSIBILIDAD, NUNCA una afirmación
#: de confianza estadística ni de rentabilidad demostrada (H1).
POINT_CITABLE_SCOPE = "sensitivity_band_only_not_statistical_confidence"

#: Motivo declarado por el que la confianza estadística NO se mide con re-sorteos del venue.
STATISTICAL_CONFIDENCE_NOT_MEASURED_REASON = (
    "Los K sorteos desplazan el ancla de la semilla del simulador sobre el MISMO dato historico: "
    "no son observaciones independientes de una poblacion. La banda mide sensibilidad al sorteo "
    "del venue, no la incertidumbre estadistica de la estrategia."
)

#: Lo que exigiría medir la confianza estadística (nunca se infiere de re-sorteos).
STATISTICAL_CONFIDENCE_REQUIRES = (
    "Observaciones INDEPENDIENTES declaradas por el llamante (design='independent_sample') y un "
    "procedimiento estadistico adecuado; jamas se infiere de re-sorteos del mismo dato."
)

#: Campos de PROCEDENCIA exigidos para acreditar `statisticalConfidence = MEASURED` (H1.1): una
#: mera declaración `independent_sample` NO basta. Sin evidencia verificable de ventanas de
#: evaluación independientes, método de muestreo, tamaño de muestra, unidad de observación y
#: tratamiento de dependencia temporal, la etiqueta queda NOT_MEASURED con el hueco declarado.
PROVENANCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "evaluationWindows",
    "samplingMethod",
    "sampleSize",
    "observationUnit",
    "temporalDependence",
)

#: Motivo: el llamante pidió `independent_sample` sin declarar NINGUNA procedencia (H1.1).
STATISTICAL_CONFIDENCE_PROVENANCE_MISSING_REASON = "provenance_missing"

#: Motivo: la procedencia declarada está INCOMPLETA; `missingProvenance` lista los campos.
STATISTICAL_CONFIDENCE_PROVENANCE_INCOMPLETE_REASON = "provenance_incomplete"

#: Motivo: los datos declaran un re-sorteo del venue (semilla desplazada) ⇒ NO son independientes.
STATISTICAL_CONFIDENCE_VENUE_DRAW_CONTRADICTION_REASON = "venue_draw_declared_independent"

#: Motivo: NO hay muestra efectiva (banda ausente o con menos de ``MIN_DRAWS_FOR_BAND`` sorteos):
#: sin datos que resumir no se computa ninguna estadística, por completa que sea la procedencia.
STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON = "no_effective_sample"

#: Dimensiones declaradas de un cubo (nunca se adivina la etiqueta).
DIM_GLOBAL = "GLOBAL"
DIM_YEAR = "YEAR"
DIM_REGIME = "REGIME"
DIM_OPERATIONAL = "OPERATIONAL"
DIM_YEAR_REGIME = "YEAR_REGIME"

#: Orden determinista de las dimensiones en la salida.
_DIM_ORDER: tuple[str, ...] = (
    DIM_GLOBAL,
    DIM_YEAR,
    DIM_REGIME,
    DIM_OPERATIONAL,
    DIM_YEAR_REGIME,
)

#: Métricas que se pliegan por cubo (todas publicadas como banda, o ``None`` sin muestra).
METRICS: tuple[str, ...] = (
    "cycles",
    "expectancyR",
    "realizedRTotal",
    "hitRate",
    "meanMaeR",
    "meanMfeR",
    "captureMean",
    "reversedCount",
)

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "La banda mide el RUIDO DEL SORTEO DEL VENUE (K re-sorteos del MISMO dato y estrategia), no la "
    "incertidumbre de muestreo del ciclo ni el futuro.",
    "Un punto solo es citable si la banda de R NO cruza cero Y |media| > 1.96*SE, con K >= 2; con "
    "menos sorteos se declara insufficient_draws y pointCitable=False.",
    "H1: las etiquetas sensitivityBand y statisticalConfidence NO se confunden. La banda de K "
    "re-sorteos del MISMO dato mide SOLO sensibilidad al sorteo del venue; la confianza estadistica "
    "queda NOT_MEASURED salvo que el llamante declare observaciones independientes CON procedencia "
    "verificable (H1.1).",
    "H1.1: declarar design='independent_sample' NO basta. Sin evidencia de ventanas de evaluacion "
    "independientes, metodo de muestreo, tamano de muestra, unidad de observacion y tratamiento de "
    "la dependencia temporal, statisticalConfidence sigue NOT_MEASURED con missingProvenance. Sin "
    "muestra efectiva (banda ausente o con menos de MIN_DRAWS_FOR_BAND sorteos) queda NOT_MEASURED "
    "con reason=no_effective_sample, aunque la procedencia sea completa.",
    "pointCitable esta acotado por pointCitableScope: es citabilidad de la banda de sensibilidad, "
    "NUNCA una afirmacion de rentabilidad demostrada.",
    "La banda se cita ENTERA o no se cita: el determinismo (reproducibilidad byte a byte) NO es "
    "validez.",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. Un cubo ausente en un sorteo baja "
    "drawsWithCell, no se inventa.",
    "Un cubo puede aparecer en pocos sorteos: drawsWithCell es el n EFECTIVO de su banda y una "
    "banda con n pequeno es fragil (se declara, no se oculta).",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas). "
    "CONFIRMED sigue reservado a evidencia PAPER.",
    "La unidad es el CICLO; la atribucion temporal es por entryDay (dia de decision).",
    "El regimen es el agregado trial por dia; el sector es el del catalogo ACTUAL (no point-in-time).",
    "MAE/MFE son extremos ENTRE DIAS (barras D1); el dia de entrada puede incluir excursion previa al fill.",
    "Determinismo: mismas K semillas => payload identico (sin reloj, ULID ni azar global).",
)


# ── Utilidades numéricas (None cuando no hay muestra; nunca 0) ───────────────────


def _mean(values: Sequence[float]) -> float | None:
    """Media de una muestra ordenada o ``None`` si está vacía."""
    return sum(values) / len(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    """Mediana de una muestra ordenada o ``None`` si está vacía (determinista)."""
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _stdev(values: Sequence[float]) -> float | None:
    """Desviación típica POBLACIONAL de la muestra (``None`` si vacía; ``0.0`` si ``n = 1``).

    Los ``K`` sorteos SON la muestra (no una muestra de una población mayor): la desviación
    poblacional es la lectura honesta. Una sola lectura no tiene dispersión medible ⇒ ``0.0``.
    """
    if not values:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _stats(values: Sequence[float]) -> dict[str, Any] | None:
    """Resumen declarado de una métrica: ``min``/``median``/``max``/``mean``/``stdev``/``n``.

    Se ordena la muestra ANTES de sumar: el payload no puede depender del orden de llegada de
    los sorteos (determinismo byte a byte). ``None`` sin muestra (un hueco no es un ``0``).
    """
    ordered = sorted(values)
    if not ordered:
        return None
    mean = _mean(ordered)
    assert mean is not None  # la muestra no está vacía
    return {
        "n": len(ordered),
        "min": ordered[0],
        "median": _median(ordered),
        "max": ordered[-1],
        "mean": mean,
        "stdev": _stdev(ordered),
    }


def _provenance_gaps(provenance: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Campos de procedencia que FALTAN o son inválidos para acreditar independencia (H1.1).

    Función pura y tolerante: un ``provenance`` ausente o malformado NO levanta; devuelve TODOS
    los campos exigidos como huecos. No se adivina: si no hay evidencia verificable de ventanas
    independientes, método de muestreo, tamaño, unidad de observación y tratamiento de dependencia
    temporal, la confianza estadística NO se mide. El orden es el de ``PROVENANCE_REQUIRED_FIELDS``
    (determinista).
    """
    source: Mapping[str, Any] = provenance if isinstance(provenance, Mapping) else {}
    gaps: list[str] = []

    windows = source.get("evaluationWindows")
    if isinstance(windows, (str, bytes)) or not isinstance(windows, Sequence):
        gaps.append("evaluationWindows")
    elif not windows or not all(isinstance(item, str) and item.strip() for item in windows):
        gaps.append("evaluationWindows")

    method = source.get("samplingMethod")
    if not isinstance(method, str) or not method.strip():
        gaps.append("samplingMethod")

    size = source.get("sampleSize")
    if isinstance(size, bool) or not isinstance(size, int) or size < MIN_DRAWS_FOR_BAND:
        gaps.append("sampleSize")

    unit = source.get("observationUnit")
    if not isinstance(unit, str) or not unit.strip():
        gaps.append("observationUnit")

    dependence = source.get("temporalDependence")
    if not isinstance(dependence, str) or not dependence.strip():
        gaps.append("temporalDependence")

    return tuple(gaps)


def band_validity(
    *,
    crosses_key: str,
    stats: Mapping[str, Any] | None,
    draws_with_cell: int,
    design: str = DESIGN_VENUE_DRAW,
    provenance: Mapping[str, Any] | None = None,
    venue_seeded: bool = False,
) -> dict[str, Any]:
    """Bloque ``validity`` con DOS etiquetas SEPARADAS (H1): sensibilidad vs confianza estadística.

    ``sensitivityBand`` — lo que los ``K`` sorteos del venue SÍ miden: ``crosses_key`` (¿la banda
    abarca el cero?) y ``pointCitable`` (= banda estable **y** ``|media| > 1.96·SE``), SIEMPRE
    acotado por ``pointCitableScope``. Es una lectura del **ruido del sorteo**, no de la estrategia.

    ``statisticalConfidence`` — lo que re-sorteos del MISMO dato **no** pueden afirmar: con
    ``design = venue_draw`` (por defecto) queda ``status = NOT_MEASURED``, ``established = False``
    y el motivo. Solo con ``design = independent_sample`` **y** procedencia verificable
    (``provenance`` con los ``PROVENANCE_REQUIRED_FIELDS``) se computa con el mismo criterio; una
    mera declaración NO basta (H1.1): sin evidencia (o si los datos revelan un ``venue_seeded``)
    vuelve a ``NOT_MEASURED`` con el motivo y ``missingProvenance`` declarados. Y sin muestra
    efectiva (``stats is None``) queda SIEMPRE ``NOT_MEASURED`` (``no_effective_sample``): declarar
    independencia no crea la medición que no existe.

    Un hueco es ``None`` (``sin_muestra`` / ``insufficient_draws``); jamás se rellena con ``0``.
    """
    measured = stats is not None
    crosses: bool | None = None
    se: float | None = None
    half_width: float | None = None
    note: str | None = None
    point_citable = False
    if stats is None:
        note = "sin_muestra"
    else:
        crosses = bool(stats["min"] < 0.0 < stats["max"])
        if draws_with_cell < MIN_DRAWS_FOR_BAND:
            note = "insufficient_draws"
        else:
            se = float(stats["stdev"]) / math.sqrt(draws_with_cell)
            half_width = CI95_Z * se
            point_citable = (not crosses) and abs(float(stats["mean"])) > half_width
    sensitivity = {
        "label": "sensitivityBand",
        "scope": "venue_draw_sensitivity",
        "measured": measured,
        "drawsWithCell": draws_with_cell,
        crosses_key: crosses,
        "pointCitable": bool(point_citable),
        "pointCitableScope": POINT_CITABLE_SCOPE,
        "se": se,
        "ci95HalfWidth": half_width,
        "note": note,
    }
    echoed_provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
    if design == DESIGN_INDEPENDENT:
        gaps = _provenance_gaps(provenance)
        if not measured:
            status = "NOT_MEASURED"
            reason: str | None = STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON
            missing = list(gaps)
        elif venue_seeded:
            status = "NOT_MEASURED"
            reason = STATISTICAL_CONFIDENCE_VENUE_DRAW_CONTRADICTION_REASON
            missing = list(gaps)
        elif not provenance:
            status = "NOT_MEASURED"
            reason = STATISTICAL_CONFIDENCE_PROVENANCE_MISSING_REASON
            missing = list(PROVENANCE_REQUIRED_FIELDS)
        elif gaps:
            status = "NOT_MEASURED"
            reason = STATISTICAL_CONFIDENCE_PROVENANCE_INCOMPLETE_REASON
            missing = list(gaps)
        else:
            status = "MEASURED"
            reason = None
            missing = []
        measured_statistical = status == "MEASURED"
        statistical: dict[str, Any] = {
            "label": "statisticalConfidence",
            "design": design,
            "status": status,
            "established": measured_statistical and bool(point_citable),
            "se": se if measured_statistical else None,
            "ci95HalfWidth": half_width if measured_statistical else None,
            "reason": reason,
            "requires": STATISTICAL_CONFIDENCE_REQUIRES,
            "provenance": echoed_provenance,
            "missingProvenance": missing,
        }
    else:
        statistical = {
            "label": "statisticalConfidence",
            "design": design,
            "status": "NOT_MEASURED",
            "established": False,
            "se": None,
            "ci95HalfWidth": None,
            "reason": STATISTICAL_CONFIDENCE_NOT_MEASURED_REASON,
            "requires": STATISTICAL_CONFIDENCE_REQUIRES,
            "provenance": echoed_provenance,
            "missingProvenance": [],
        }
    return {
        "design": design,
        "crossesKey": crosses_key,
        "sensitivityBand": sensitivity,
        "statisticalConfidence": statistical,
    }


def _validity(
    realized_stats: Mapping[str, Any] | None,
    draws_with_cell: int,
    *,
    design: str = DESIGN_VENUE_DRAW,
    provenance: Mapping[str, Any] | None = None,
    venue_seeded: bool = False,
) -> dict[str, Any]:
    """`validity` de la banda DÍA-D: delega en `band_validity` (H1/H1.1) con su clave de cruce."""
    return band_validity(
        crosses_key="crossesZeroR",
        stats=realized_stats,
        draws_with_cell=draws_with_cell,
        design=design,
        provenance=provenance,
        venue_seeded=venue_seeded,
    )


def _label(value: Any, fallback: str = "") -> str:
    """Etiqueta declarada de una dimensión: texto no vacío o el cubo ``fallback``."""
    text = str(value if value is not None else "").strip()
    return text or fallback


# ── Extracción de métricas de un artefacto ``dia-d-multi-v1`` ────────────────────


def _metric_row(row: Mapping[str, Any]) -> dict[str, float | None]:
    """Métricas de una fila de cubo (``byYear``/``byRegime``/``byYearByRegime``).

    La captura media y las reversiones viven en ``row.capture``; un valor ilegible es un hueco.
    """
    capture = row.get("capture") or {}
    ratio = capture.get("captureRatio") or {}
    return {
        "cycles": finite_number(row.get("cycles")),
        "expectancyR": finite_number(row.get("expectancyR")),
        "realizedRTotal": finite_number(row.get("realizedRTotal")),
        "hitRate": finite_number(row.get("hitRate")),
        "meanMaeR": finite_number(row.get("meanMaeR")),
        "meanMfeR": finite_number(row.get("meanMfeR")),
        "captureMean": finite_number(ratio.get("mean")),
        "reversedCount": finite_number(capture.get("reversedCount")),
    }


def _global_metrics(artifact: Mapping[str, Any]) -> dict[str, float | None]:
    """Métricas del cubo GLOBAL: del ``summary``, la severidad ALL y la captura global.

    El artefacto multirregimen NO publica un MFE medio global, así que ``meanMfeR`` es un hueco
    declarado (``None``), nunca un ``0``.
    """
    summary = artifact.get("summary") or {}
    populations = (artifact.get("maeSeverity") or {}).get("populations") or {}
    all_population = populations.get("ALL") or {}
    capture = artifact.get("capture") or {}
    ratio = capture.get("captureRatio") or {}
    return {
        "cycles": finite_number(summary.get("measuredCycles")),
        "expectancyR": finite_number(summary.get("expectancyR")),
        "realizedRTotal": finite_number(summary.get("realizedRTotal")),
        "hitRate": finite_number(summary.get("hitRate")),
        "meanMaeR": finite_number(all_population.get("meanMaeR")),
        "meanMfeR": None,
        "captureMean": finite_number(ratio.get("mean")),
        "reversedCount": finite_number(capture.get("reversedCount")),
    }


def _draw_cells(artifact: Mapping[str, Any]) -> dict[tuple[str, str, str], dict[str, float | None]]:
    """Cubos de UN sorteo: ``{(dim, year, regime): métricas}`` (claves canónicas)."""
    cells: dict[tuple[str, str, str], dict[str, float | None]] = {
        (DIM_GLOBAL, "", ""): _global_metrics(artifact),
    }
    for row in artifact.get("byYear") or ():
        cells[(DIM_YEAR, _label(row.get("year")), "")] = _metric_row(row)
    for row in artifact.get("byRegime") or ():
        cells[(DIM_REGIME, "", _label(row.get("regime")))] = _metric_row(row)
    for row in artifact.get("byOperationalRegime") or ():
        cells[(DIM_OPERATIONAL, "", _label(row.get("regime")))] = _metric_row(row)
    for row in artifact.get("byYearByRegime") or ():
        cells[(DIM_YEAR_REGIME, _label(row.get("year")), _label(row.get("regime")))] = _metric_row(row)
    return cells


# ── Plegado de los K sorteos ─────────────────────────────────────────────────────


def _fold(
    draws: Sequence[Mapping[str, Any]],
) -> tuple[dict[tuple[str, str, str], dict[str, list[float]]], dict[tuple[str, str, str], int]]:
    """Pliega los sorteos: valores por métrica y presencia de cada cubo (deterministas).

    Sólo se acumulan valores finitos: un hueco no vota (no se rellena con ``0``). La presencia
    de un cubo se cuenta por sorteo, para que ``drawsWithCell`` distinga "no medido" de "medido".
    """
    values: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    presence: dict[tuple[str, str, str], int] = {}
    for artifact in draws:
        for key, metrics in _draw_cells(artifact).items():
            presence[key] = presence.get(key, 0) + 1
            bucket = values.setdefault(key, {metric: [] for metric in METRICS})
            for metric in METRICS:
                value = metrics.get(metric)
                if value is not None:
                    bucket[metric].append(value)
    return values, presence


def _sort_key(key: tuple[str, str, str]) -> tuple[int, str, str]:
    """Orden determinista de los cubos: por dimensión, luego año, luego régimen."""
    dimension, year, regime = key
    return (_DIM_ORDER.index(dimension), year, regime)


def _render_cell(
    key: tuple[str, str, str],
    metric_values: Mapping[str, list[float]],
    *,
    draws_with_cell: int,
    draws_total: int,
    design: str = DESIGN_VENUE_DRAW,
    provenance: Mapping[str, Any] | None = None,
    venue_seeded: bool = False,
) -> dict[str, Any]:
    """Cubo con su banda por métrica y su ``validity`` (las etiquetas del cubo, según dimensión)."""
    dimension, year, regime = key
    bands = {metric: _stats(metric_values.get(metric, [])) for metric in METRICS}
    cell: dict[str, Any] = {
        "drawsWithCell": draws_with_cell,
        "drawsTotal": draws_total,
        "bands": bands,
        "validity": _validity(
            bands.get("realizedRTotal"),
            draws_with_cell,
            design=design,
            provenance=provenance,
            venue_seeded=venue_seeded,
        ),
    }
    if dimension == DIM_YEAR:
        cell["year"] = year
    elif dimension in (DIM_REGIME, DIM_OPERATIONAL):
        cell["regime"] = regime
    elif dimension == DIM_YEAR_REGIME:
        cell["year"] = year
        cell["regime"] = regime
    return cell


# ── Cobertura declarada (años × sorteos) ─────────────────────────────────────────


def _year_status(coverage: Mapping[str, Any], year: str) -> str:
    """Estado de un año en UN sorteo: ``measured`` / ``empty`` / ``not_measured`` / ``absent``."""
    measured = {str(item) for item in coverage.get("yearsMeasured") or []}
    empty = {str(item) for item in coverage.get("yearsEmpty") or []}
    not_measured = {
        str(row.get("year"))
        for row in coverage.get("yearsNotMeasured") or []
        if isinstance(row, Mapping)
    }
    if year in empty:
        return "empty"
    if year in measured:
        return "measured"
    if year in not_measured:
        return "not_measured"
    return "absent"


def _coverage(draws: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Cobertura de la banda: por año pedido, en cuántos sorteos se midió / vacío / no se midió.

    Un año que ningún sorteo mide queda con ``measured = 0`` (no se rellena); los motivos de
    ``yearsNotMeasured`` se agregan declarados. ``yearsRequested`` es la unión de los pedidos.
    """
    requested: list[str] = []
    seen: set[str] = set()
    for draw in draws:
        for year in (draw.get("coverage") or {}).get("yearsRequested") or []:
            label = str(year)
            if label not in seen:
                seen.add(label)
                requested.append(label)
    requested.sort()

    counters: dict[str, dict[str, Any]] = {
        year: {"measured": 0, "empty": 0, "notMeasured": 0, "reasons": set()} for year in requested
    }
    for draw in draws:
        coverage = draw.get("coverage") or {}
        reasons = {
            str(row.get("year")): str(row.get("reason") or "no_medido")
            for row in coverage.get("yearsNotMeasured") or []
            if isinstance(row, Mapping)
        }
        for year in requested:
            status = _year_status(coverage, year)
            row = counters[year]
            if status == "measured":
                row["measured"] += 1
            elif status == "empty":
                row["empty"] += 1
            elif status == "not_measured":
                row["notMeasured"] += 1
                row["reasons"].add(reasons.get(year, "no_medido"))
    per_year = [
        {
            "year": year,
            "measured": counters[year]["measured"],
            "empty": counters[year]["empty"],
            "notMeasured": counters[year]["notMeasured"],
            "reasons": sorted(counters[year]["reasons"]),
        }
        for year in requested
    ]
    return {"yearsRequested": requested, "drawsTotal": len(draws), "perYear": per_year}


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_band_artifact(
    *,
    draws: Sequence[Mapping[str, Any]],
    seed_shift: Mapping[str, Any] | None = None,
    cross_check: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
    design: str = DESIGN_VENUE_DRAW,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Payload canónico de la banda multirregimen (puro y determinista: sin reloj ni azar).

    ``draws`` son los ``K`` artefactos ``dia-d-multi-v1`` (uno por sorteo del venue). Pliega cada
    cubo con ``bands`` (min/median/max/mean/stdev) y ``validity`` (bloque H1 con ``sensitivityBand``
    y ``statisticalConfidence`` separados). Un cubo sin muestra no aparece en su dimensión; un hueco
    queda ``None``, nunca ``0``. ``design`` declara la procedencia de los ``K`` sorteos; ``provenance``
    es la evidencia requerida para computar la confianza estadística (H1.1) y un ``seed_shift`` no
    vacío revela un re-sorteo del venue (contradice una declaración de independencia).
    """
    ordered = list(draws or ())
    draws_total = len(ordered)
    venue_seeded = bool(seed_shift)
    values, presence = _fold(ordered)
    cells = {
        key: _render_cell(
            key,
            values[key],
            draws_with_cell=presence.get(key, 0),
            draws_total=draws_total,
            design=design,
            provenance=provenance,
            venue_seeded=venue_seeded,
        )
        for key in sorted(values, key=_sort_key)
    }

    def _dimension(dimension: str) -> list[dict[str, Any]]:
        return [cells[key] for key in sorted(cells, key=_sort_key) if key[0] == dimension]

    global_cell = cells.get((DIM_GLOBAL, "", ""), {
        "drawsWithCell": 0,
        "drawsTotal": draws_total,
        "bands": {metric: None for metric in METRICS},
        "validity": _validity(
            None, 0, design=design, provenance=provenance, venue_seeded=venue_seeded
        ),
    })

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "basis": "entryDay",
        "design": design,
        "draws": draws_total,
        "seedShift": {str(key): value for key, value in (seed_shift or {}).items()},
        "coverage": _coverage(ordered),
        "global": global_cell,
        "byYear": _dimension(DIM_YEAR),
        "byRegime": _dimension(DIM_REGIME),
        "byOperationalRegime": _dimension(DIM_OPERATIONAL),
        "byYearByRegime": _dimension(DIM_YEAR_REGIME),
        "crossCheck": dict(cross_check) if cross_check is not None else {
            "source": None,
            "available": False,
            "note": "no se cruzó contra un artefacto sellado",
        },
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "CI95_Z",
    "DEFAULT_LIMITS",
    "DESIGN_INDEPENDENT",
    "DESIGN_VENUE_DRAW",
    "DIM_GLOBAL",
    "DIM_OPERATIONAL",
    "DIM_REGIME",
    "DIM_YEAR",
    "DIM_YEAR_REGIME",
    "KIND",
    "METRICS",
    "MIN_DRAWS_FOR_BAND",
    "POINT_CITABLE_SCOPE",
    "PROVENANCE_REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "STATISTICAL_CONFIDENCE_NOT_MEASURED_REASON",
    "STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON",
    "STATISTICAL_CONFIDENCE_PROVENANCE_INCOMPLETE_REASON",
    "STATISTICAL_CONFIDENCE_PROVENANCE_MISSING_REASON",
    "STATISTICAL_CONFIDENCE_REQUIRES",
    "STATISTICAL_CONFIDENCE_VENUE_DRAW_CONTRADICTION_REASON",
    "band_validity",
    "build_band_artifact",
]
