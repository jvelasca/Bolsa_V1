"""V2.88.44 · DÍA-D AUTO — DIAGNÓSTICO DE DÓNDE NACE LA PÉRDIDA (puro, sin I/O).

Qué es
------
La atribución multirregimen (``dia_d_multi``) y su banda venue/sampling (``dia_d_multi_sampling``)
dicen *cuánto* y *dónde* (año/régimen) se pierde, y *cuánto de eso es ruido del instrumento*.
Este módulo responde **por qué se cierra cada ciclo y cuánto pesa cada causa**: descompone el R
observado por

* **mecanismo de salida** (``STOP_EJECUTADO``/``TARGET_1``/``TARGET_2``/``TRAILING``/``TIME_EXIT``/
  ``THESIS_EXIT``/``REGIME_EXIT``/``RISK_EXIT``/``KILL_SWITCH``/``PORTFOLIO_RISK``/``MANUAL``/
  ``EXIT_REQUESTED``/``SIN_MECANISMO``) — qué clase de decisión cierra el ciclo y cuánta R aporta;
* **coste aplicado** (fricción/slippage del simulador, ``applied_cost``) — cuánto R BRUTO se come
  la fricción y cuánto queda NETO, separando el suelo medido de la cifra completa;
* **calidad de entrada** — cómo de adversa fue la excursión TEMPRANA post-entrada (primeras
  ``N`` barras D1) y cuánto se desvió la ejecución de entrada de su mid de referencia (bps).

Consume el **ledger de ciclos por sorteo** (``dia-d-multi-cycle-ledger-v2``) y pliega los ``K``
sorteos del venue, de modo que cada causa viaja con su **dispersión entre sorteos** y su
**fragilidad** declarada.

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* El R neto sólo se afirma con fricción ``COMPLETE``: con ``PARTIAL`` el neto es un **suelo** y se
  declara (jamás se publica el bruto disfrazado de neto).
* Un mecanismo sin muestra no aparece; ``SIN_MECANISMO`` es el hueco declarado, no una categoría
  que se pueda inventar.
* **Advisory y read-only:** no cambia el motor, los umbrales, ``TOP_N`` ni la allocation.
* Determinista (sin reloj ni azar global): mismas entradas ⇒ payload byte a byte idéntico.
* Evidencia de **REPLAY/OOS**: no sustituye la ventana PAPER (``P3-2``/``P3-3`` siguen abiertas).

Qué NO es: causal. Es una descomposición **descriptiva** de la muestra medida; la fricción se mide
contra el mid de referencia del simulador, no contra el precio de mercado.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.dia_d_auto import finite_number
from bolsa_application.dia_d_multi_sampling import (
    MIN_CYCLES_FOR_SAMPLING,
    build_cycle_ledger,
)
from bolsa_application.dia_d_multi_uncertainty import MIN_DRAWS_FOR_BAND

#: Versión del esquema del artefacto de diagnóstico de la pérdida. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-loss-origin-v1"

#: Tipo del artefacto.
KIND = "DIA_D_AUTO_LOSS_ORIGIN"

#: Umbrales declarados de la calidad de entrada (no son decisiones estadísticas: son el suelo
#: con el que se lee "la entrada fue prontamente adversa").
ENTRY_ADVERSE_HALF_R = -0.5
ENTRY_ADVERSE_ONE_R = -1.0

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Diagnostico DESCRIPTIVO, no causal: descompone la muestra medida, no explica el mercado.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. La media de una muestra vacia es None.",
    "El R NETO solo se afirma con friccion COMPLETE; con PARTIAL es un SUELO y se declara "
    "(netRealizedRGap), jamas se publica el bruto disfrazado de neto.",
    "La friccion se mide contra el mid de referencia del SIMULADOR (applied_cost), no contra el "
    "precio de mercado: es el coste que ESTE venue aplico, no el de un broker real.",
    "El mecanismo de salida es el motivo DECISORIO del plan (day_exit_reason); un motivo de cierre "
    "sin medir es SIN_MECANISMO (hueco declarado), nunca una etiqueta inventada.",
    "La excursion adversa temprana es ENTRE DIAS (barras D1) sobre las primeras N barras tras la "
    "entrada; el dia de entrada puede incluir excursion previa al fill.",
    "La banda por mecanismo es la DISPERSION entre los K sorteos del venue (mismo dato, misma "
    "estrategia); NO es el bootstrap de ciclos ni la incertidumbre de mercado.",
    "Un cubo puede aparecer en pocos sorteos o con pocos ciclos: fragility declara el n efectivo "
    "y por que la lectura puede ser enganosamente estrecha (no se oculta).",
    "REPLAY/OOS != PAPER: CONFIRMED sigue reservado a evidencia PAPER y NO se emite aqui.",
)


# ── Utilidades numéricas (None cuando no hay muestra; nunca 0) ───────────────────


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _pop_variance(values: Sequence[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _dispersion(values: Sequence[float]) -> dict[str, Any] | None:
    """Dispersión entre sorteos de una métrica (``None`` sin muestra; nunca un ``0`` hueco)."""
    if not values:
        return None
    return {
        "n": len(values),
        "mean": _mean(values),
        "min": min(values),
        "max": max(values),
        "var": _pop_variance(values),
    }


def _share(values: Sequence[float], predicate: Any) -> float | None:
    """Fracción de una muestra que cumple ``predicate`` (``None`` sin muestra; nunca ``0``)."""
    if not values:
        return None
    return sum(1 for value in values if predicate(value)) / len(values)


# ── Plegado por mecanismo de salida ──────────────────────────────────────────────


def _cycles(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in (ledger.get("cycles") or ()) if isinstance(row, Mapping)]


def _mechanism_of(row: Mapping[str, Any]) -> str:
    text = str(row.get("exitMechanism") or "").strip()
    return text or "SIN_MECANISMO"


def _fold_mechanisms(draw_ledgers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Una fila por mecanismo con la dispersión venue de su R bruto/neto y su fragilidad."""
    draws_total = len(draw_ledgers)
    labels: set[str] = set()
    per_draw: list[dict[str, list[Mapping[str, Any]]]] = []
    for ledger in draw_ledgers:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for row in _cycles(ledger):
            grouped.setdefault(_mechanism_of(row), []).append(row)
        per_draw.append(grouped)
        labels.update(grouped)

    rows: list[dict[str, Any]] = []
    for label in sorted(labels):
        gross_totals: list[float] = []
        gross_exp: list[float] = []
        hits: list[float] = []
        net_totals: list[float] = []
        net_exp: list[float] = []
        friction_r_means: list[float] = []
        cycles_total = 0
        cycles_per_draw: list[int] = []
        net_measured = 0
        net_unmeasured = 0
        friction_by_measurement = {"COMPLETE": 0, "PARTIAL": 0, "UNKNOWN": 0}
        for grouped in per_draw:
            present = grouped.get(label) or []
            if not present:
                continue
            gross = [value for row in present if (value := finite_number(row.get("realizedR"))) is not None]
            net = [value for row in present if (value := finite_number(row.get("netRealizedR"))) is not None]
            fr = [value for row in present if (value := finite_number(row.get("frictionR"))) is not None]
            net_measured += len(net)
            net_unmeasured += len(gross) - len(net)
            for row in present:
                key = str(row.get("frictionMeasurement") or "UNKNOWN")
                if key in friction_by_measurement:
                    friction_by_measurement[key] += 1
            if not gross:
                continue
            cycles_total += len(gross)
            cycles_per_draw.append(len(gross))
            gross_totals.append(sum(gross))
            gross_exp.append(sum(gross) / len(gross))
            hits.append(sum(1 for value in gross if value > 0.0) / len(gross))
            if net:
                net_totals.append(sum(net))
                net_exp.append(sum(net) / len(net))
            if fr:
                friction_r_means.append(sum(fr) / len(fr))
        reasons: list[str] = []
        draws_with_cell = len(gross_totals)
        if draws_with_cell < MIN_DRAWS_FOR_BAND:
            reasons.append("insufficient_draws")
        if cycles_per_draw and min(cycles_per_draw) < MIN_CYCLES_FOR_SAMPLING:
            reasons.append("few_cycles_per_draw")
        if net_unmeasured:
            reasons.append("net_partial")
        rows.append(
            {
                "mechanism": label,
                "drawsWithCell": draws_with_cell,
                "drawsTotal": draws_total,
                "cycles": cycles_total,
                "realizedRGross": {
                    "total": _dispersion(gross_totals),
                    "expectancyR": _dispersion(gross_exp),
                    "hitRate": _dispersion(hits),
                },
                "realizedRNet": {
                    "total": _dispersion(net_totals),
                    "expectancyR": _dispersion(net_exp),
                    "cyclesMeasured": net_measured,
                    "cyclesUnmeasured": net_unmeasured,
                },
                "frictionR": {"mean": _dispersion(friction_r_means)},
                "frictionMeasurement": friction_by_measurement,
                "fragility": {"fragile": bool(reasons), "reasons": reasons},
            }
        )
    return rows


# ── Coste aplicado (global) ──────────────────────────────────────────────────────


def _fold_costs(draw_ledgers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Impacto de la fricción aplicada: R bruto vs neto, suelo medido y conteo de medición."""
    gross_totals: list[float] = []
    net_totals: list[float] = []
    friction_totals: list[float] = []
    friction_r_totals: list[float] = []
    friction_r_means: list[float] = []
    measurement = {"COMPLETE": 0, "PARTIAL": 0, "UNKNOWN": 0}
    cycles = 0
    net_unmeasured = 0
    for ledger in draw_ledgers:
        rows = _cycles(ledger)
        gross = [value for row in rows if (value := finite_number(row.get("realizedR"))) is not None]
        net = [value for row in rows if (value := finite_number(row.get("netRealizedR"))) is not None]
        friction = [value for row in rows if (value := finite_number(row.get("frictionCost"))) is not None]
        fr = [value for row in rows if (value := finite_number(row.get("frictionR"))) is not None]
        for row in rows:
            key = str(row.get("frictionMeasurement") or "UNKNOWN")
            if key in measurement:
                measurement[key] += 1
        cycles += len(gross)
        net_unmeasured += len(gross) - len(net)
        if gross:
            gross_totals.append(sum(gross))
        if net:
            net_totals.append(sum(net))
        if friction:
            friction_totals.append(sum(friction))
        if fr:
            friction_r_totals.append(sum(fr))
            friction_r_means.append(sum(fr) / len(fr))
    return {
        "cycles": cycles,
        "realizedRGrossTotal": _dispersion(gross_totals),
        "realizedRNetTotal": _dispersion(net_totals),
        "frictionCostTotal": _dispersion(friction_totals),
        "frictionRTotal": _dispersion(friction_r_totals),
        "frictionRMean": _dispersion(friction_r_means),
        "frictionMeasurement": measurement,
        "netUnmeasuredCycles": net_unmeasured,
        "netIsLowerBound": bool(net_unmeasured),
    }


# ── Calidad de entrada (excursión temprana + desvío de ejecución) ────────────────


def _fold_entry_quality(draw_ledgers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Excursión adversa TEMPRANA y desvío de ejecución de entrada (bps), por sorteo."""
    adverse: list[float] = []
    adverse_means: list[float] = []
    slippage: list[float] = []
    slippage_means: list[float] = []
    window_days: int | None = None
    unmeasured = 0
    for ledger in draw_ledgers:
        draw_adverse: list[float] = []
        draw_slip: list[float] = []
        for row in _cycles(ledger):
            days = finite_number(row.get("entryAdverseWindowDays"))
            if window_days is None and days is not None:
                window_days = int(days)
            value = finite_number(row.get("entryAdverseR"))
            if value is None:
                unmeasured += 1
            else:
                adverse.append(value)
                draw_adverse.append(value)
            slip = finite_number(row.get("entrySlippageBps"))
            if slip is not None:
                slippage.append(slip)
                draw_slip.append(slip)
        if draw_adverse:
            adverse_means.append(sum(draw_adverse) / len(draw_adverse))
        if draw_slip:
            slippage_means.append(sum(draw_slip) / len(draw_slip))
    return {
        "windowDays": window_days,
        "adverseExcursion": {
            "measured": len(adverse),
            "unmeasured": unmeasured,
            "meanR": _mean(adverse),
            "medianR": _median(adverse),
            "shareBelowHalfR": _share(adverse, lambda value: value < ENTRY_ADVERSE_HALF_R),
            "shareBelowOneR": _share(adverse, lambda value: value < ENTRY_ADVERSE_ONE_R),
            "meanAcrossDraws": _dispersion(adverse_means),
        },
        "entrySlippageBps": {
            "measured": len(slippage),
            "mean": _mean(slippage),
            "median": _median(slippage),
            "shareAboveZero": _share(slippage, lambda value: value > 0.0),
            "meanAcrossDraws": _dispersion(slippage_means),
        },
    }


def _coverage_from_ledgers(draw_ledgers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Cobertura mínima: años presentes y si cada ciclo trae detalle de fricción medido."""
    years: list[str] = []
    seen: set[str] = set()
    cycles = 0
    with_detail = 0
    for ledger in draw_ledgers:
        for row in _cycles(ledger):
            cycles += 1
            year = str(row.get("year") or "").strip()
            if year and year not in seen:
                seen.add(year)
                years.append(year)
            if str(row.get("frictionMeasurement") or "UNKNOWN") == "COMPLETE":
                with_detail += 1
    years.sort()
    return {
        "yearsRequested": years,
        "drawsTotal": len(draw_ledgers),
        "cyclesTotal": cycles,
        "cyclesWithCompleteFriction": with_detail,
        "detailCaptured": with_detail > 0,
    }


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_loss_origin_artifact(
    *,
    draw_ledgers: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico del diagnóstico de la pérdida (puro y determinista).

    ``draw_ledgers`` son los ``K`` ledgers de ciclos (``dia-d-multi-cycle-ledger-v2``). Pliega el
    resultado por **mecanismo de salida**, el **impacto de la fricción** (bruto vs neto) y la
    **calidad de entrada** (excursión adversa temprana + desvío de ejecución), cada causa con su
    **dispersión entre sorteos** y su **fragilidad** declarada. Un hueco queda ``None``, nunca ``0``.
    """
    ordered = list(draw_ledgers or ())
    mechanisms = _fold_mechanisms(ordered)
    resolved_coverage = dict(coverage) if coverage is not None else _coverage_from_ledgers(ordered)
    if not resolved_coverage.get("detailCaptured") and ordered:
        resolved_coverage["detailCaptured"] = False
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "basis": "entryDay",
        "draws": len(ordered),
        "axes": ["exit_mechanism", "costs", "entry"],
        "coverage": resolved_coverage,
        "byExitMechanism": mechanisms,
        "costImpact": _fold_costs(ordered),
        "entryQuality": _fold_entry_quality(ordered),
        "recompileNote": (
            "Un ledger sin detalle de friccion (sin --cycle-detail) produce costes UNKNOWN: "
            "el diagnostico de coste queda declarado, no en blanco."
        ),
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "DEFAULT_LIMITS",
    "ENTRY_ADVERSE_HALF_R",
    "ENTRY_ADVERSE_ONE_R",
    "KIND",
    "SCHEMA_VERSION",
    "build_cycle_ledger",
    "build_loss_origin_artifact",
]
