"""DÍA-D AUTO — bucle de realimentación POR VALOR (advisory, read-only).

Qué es
------
El sandbox DÍA-D AUTO (``dia_d_auto.py`` + ``v2_89``) produce la foto de **un** día: qué
declaró el motor, qué ejecutó la ventana PAPER y qué hizo el mercado después. Este módulo
pliega **muchos** días en un veredicto **por instrumento**: ¿la tesis del motor se cumple
OOS?, ¿coincide lo declarado con lo ejecutado?, ¿aparecen errores de software/operativa/dato?

Es un artefacto derivado: **no** toca el motor, **no** cambia umbrales ni ``TOP_N``, **no**
escribe en la BD durable. Es una LECTURA que un humano interpreta (``advisory``).

Regla dura heredada: un hueco es ``None`` / ``NOT_MEASURED``, **nunca** ``0``. La media, el
total y el hit-rate de una muestra vacía se declaran ausentes, no se rellenan.

Vocabulario (se reutiliza, no se inventa)
-----------------------------------------
* Comparador por paso: ``MATCH`` / ``DIVERGENT`` / ``NOT_MEASURED`` de ``dia_d_auto``.
* Familia de vetos y códigos de motivo: ``market_operability`` / ``auto_reason_codes``.
* Gate de ventana: ``window_gate`` de ``operability_window`` (se INCORPORA como declaración;
  el veredicto por valor es un complemento, no lo sustituye).

Taxonomía de errores ``ERROR_KINDS = ("SOFTWARE", "OPERATIONAL", "DATA")``:
* ``SOFTWARE``: ``DIVERGENT`` en un paso DETERMINISTA (``SIGNAL``/``ORDER``/``FILL``) o un
  estado de reconciliación de integridad ``drift``/``blocked``. Es evidencia POSITIVA de un
  fallo lógico: gana sobre el suelo de muestra (no se esconde tras ``NOT_MEASURED``).
* ``OPERATIONAL``: ``protection_missing``, ``reservation_unmeasurable``, ``RELEASED_BY_*``,
  ``auto_exit_orders`` en ``ABANDONED``/``EMERGENCY``, ``execution_events`` en
  ``FAILED``/``RETRY``.
* ``DATA``: códigos del cubo ``data`` de ``market_operability`` (``stale_data``,
  ``atr_unknown``, ``sector_unknown``, ``no_mark_data``, ...) y la violación de contrato
  ``other > 0``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.auto_reason_codes import (
    NO_MARK_DATA,
    PROTECTION_MISSING,
    RESERVATION_RELEASED_CANCEL,
    RESERVATION_RELEASED_FILL,
    RESERVATION_RELEASED_RESTART,
    RESERVATION_RELEASED_ROLLBACK,
    RESERVATION_UNMEASURABLE,
)
from bolsa_application.dia_d_auto import (
    VERDICT_DIVERGENT,
    finite_number,
    normalize_day,
)
from bolsa_application.market_operability import (
    BUCKET_DATA,
    VETO_BUCKET_BY_REASON,
)

#: Versión del esquema del artefacto de feedback. Un cambio de forma la sube.
#: ``v2`` añade el índice ``cycles[]`` (``cycleId`` → identidad del ciclo) manteniendo el
#: veredicto AGREGADO por instrumento: sólo desambigua a qué valor pertenece cada ciclo.
SCHEMA_VERSION = "dia-d-feedback-v2"

#: Veredicto POR VALOR sobre evidencia de REPLAY/OOS: soporta / mezcla / refuta / no medido.
#: ``OOS_SUPPORTED`` NO significa "valor confirmado operativamente": afirma que el
#: comportamiento OOS del REPLAY del motor fue positivo bajo este experimento (D34-03). No
#: dice nada sobre la ejecución PAPER real. ``CONFIRMED`` se RESERVA para evidencia PAPER
#: (ejecución real + muestra suficiente + datos íntegros); hoy NO se emite.
VALUE_OOS_SUPPORTED = "OOS_SUPPORTED"
VALUE_MIXED = "MIXED"
VALUE_REFUTED = "REFUTED"
VALUE_NOT_MEASURED = "NOT_MEASURED"
VALUE_VERDICTS: tuple[str, ...] = (
    VALUE_OOS_SUPPORTED,
    VALUE_MIXED,
    VALUE_REFUTED,
    VALUE_NOT_MEASURED,
)

#: Reservado: veredicto para evidencia PAPER real. NO entra en ``VALUE_VERDICTS`` ni se emite
#: mientras el instrumento sólo observe el replay.
VALUE_CONFIRMED = "CONFIRMED"

#: Calidad de la EVIDENCIA por tamaño de muestra (eje INDEPENDIENTE del veredicto, D34-04):
#: ``n = 5`` basta para MEDIR, no para llamar "confirmado" a nada.
EVIDENCE_NOT_MEASURED = "NOT_MEASURED"
EVIDENCE_PRELIMINARY = "PRELIMINARY"
EVIDENCE_SUPPORTED = "SUPPORTED"
EVIDENCE_STRONG = "STRONG"
EVIDENCE_QUALITIES: tuple[str, ...] = (
    EVIDENCE_NOT_MEASURED,
    EVIDENCE_PRELIMINARY,
    EVIDENCE_SUPPORTED,
    EVIDENCE_STRONG,
)

#: Familias de error del bucle. ``SOFTWARE`` es el fallo lógico, ``OPERATIONAL`` la gestión
#: comprometida y ``DATA`` el dato no verificable.
SOFTWARE = "SOFTWARE"
OPERATIONAL = "OPERATIONAL"
DATA = "DATA"
ERROR_KINDS: tuple[str, ...] = (SOFTWARE, OPERATIONAL, DATA)

#: Pasos DETERMINISTAS de la cadena: si difieren, es un fallo lógico (no ruido de medición).
DETERMINISTIC_STEPS: frozenset[str] = frozenset({"SIGNAL", "ORDER", "FILL"})

#: Suelo de muestra declarado (NO se relaja para forzar un veredicto). Por debajo de él un
#: valor se declara ``NOT_MEASURED``: no se afirma nada con dos ciclos.
MIN_VALUE_CYCLES = 5
#: Hit-rate mínimo declarado para ``OOS_SUPPORTED`` (una esperanza positiva sin acierto
#: sólido no soporta nada).
MIN_VALUE_HIT_RATE = 0.5
#: Suelos de CALIDAD de evidencia (declarados, no una decisión estadística definitiva): con
#: ``n = 5`` se puede MEDIR, pero no llamar "soportado" a nada. ``n >= 20`` es el mínimo
#: para hablar de evidencia OOS soportada; ``n >= 32`` la refuerza.
EVIDENCE_SUPPORTED_MIN_CYCLES = 20
EVIDENCE_STRONG_MIN_CYCLES = 32

#: Estados de la reconciliación de integridad que se leen como fallo de SOFTWARE.
_RECONCILE_SOFTWARE_STATES: frozenset[str] = frozenset({"drift", "blocked"})

#: Estados de una orden de salida automática que son una incidencia OPERATIVA.
_EXIT_ORDER_OPERATIONAL_STATES: frozenset[str] = frozenset({"ABANDONED", "EMERGENCY"})

#: Estados de un evento de ejecución que son una incidencia OPERATIVA.
_EXECUTION_EVENT_OPERATIONAL_STATUSES: frozenset[str] = frozenset({"FAILED", "RETRY"})

#: Códigos de motivo del cubo ``DATA`` (dato no verificable, fail-closed).
DATA_REASON_CODES: frozenset[str] = frozenset(
    {code for code, bucket in VETO_BUCKET_BY_REASON.items() if bucket == BUCKET_DATA}
) | {NO_MARK_DATA, "other"}

#: Códigos de motivo del ciclo de reserva que son una incidencia OPERATIVA (no un veto).
OPERATIONAL_REASON_CODES: frozenset[str] = frozenset(
    {
        PROTECTION_MISSING,
        RESERVATION_UNMEASURABLE,
        RESERVATION_RELEASED_FILL,
        RESERVATION_RELEASED_CANCEL,
        RESERVATION_RELEASED_RESTART,
        RESERVATION_RELEASED_ROLLBACK,
    }
)

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Muestras por valor pequenas: NOT_MEASURED sera frecuente; el suelo de muestra se declara.",
    "La deteccion de divergencia de software es heuristica (pasos deterministas), no una prueba de bug.",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0.",
    "El lado ejecutado queda NOT_MEASURED en dias historicos hasta que la ventana PAPER opere ese D.",
    "OOS_SUPPORTED describe evidencia de REPLAY/OOS, no ejecucion PAPER: CONFIRMED queda "
    "reservado para evidencia PAPER y NO se emite todavia.",
    "evidenceQuality clasifica la muestra: NOT_MEASURED (<5), PRELIMINARY (5-19), "
    "SUPPORTED (20-31), STRONG (>=32).",
    "La matriz valor x dia atribuye por entryDay (dia de decision); exitDay es atributo de la "
    "operacion, no dimension del experimento.",
    "El watch derivado del catalogo actual puede introducir survivorship bias en estudios "
    "historicos (ver meta.survivorBiasRisk). El contrato Universe(D) ya modela intervalo de "
    "fin/delistado y elegibilidad DEMOSTRABLE, pero la fuente real sigue pendiente: el watch "
    "no se construye con el.",
    "El veredicto OOS es AGREGADO por instrumento (suelo de muestra n>=5): un veredicto por "
    "ciclo seria n=1 y no mediria nada. El indice cycles[] solo desambigua a que valor "
    "pertenece cada ciclo; NO emite veredicto por ciclo.",
)


# ── Clasificación de errores (reutiliza el vocabulario existente) ─────────────────


def software_error_for_step(step: Any, verdict: Any) -> str | None:
    """Nombre del paso si una divergencia es de SOFTWARE (paso determinista); si no, ``None``.

    Una divergencia en un paso NO determinista (p. ej. ``PROTECTION``) es una señal a mirar,
    pero no se cataloga como fallo lógico: por eso el catálogo solo recoge deterministas.
    """
    key = str(step or "").strip().upper()
    if key in DETERMINISTIC_STEPS and str(verdict or "").strip().upper() == VERDICT_DIVERGENT:
        return key
    return None


def error_kind_for_reason(code: Any) -> str | None:
    """Familia de un código de motivo; ``None`` si no está catalogado (se declara, no se fuerza).

    La precedencia da prioridad a ``OPERATIONAL`` sobre ``DATA``: un código del ciclo de
    reserva que además cayera en el cubo de datos seguiría siendo una incidencia de operativa.
    """
    key = str(code or "").strip()
    if not key:
        return None
    if key in OPERATIONAL_REASON_CODES:
        return OPERATIONAL
    if key in DATA_REASON_CODES:
        return DATA
    return None


def error_kind_for_exit_state(state: Any) -> str | None:
    """``OPERATIONAL`` si la orden de salida automática quedó ``ABANDONED``/``EMERGENCY``."""
    key = str(state or "").strip().upper()
    return OPERATIONAL if key in _EXIT_ORDER_OPERATIONAL_STATES else None


def error_kind_for_execution_status(status: Any) -> str | None:
    """``OPERATIONAL`` si el evento de ejecución quedó ``FAILED``/``RETRY``."""
    key = str(status or "").strip().upper()
    return OPERATIONAL if key in _EXECUTION_EVENT_OPERATIONAL_STATUSES else None


def error_kind_for_reconcile_state(state: Any) -> str | None:
    """``SOFTWARE`` si la reconciliación de integridad declaró ``drift``/``blocked``."""
    key = str(state or "").strip().lower()
    return SOFTWARE if key in _RECONCILE_SOFTWARE_STATES else None


def classify_error(
    *,
    step: Any = None,
    verdict: Any = None,
    reason_code: Any = None,
    exit_state: Any = None,
    execution_status: Any = None,
    reconcile_state: Any = None,
) -> dict[str, str] | None:
    """Clasifica UNA señal durable en ``{"kind", "code"}``; ``None`` si no es un error.

    El orden es fail-loud: primero SOFTWARE (un paso determinista que no cuadra), luego
    OPERATIONAL (gestión/ejecución comprometida) y por último DATA. Un código sin familia no
    se cataloga: se declara ``None`` en vez de inventarle un cubo.
    """
    step_name = software_error_for_step(step, verdict)
    if step_name is not None:
        return {"kind": SOFTWARE, "code": step_name}
    reconcile_kind = error_kind_for_reconcile_state(reconcile_state)
    if reconcile_kind is not None:
        return {"kind": reconcile_kind, "code": str(reconcile_state).strip().lower()}
    exit_kind = error_kind_for_exit_state(exit_state)
    if exit_kind is not None:
        return {"kind": exit_kind, "code": str(exit_state).strip().upper()}
    execution_kind = error_kind_for_execution_status(execution_status)
    if execution_kind is not None:
        return {"kind": execution_kind, "code": str(execution_status).strip().upper()}
    reason_kind = error_kind_for_reason(reason_code)
    if reason_kind is not None:
        return {"kind": reason_kind, "code": str(reason_code).strip()}
    return None


# ── Veredicto por valor ──────────────────────────────────────────────────────────


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evidence_quality_for(measured_cycles: Any) -> str:
    """Tier de CALIDAD de evidencia por tamaño de muestra (eje independiente del veredicto).

    ``NOT_MEASURED`` (<5), ``PRELIMINARY`` (5-19), ``SUPPORTED`` (20-31), ``STRONG`` (>=32).
    No decide nada por sí solo: describe cuánta muestra respalda el veredicto. Un valor no
    numérico se trata como ``0`` mediciones (fail-closed).
    """
    try:
        cycles = int(measured_cycles)
    except (TypeError, ValueError):
        cycles = 0
    if cycles < MIN_VALUE_CYCLES:
        return EVIDENCE_NOT_MEASURED
    if cycles < EVIDENCE_SUPPORTED_MIN_CYCLES:
        return EVIDENCE_PRELIMINARY
    if cycles < EVIDENCE_STRONG_MIN_CYCLES:
        return EVIDENCE_SUPPORTED
    return EVIDENCE_STRONG


def build_value_scorecard(
    symbol: Any,
    *,
    round_trips: Sequence[Mapping[str, Any]] = (),
    errors: Sequence[Mapping[str, Any]] = (),
    days: Sequence[Any] = (),
) -> dict[str, Any]:
    """Ficha de UN valor: expectativa, hit-rate, cobertura y veredicto (PURA).

    ``round_trips`` son las operaciones cerradas del valor en la ventana (forma de
    ``replay_oos.RoundTrip.to_dict``: ``realizedR`` + ``entryDay``/``exitDay``). Un ``realizedR``
    ilegible se declara hueco (no cuenta como ciclo). ``errors`` son las incidencias del valor
    (``{"kind", "code", "day"}``). ``days`` es el calendario de la ventana (para la cobertura y
    la matriz valor × día). Nada se rellena con ``0``.

    Atribución temporal (D34-02): el día del experimento es el **día de DECISIÓN**
    (``entryDay``), la MISMA dimensión con la que ``v2_90`` selecciona los ciclos. ``exitDay``
    es un atributo de la operación, no una dimensión: si un ciclo se abre en ``D`` y cierra
    fuera de la ventana, pertenece a ``D``. Un ciclo sin ``entryDay`` legible no se atribuye a
    ningún día (hueco declarado), nunca se cae a ``exitDay``.
    """
    name = str(symbol or "").strip()
    window_days = [normalize_day(day) for day in days if normalize_day(day)]

    by_day_r: dict[str, list[float]] = {}
    by_day_cycles: dict[str, int] = {}
    realized: list[float] = []
    for trip in round_trips or ():
        value = finite_number(trip.get("realizedR"))
        if value is None:
            continue
        realized.append(value)
        day = normalize_day(trip.get("entryDay"))
        if day:
            by_day_r.setdefault(day, []).append(value)
            by_day_cycles[day] = by_day_cycles.get(day, 0) + 1

    errors_by_day: dict[str, int] = {}
    errors_by_kind: dict[str, int] = {kind: 0 for kind in ERROR_KINDS}
    for error in errors or ():
        kind = str(error.get("kind") or "").strip().upper()
        if kind not in errors_by_kind:
            continue
        errors_by_kind[kind] += 1
        day = normalize_day(error.get("day"))
        if day:
            errors_by_day[day] = errors_by_day.get(day, 0) + 1

    measured_cycles = len(realized)
    expectancy_r = _mean(realized)
    hit_rate = (
        sum(1 for value in realized if value > 0) / measured_cycles if measured_cycles else None
    )
    software_errors = errors_by_kind[SOFTWARE]
    total_errors = sum(errors_by_kind.values())

    verdict, reason = _value_verdict(
        measured_cycles=measured_cycles,
        expectancy_r=expectancy_r,
        hit_rate=hit_rate,
        software_errors=software_errors,
    )
    evidence_quality = evidence_quality_for(measured_cycles)

    by_day: dict[str, dict[str, Any]] = {}
    for day in window_days:
        values = by_day_r.get(day, [])
        cycles = by_day_cycles.get(day, 0)
        by_day[day] = {
            "realizedR": sum(values) if values else None,
            "cycles": cycles,
            "errors": errors_by_day.get(day, 0),
        }

    return {
        "symbol": name,
        "verdict": verdict,
        "verdictReason": reason,
        "evidenceQuality": evidence_quality,
        "expectancyR": expectancy_r,
        "hitRate": hit_rate,
        "measuredCycles": measured_cycles,
        "daysCovered": sum(1 for day in window_days if by_day_cycles.get(day, 0) > 0),
        "windowDays": len(window_days),
        "realizedRTotal": sum(realized) if realized else None,
        "errors": dict(errors_by_kind),
        "errorTotal": total_errors,
        "byDay": by_day,
        "limits": {
            "minCycles": MIN_VALUE_CYCLES,
            "minHitRate": MIN_VALUE_HIT_RATE,
            "supportedMinCycles": EVIDENCE_SUPPORTED_MIN_CYCLES,
            "strongMinCycles": EVIDENCE_STRONG_MIN_CYCLES,
        },
    }


def _value_verdict(
    *,
    measured_cycles: int,
    expectancy_r: float | None,
    hit_rate: float | None,
    software_errors: int,
) -> tuple[str, str]:
    """Veredicto + motivo, con la precedencia DECLARADA (fail-loud).

    1. Un error de SOFTWARE es evidencia POSITIVA ⇒ ``REFUTED`` aunque la muestra sea pequeña:
       un fallo lógico no se esconde detrás del suelo de muestra.
    2. Muestra insuficiente ⇒ ``NOT_MEASURED`` (no se afirma nada).
    3. ``expectancyR <= 0`` ⇒ ``REFUTED`` (la tesis no paga).
    4. ``expectancyR > 0`` y hit-rate suficiente ⇒ ``OOS_SUPPORTED`` SOLO si la muestra llega
       al suelo de evidencia soportada (``>= 20``); por debajo ⇒ ``MIXED`` (``preliminary_sample``).
    5. Resto ⇒ ``MIXED`` (se mide, no concluye).

    El veredicto NUNCA llama "confirmado" a evidencia de replay (D34-03): ``CONFIRMED`` queda
    reservado a evidencia PAPER. Un ``expectancyR``/``hit_rate`` ausente con muestra ``>=``
    suelo es imposible por construcción; por si acaso, se trata como ``NOT_MEASURED``.
    """
    if software_errors > 0:
        return VALUE_REFUTED, "software_divergence"
    if measured_cycles < MIN_VALUE_CYCLES:
        return VALUE_NOT_MEASURED, "insufficient_sample"
    if expectancy_r is None or hit_rate is None:
        return VALUE_NOT_MEASURED, "no_measurement"
    if expectancy_r <= 0:
        return VALUE_REFUTED, "negative_expectancy"
    if hit_rate < MIN_VALUE_HIT_RATE:
        return VALUE_MIXED, "no_conclusive_edge"
    if measured_cycles < EVIDENCE_SUPPORTED_MIN_CYCLES:
        return VALUE_MIXED, "preliminary_sample"
    return VALUE_OOS_SUPPORTED, "positive_expectancy"


# ── Matriz valor × día (heatmap) y catálogo de errores ───────────────────────────


def build_day_matrix(
    values: Sequence[Mapping[str, Any]],
    *,
    days: Sequence[Any],
) -> list[dict[str, Any]]:
    """Cuadrícula valor × día derivada de las fichas: una fila por símbolo, una celda por día.

    Cada celda declara ``outcome`` (``GAIN``/``LOSS``/``NOT_MEASURED``) y, si hubo, la familia
    de error dominante del día (``SOFTWARE`` > ``OPERATIONAL`` > ``DATA``). No interpreta más
    de lo que la ficha ya midió.
    """
    window_days = [normalize_day(day) for day in days if normalize_day(day)]
    rows: list[dict[str, Any]] = []
    for value in values:
        symbol = str(value.get("symbol") or "")
        by_day = value.get("byDay") if isinstance(value.get("byDay"), Mapping) else {}
        cells: list[dict[str, Any]] = []
        for day in window_days:
            cell = by_day.get(day) if isinstance(by_day, Mapping) else None
            cell_map = cell if isinstance(cell, Mapping) else {}
            realized = finite_number(cell_map.get("realizedR"))
            cycles = int(cell_map.get("cycles") or 0)
            errors = int(cell_map.get("errors") or 0)
            cells.append(
                {
                    "day": day,
                    "realizedR": realized,
                    "cycles": cycles,
                    "errors": errors,
                    "outcome": _cell_outcome(realized, cycles, errors),
                }
            )
        rows.append({"symbol": symbol, "cells": cells})
    return rows


def _cell_outcome(realized_r: float | None, cycles: int, errors: int) -> str:
    """Etiqueta de una celda del heatmap: error > signo del R > sin medir."""
    if errors > 0:
        return "ERROR"
    if cycles <= 0 or realized_r is None:
        return "NOT_MEASURED"
    if realized_r > 0:
        return "GAIN"
    if realized_r < 0:
        return "LOSS"
    return "FLAT"


def summarize_feedback(
    values: Sequence[Mapping[str, Any]],
    errors: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Resumen GLOBAL: conteo de veredictos, de CALIDAD de evidencia y de errores por familia."""
    verdicts = {verdict: 0 for verdict in VALUE_VERDICTS}
    evidence = {tier: 0 for tier in EVIDENCE_QUALITIES}
    for value in values:
        key = str(value.get("verdict") or "")
        if key in verdicts:
            verdicts[key] += 1
        tier = str(value.get("evidenceQuality") or "")
        if tier in evidence:
            evidence[tier] += 1
    error_counts = {kind: 0 for kind in ERROR_KINDS}
    for error in errors or ():
        kind = str(error.get("kind") or "").strip().upper()
        if kind in error_counts:
            error_counts[kind] += 1
    return {
        "values": len(values),
        "oosSupported": verdicts[VALUE_OOS_SUPPORTED],
        "mixed": verdicts[VALUE_MIXED],
        "refuted": verdicts[VALUE_REFUTED],
        "notMeasured": verdicts[VALUE_NOT_MEASURED],
        "measuredValues": (
            verdicts[VALUE_OOS_SUPPORTED] + verdicts[VALUE_MIXED] + verdicts[VALUE_REFUTED]
        ),
        "byEvidenceQuality": evidence,
        "errors": {**error_counts, "total": sum(error_counts.values())},
    }


def normalize_error(
    *,
    day: Any = None,
    symbol: Any = None,
    kind: Any,
    code: Any,
    detail: Any = None,
) -> dict[str, Any] | None:
    """Normaliza UNA incidencia al contrato del catálogo; ``None`` si falta ``kind``/``code``.

    Un ``kind`` fuera de ``ERROR_KINDS`` NO se cuela en el catálogo (se declara ausente en vez
    de crear una familia fantasma).
    """
    family = str(kind or "").strip().upper()
    label = str(code or "").strip()
    if family not in ERROR_KINDS or not label:
        return None
    row: dict[str, Any] = {
        "day": normalize_day(day),
        "symbol": str(symbol or "").strip(),
        "kind": family,
        "code": label,
    }
    if detail is not None:
        row["detail"] = str(detail)
    return row


# ── Índice de ciclos (desambiguación por ``cycleId``) ────────────────────────────


def _normalize_cycle_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Fila del índice de ciclos con la forma EXACTA del contrato; un campo ausente es hueco.

    No re-deriva: copia lo que el replay ya midió (``cycleId``/``symbol``/``entryDay``/
    ``exitDay``/``strategyVersion``/``realizedR``) y declara ``None`` cuando falta. Un
    ``realizedR`` ilegible es un hueco (no un ``0``).
    """
    cycle_id = str(row.get("cycleId") or "").strip()
    version = row.get("strategyVersion")
    return {
        "cycleId": cycle_id,
        "symbol": str(row.get("symbol") or "").strip(),
        "entryDay": normalize_day(row.get("entryDay")) or None,
        "exitDay": normalize_day(row.get("exitDay")) or None,
        "strategyVersion": str(version) if version is not None else None,
        "realizedR": finite_number(row.get("realizedR")),
    }


def build_cycle_index(
    round_trips: Sequence[Mapping[str, Any]] = (),
    *,
    days: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    """Índice de CICLOS de la ventana: ``cycleId`` → identidad del ciclo (PURA y determinista).

    El veredicto OOS es AGREGADO por instrumento (suelo de muestra ``n >= 5``); un veredicto
    por ciclo sería ``n = 1`` y no mediría nada. Este índice sólo DESAMBIGUA a qué valor
    pertenece cada ciclo, para que el consumidor resuelva la explicación por ``cycleId`` en vez
    de por ``symbol`` (dos ciclos del mismo instrumento dejan de compartir explicación en
    silencio).

    Un ciclo SIN ``cycleId`` legible se OMITE (se declara el hueco; nunca se inventa una clave
    para forzar una resolución). ``entryDay`` acota a la ventana (un ciclo sin día legible no se
    descarta por eso: se conserva como hueco declarado). ``exitDay`` es atributo del ciclo, no
    filtro de ventana. Salida ordenada por ``cycleId`` (mismo estado ⇒ mismo payload).
    """
    window_days = {day for day in (normalize_day(item) for item in days) if day}
    by_cycle: dict[str, dict[str, Any]] = {}
    for trip in round_trips or ():
        cycle_id = str(trip.get("cycleId") or "").strip()
        if not cycle_id:
            continue
        row = _normalize_cycle_row(trip)
        if window_days and row["entryDay"] and row["entryDay"] not in window_days:
            continue
        by_cycle[cycle_id] = row
    return [by_cycle[key] for key in sorted(by_cycle)]


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_dia_d_feedback_artifact(
    *,
    window_from: Any,
    window_to: Any,
    days: Sequence[Any],
    values: Sequence[Mapping[str, Any]],
    cycles: Sequence[Mapping[str, Any]] = (),
    errors: Sequence[Mapping[str, Any]] = (),
    gate: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Construye el payload canónico del feedback (puro y determinista).

    ``values`` son fichas ya construidas con ``build_value_scorecard`` (se ordenan por
    símbolo); ``cycles`` el índice de ciclos (``build_cycle_index``, deduplicado y ordenado por
    ``cycleId``); ``errors`` el catálogo normalizado; ``gate`` la declaración de ``window_gate``.
    Los símbolos y los ciclos se deduplican y ordenan para que el mismo estado produzca el mismo
    payload byte a byte (sin reloj ni identificadores aleatorios).
    """
    window_days = [normalize_day(day) for day in days if normalize_day(day)]
    unique_days = sorted(set(window_days))
    ordered_values = sorted(values, key=lambda item: str(item.get("symbol") or ""))
    normalized_errors = [
        row
        for row in (
            normalize_error(
                day=error.get("day"),
                symbol=error.get("symbol"),
                kind=error.get("kind"),
                code=error.get("code"),
                detail=error.get("detail"),
            )
            for error in errors or ()
        )
        if row is not None
    ]
    normalized_errors.sort(
        key=lambda row: (str(row.get("day")), str(row.get("symbol")), str(row.get("kind")), str(row.get("code")))
    )
    matrix = build_day_matrix(ordered_values, days=unique_days)
    ordered_cycles: list[dict[str, Any]] = []
    seen_cycles: set[str] = set()
    for cycle in cycles or ():
        row = _normalize_cycle_row(cycle)
        if not row["cycleId"] or row["cycleId"] in seen_cycles:
            continue
        seen_cycles.add(row["cycleId"])
        ordered_cycles.append(row)
    ordered_cycles.sort(key=lambda item: item["cycleId"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "DIA_D_AUTO_FEEDBACK",
        "readOnly": True,
        "matrixBasis": "entryDay",
        "window": {
            "from": normalize_day(window_from),
            "to": normalize_day(window_to),
            "days": unique_days,
        },
        "summary": summarize_feedback(ordered_values, normalized_errors),
        "values": [dict(value) for value in ordered_values],
        "cycles": ordered_cycles,
        "matrix": matrix,
        "errors": normalized_errors,
        "gate": dict(gate or {}),
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "DATA",
    "DATA_REASON_CODES",
    "DEFAULT_LIMITS",
    "DETERMINISTIC_STEPS",
    "ERROR_KINDS",
    "EVIDENCE_NOT_MEASURED",
    "EVIDENCE_PRELIMINARY",
    "EVIDENCE_QUALITIES",
    "EVIDENCE_STRONG",
    "EVIDENCE_STRONG_MIN_CYCLES",
    "EVIDENCE_SUPPORTED",
    "EVIDENCE_SUPPORTED_MIN_CYCLES",
    "MIN_VALUE_CYCLES",
    "MIN_VALUE_HIT_RATE",
    "OPERATIONAL",
    "OPERATIONAL_REASON_CODES",
    "SCHEMA_VERSION",
    "SOFTWARE",
    "VALUE_CONFIRMED",
    "VALUE_MIXED",
    "VALUE_NOT_MEASURED",
    "VALUE_OOS_SUPPORTED",
    "VALUE_REFUTED",
    "VALUE_VERDICTS",
    "build_cycle_index",
    "build_day_matrix",
    "build_dia_d_feedback_artifact",
    "build_value_scorecard",
    "classify_error",
    "error_kind_for_execution_status",
    "error_kind_for_exit_state",
    "error_kind_for_reason",
    "error_kind_for_reconcile_state",
    "evidence_quality_for",
    "normalize_error",
    "software_error_for_step",
    "summarize_feedback",
]
