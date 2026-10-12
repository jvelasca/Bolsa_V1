"""`§8-c` — BANDA `K` MEDIDA del reporte financiero OOS (puro y determinista).

Qué es
------
El reporte financiero OOS (`oos_finance`, sello `§8-a`) fija `pointCitable = False` a
propósito, porque **no** cita la banda `K`: declara que el replay AUTO es un **sorteo del
venue** y que la banda de `K=12` sorteos cruza el cero (`W3.3`, `v2.88.16.3`). Este módulo
da el siguiente paso: pliega `K` reportes financieros (uno por sorteo del venue) en una
**banda** por grupo `(strategyVersion, symbol)` y por el agregado, y **evalúa** la
citabilidad en vez de narrarla.

Por cada cubo publica:

* ``bands`` — ``min``/``median``/``max``/``mean``/``stdev``/``n`` de cada métrica de dinero
  (``netReturnPct``, ``grossReturnPct``, ``netReturnPctAtStress``, ``maxDrawdownPct``,
  ``hitRate``, ``profitFactor``, ``sharpe``, ``trades``, ``committedCapital``); ``None``
  sin muestra, **nunca** ``0``.
* ``validity`` — ``crossesZeroNetReturn`` y ``pointCitable`` evaluados con el MISMO
  criterio que el resto del repositorio (``pointCitable`` sólo si la banda de retorno neto
  **no** cruza cero **y** ``|media| > 1.96·SE``), más ``se``/``ci95HalfWidth``. Con menos de
  ``MIN_DRAWS_FOR_BAND`` sorteos **no** hay banda que cite un punto: se declara
  (``insufficient_draws``).

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* Un cubo ausente en un sorteo baja ``drawsWithCell`` (no se inventa un valor).
* La capa es **advisory y read-only**: no cambia el motor, los umbrales, ``TOP_N`` ni la
  allocation; es un **observador** del mismo instrumento.
* La banda se cita **entera o no se cita**; el artefacto es **determinista** (sin reloj ni
  azar: las ``K`` semillas son una entrada declarada).
* Mide el **ruido del sorteo del venue** (mismo dato, misma estrategia), **no** la
  incertidumbre de muestreo del ciclo ni el futuro.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.dia_d_auto import finite_number

#: Fuente ÚNICA de verdad del criterio de banda: el sello ya existente no se re-declara.
#: Importarlos aquí garantiza que la banda financiera y la banda DÍA-D usan el mismo umbral.
from bolsa_application.dia_d_multi_uncertainty import CI95_Z, MIN_DRAWS_FOR_BAND

#: Versión del esquema del artefacto de banda. Un cambio de forma la sube.
SCHEMA_VERSION = "oos-finance-band-v1"

#: Tipo del artefacto.
KIND = "OOS_FINANCE_BAND"

#: Clave reservada del grupo agregado (la MISMA que usa `oos_finance`).
AGGREGATE_KEY: tuple[str | None, str] = ("__ALL__", "__ALL__")

#: Métricas de dinero que se pliegan por cubo (todas publicadas como banda, o ``None`` sin
#: muestra). Se ordena para que el payload sea determinista.
METRICS: tuple[str, ...] = (
    "trades",
    "committedCapital",
    "grossReturnPct",
    "netReturnPct",
    "netReturnPctAtStress",
    "maxDrawdownPct",
    "hitRate",
    "profitFactor",
    "sharpe",
)

#: Métrica cuyo cruce por cero decide la citabilidad (el análogo financiero del R total).
VALIDITY_METRIC = "netReturnPct"

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "La banda mide el RUIDO DEL SORTEO DEL VENUE (K re-sorteos del MISMO dato y estrategia), "
    "no la incertidumbre de muestreo del ciclo ni el futuro.",
    "Un punto solo es citable si la banda de retorno neto NO cruza cero Y |media| > 1.96*SE, "
    "con K >= 2; con menos sorteos se declara insufficient_draws y pointCitable=False.",
    "La banda se cita ENTERA o no se cita: el determinismo (reproducibilidad byte a byte) NO es "
    "validez.",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. Un cubo ausente en un sorteo baja "
    "drawsWithCell, no se inventa.",
    "Compone reportes financieros ya calculados (oos_finance): NO recalcula el motor ni proclama "
    "una estrategia ganadora.",
    "Costes MODELADOS (overlay de comision/deslizamiento): la friccion medida del SIM se "
    "reportaria aparte, sin doble contabilizacion.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas). "
    "CONFIRMED sigue reservado a evidencia PAPER.",
    "La banda medida NO es reproducible sin PostgreSQL (el replay lee barras reales): se cita como "
    "medicion, no como gate de CI.",
    "Determinismo: mismas K semillas => payload identico (sin reloj, ULID ni azar global).",
)


# ── Utilidades numéricas (None cuando no hay muestra; nunca 0) ───────────────────


def _mean(values: Sequence[float]) -> float | None:
    """Media de una muestra o ``None`` si está vacía."""
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
    """Resumen declarado de una métrica: ``n``/``min``/``median``/``max``/``mean``/``stdev``.

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


def _validity(net_return_stats: Mapping[str, Any] | None, draws_with_cell: int) -> dict[str, Any]:
    """Criterio de citabilidad evaluado (no narrado).

    ``crossesZeroNetReturn`` = la banda de retorno neto abarca el cero. ``pointCitable`` = la
    banda **no** cruza el cero **y** ``|media| > 1.96·SE`` (SE = ``stdev / sqrt(n)``), con al
    menos ``MIN_DRAWS_FOR_BAND`` sorteos. Sin banda ⇒ ``crossesZeroNetReturn = None`` y
    ``pointCitable = False``.
    """
    if net_return_stats is None:
        return {
            "crossesZeroNetReturn": None,
            "pointCitable": False,
            "se": None,
            "ci95HalfWidth": None,
            "note": "sin_muestra",
        }
    crosses = bool(net_return_stats["min"] < 0.0 < net_return_stats["max"])
    if draws_with_cell < MIN_DRAWS_FOR_BAND:
        return {
            "crossesZeroNetReturn": crosses,
            "pointCitable": False,
            "se": None,
            "ci95HalfWidth": None,
            "note": "insufficient_draws",
        }
    se = float(net_return_stats["stdev"]) / math.sqrt(draws_with_cell)
    point_citable = (not crosses) and abs(float(net_return_stats["mean"])) > CI95_Z * se
    return {
        "crossesZeroNetReturn": crosses,
        "pointCitable": bool(point_citable),
        "se": se,
        "ci95HalfWidth": CI95_Z * se,
        "note": None,
    }


# ── Extracción de métricas de UN reporte `oos_finance` ───────────────────────────


def _metrics(mapping: Mapping[str, Any]) -> dict[str, float | None]:
    """Métricas de dinero de una fila de grupo (o del agregado); un valor ilegible es hueco."""
    return {metric: finite_number(mapping.get(metric)) for metric in METRICS}


def _group_key(group: Mapping[str, Any]) -> tuple[str | None, str]:
    """Clave canónica de un grupo: ``(strategyVersion, symbol)`` (versión ausente ⇒ ``None``)."""
    version = group.get("strategyVersion")
    return (None if version is None else str(version), str(group.get("symbol") or ""))


def _preset_key(group: Mapping[str, Any]) -> str | None:
    """Identidad EXACTA (H1) del grupo si la declara; ``None`` = hueco declarado (nunca ``""``)."""
    preset = group.get("strategyPresetKey")
    if preset is None:
        return None
    text = str(preset).strip()
    return text or None


def _draw_cells(report: Mapping[str, Any]) -> dict[tuple[str | None, str], dict[str, float | None]]:
    """Cubos de UN reporte: ``{(version, symbol): métricas}`` + el agregado bajo ``AGGREGATE_KEY``."""
    cells: dict[tuple[str | None, str], dict[str, float | None]] = {}
    aggregate = report.get("aggregate")
    if isinstance(aggregate, Mapping):
        cells[AGGREGATE_KEY] = _metrics(aggregate)
    for group in report.get("groups") or ():
        if not isinstance(group, Mapping):
            continue
        cells[_group_key(group)] = _metrics(group)
    return cells


# ── Plegado de los K sorteos ─────────────────────────────────────────────────────


def _fold(
    draws: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[str | None, str], dict[str, list[float]]],
    dict[tuple[str | None, str], int],
    dict[tuple[str | None, str], str | None],
]:
    """Pliega los sorteos: valores por métrica, presencia de cada cubo y su identidad exacta.

    Sólo se acumulan valores finitos: un hueco no vota (no se rellena con ``0``). La presencia
    de un cubo se cuenta por sorteo, para que ``drawsWithCell`` distinga "no medido" de "medido".
    """
    values: dict[tuple[str | None, str], dict[str, list[float]]] = {}
    presence: dict[tuple[str | None, str], int] = {}
    presets: dict[tuple[str | None, str], str | None] = {}
    for report in draws:
        if not isinstance(report, Mapping):
            continue
        cells = _draw_cells(report)
        for key, metrics in cells.items():
            presence[key] = presence.get(key, 0) + 1
            bucket = values.setdefault(key, {metric: [] for metric in METRICS})
            for metric in METRICS:
                value = metrics.get(metric)
                if value is not None:
                    bucket[metric].append(value)
    for report in draws:
        if not isinstance(report, Mapping):
            continue
        for group in report.get("groups") or ():
            if not isinstance(group, Mapping):
                continue
            key = _group_key(group)
            if presets.get(key) is None:
                presets[key] = _preset_key(group)
    return values, presence, presets


def _sort_key(key: tuple[str | None, str]) -> tuple[int, str, str]:
    """Orden determinista de los cubos: el agregado primero, luego ``(versión, símbolo)``."""
    return (0 if key == AGGREGATE_KEY else 1, key[0] or "", key[1])


def _render_cell(
    key: tuple[str | None, str],
    metric_values: Mapping[str, list[float]],
    *,
    draws_with_cell: int,
    draws_total: int,
    preset_key: str | None,
) -> dict[str, Any]:
    """Cubo con su banda por métrica y su ``validity`` medida."""
    bands = {metric: _stats(metric_values.get(metric, [])) for metric in METRICS}
    return {
        "strategyVersion": key[0],
        "strategyPresetKey": preset_key,
        "symbol": key[1],
        "drawsWithCell": draws_with_cell,
        "drawsTotal": draws_total,
        "bands": bands,
        "validity": _validity(bands.get(VALIDITY_METRIC), draws_with_cell),
    }


def _coverage(
    cells: Mapping[tuple[str | None, str], dict[str, Any]],
    *,
    draws_total: int,
) -> dict[str, Any]:
    """Cobertura declarada: por cubo, en cuántos sorteos se midió (``drawsWithCell``)."""
    return {
        "drawsTotal": draws_total,
        "groups": [
            {
                "strategyVersion": key[0],
                "symbol": key[1],
                "drawsWithCell": cells[key]["drawsWithCell"],
            }
            for key in sorted(cells, key=_sort_key)
            if key != AGGREGATE_KEY
        ],
    }


def _declared_scalar(draws: Sequence[Mapping[str, Any]], name: str) -> Any:
    """Valor declarado (``minTrades``/``stressMultiplier``) del primer sorteo que lo traiga."""
    for report in draws:
        if isinstance(report, Mapping) and report.get(name) is not None:
            return report.get(name)
    return None


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_finance_band(
    *,
    draws: Sequence[Mapping[str, Any]],
    seed_shift: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico de la banda financiera OOS (puro y determinista: sin reloj ni azar).

    ``draws`` son los ``K`` reportes ``oos_finance`` (``OosFinanceReport.to_dict()``), uno por
    sorteo del venue. Pliega cada cubo con ``bands`` (min/median/max/mean/stdev/n) y ``validity``
    (``crossesZeroNetReturn``/``pointCitable``). Un cubo sin muestra no aparece; un hueco queda
    ``None``, nunca ``0``.
    """
    ordered = [report for report in (draws or ()) if isinstance(report, Mapping)]
    draws_total = len(ordered)
    values, presence, presets = _fold(ordered)
    cells = {
        key: _render_cell(
            key,
            values.get(key, {metric: [] for metric in METRICS}),
            draws_with_cell=presence.get(key, 0),
            draws_total=draws_total,
            preset_key=presets.get(key),
        )
        for key in values
    }
    aggregate_cell = cells.get(AGGREGATE_KEY, {
        "strategyVersion": AGGREGATE_KEY[0],
        "strategyPresetKey": None,
        "symbol": AGGREGATE_KEY[1],
        "drawsWithCell": 0,
        "drawsTotal": draws_total,
        "bands": {metric: None for metric in METRICS},
        "validity": _validity(None, 0),
    })
    group_cells = [
        cells[key] for key in sorted(cells, key=_sort_key) if key != AGGREGATE_KEY
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "draws": draws_total,
        "minTrades": _declared_scalar(ordered, "minTrades"),
        "stressMultiplier": _declared_scalar(ordered, "stressMultiplier"),
        "seedShift": {str(key): value for key, value in (seed_shift or {}).items()},
        "coverage": _coverage(cells, draws_total=draws_total),
        "aggregate": aggregate_cell,
        "groups": group_cells,
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "AGGREGATE_KEY",
    "CI95_Z",
    "DEFAULT_LIMITS",
    "KIND",
    "METRICS",
    "MIN_DRAWS_FOR_BAND",
    "SCHEMA_VERSION",
    "VALIDITY_METRIC",
    "build_finance_band",
]
