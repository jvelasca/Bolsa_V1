#!/usr/bin/env python
"""Auditoría de los ciclos ``stopFiredNotFilled``: artefacto de barra ausente vs ejecución.

Pregunta que responde: de los ciclos que el ledger marca ``stopFiredNotFilled``, ¿cuántos
lo están porque el motor REAL tocó el stop y no lo ejecutó, y cuántos porque una barra
AUSENTE codificada como ``mark = 0.0`` cruzó el stop por construcción (``0 <= stop`` en
un LONG)?

Por qué importa: el ``mark = 0.0`` no es un precio. ``finite_number`` lo acepta y
``mark <= stop`` lo cuenta como toque, así que infla ``stopTouchDays``/``firstTouchDay``/
``maeR`` y puede poner la marca en ciclos donde el stop NUNCA se disparó. Un ``0.0``
cuenta como artefacto; un stop disparado con ``orderCreated=True`` y ``filledQty=0``
cuenta como ejecución.

Regla dura (la misma del ledger, sin inventar): un ``mark`` nulo o ``<= 0`` es **barra
ausente**, nunca un toque. El resto de la clasificación reproduce literalmente
``_decision_route`` de
``packages/py/application/src/bolsa_application/dia_d_multi_sampling.py``
(token ``STRUCTURAL_STOP``, insensible a mayúsculas, en ``decisionReasons`` o
``decisionLabel``), para que el reparto sea comparable con el publicado.

Uso::

    python scripts/stop_fired_not_filled_audit.py --selftest
    python scripts/stop_fired_not_filled_audit.py

Salida: tabla por ciclo por stdout y un JSON en ``--json-out`` (gitignored bajo
``operability_runs/``). Solo lectura: no escribe en PostgreSQL ni toca el árbol.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── Contrato con el ledger ──────────────────────────────────────────────────────────
STOP_TOKEN = "STRUCTURAL_STOP"
LONG = "long"
SHORT = "short"

#: Marcas que NO son precios: barra ausente codificada como 0 (o negativa).
MISSING_MARK_AT_OR_BELOW = 0.0

BUCKET_PURE_ARTIFACT = "artefacto_puro"
BUCKET_METRIC_ARTIFACT = "artefacto_metrico"
BUCKET_LATE_FILL = "fill_posterior"
BUCKET_ORDER_NO_FILL = "orden_creada_sin_fill"
BUCKET_FIRED_NO_ORDER = "stop_evaluado_sin_orden"
BUCKET_UNMEASURABLE = "no_medible"
BUCKET_UNFLAGGED = "sin_marca"

BUCKET_ORDER = (
    BUCKET_LATE_FILL,
    BUCKET_ORDER_NO_FILL,
    BUCKET_FIRED_NO_ORDER,
    BUCKET_UNMEASURABLE,
    BUCKET_PURE_ARTIFACT,
    BUCKET_METRIC_ARTIFACT,
)

#: Cubos que son fallo de EJECUCIÓN (la marca la puso una barra real).
EXECUTION_BUCKETS = (
    BUCKET_LATE_FILL,
    BUCKET_ORDER_NO_FILL,
    BUCKET_FIRED_NO_ORDER,
    BUCKET_UNMEASURABLE,
)

#: Cubos que son artefacto de datos (la marca la puso una barra ausente).
ARTIFACT_BUCKETS = (BUCKET_PURE_ARTIFACT, BUCKET_METRIC_ARTIFACT)

ROOT = Path(__file__).resolve().parents[1]


# ── Núcleo puro ─────────────────────────────────────────────────────────────────────
def finite_number(value: Any) -> float | None:
    """``float`` finito o ``None`` (mismo criterio que ``dia_d_auto.finite_number``)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def is_missing_bar(mark: float | None) -> bool:
    """``True`` si la marca no es un precio: hueco o ``<= 0`` (barra ausente)."""
    return mark is None or mark <= MISSING_MARK_AT_OR_BELOW


def _stop_fired(row: dict[str, Any]) -> bool:
    reasons = [str(reason) for reason in (row.get("decisionReasons") or [])]
    label = str(row.get("decisionLabel") or "").strip()
    return any(r.strip().upper() == STOP_TOKEN for r in reasons) or label.upper() == STOP_TOKEN


@dataclass(frozen=True)
class Tick:
    """Un día de la secuencia con su lectura de toque ya desambiguada."""

    day: str | None
    mark: float | None
    stop: float | None
    fired: bool
    order_created: bool | None
    filled_qty: float | None
    survived: bool | None
    missing_bar: bool
    real_touch: bool
    artifact_touch: bool


def read_ticks(sequence: Any, direction: str | None) -> list[Tick]:
    """Proyecta la secuencia del ledger en ticks con toque REAL y toque ARTEFACTO separados.

    Un toque artefacto es el que produce una marca ausente (``<= 0``): se cuenta para poder
    explicar la marca del ledger, pero **nunca** como precio. Un toque real exige marca y
    stop finitos y ``> 0``.
    """
    ticks: list[Tick] = []
    for row in sequence or ():
        if not isinstance(row, dict):
            continue
        mark = finite_number(row.get("mark"))
        stop = finite_number(row.get("currentStop"))
        missing = is_missing_bar(mark)
        comparable = not missing and stop is not None
        real_touch = bool(
            comparable
            and (
                (direction == LONG and mark is not None and mark <= stop)  # type: ignore[operator]
                or (direction == SHORT and mark is not None and mark >= stop)  # type: ignore[operator]
            )
        )
        artifact_touch = bool(
            missing
            and stop is not None
            and (
                (direction == LONG and mark is not None and mark <= stop)  # type: ignore[operator]
                or (direction == SHORT and mark is not None and mark >= stop)  # type: ignore[operator]
            )
        )
        created = row.get("orderCreated")
        survived = row.get("survived")
        ticks.append(
            Tick(
                day=str(row.get("day"))[:10] or None if row.get("day") else None,
                mark=mark,
                stop=stop,
                fired=_stop_fired(row),
                order_created=created if isinstance(created, bool) else None,
                filled_qty=finite_number(row.get("filledQty")),
                survived=survived if isinstance(survived, bool) else None,
                missing_bar=missing,
                real_touch=real_touch,
                artifact_touch=artifact_touch,
            )
        )
    return ticks


def classify_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    """Clasifica UN ciclo. Puro: no toca disco ni base de datos.

    La marca ``stopFiredNotFilled`` del ledger se reproduce con SU regla exacta (un tick
    con el stop disparado, ``filledQty`` nulo o 0 y ``survived=True``). Después se separa
    lo que la pone en dos causas incompatibles:

    * **artefacto** — el disparo ocurrió en una barra AUSENTE (``mark <= 0``), que cruza el
      stop por construcción en un LONG;
    * **ejecución** — el disparo ocurrió en una barra real y la orden no llenó en ese tick.

    La ejecución se subdivide por lo que pasa después del primer tick real sin fill:
    ``fill_posterior`` (llenó más tarde: la posición sobrevivió al toque), ``nunca_llena``
    (no hay fill posterior; si además hay orden, el fallo es de venue).
    """
    direction = str(cycle.get("direction") or "").strip().lower() or None
    ticks = read_ticks(cycle.get("sequence"), direction)

    real_touches = [t for t in ticks if t.real_touch]
    artifact_touches = [t for t in ticks if t.artifact_touch]
    fired_real = [t for t in real_touches if t.fired]

    # Regla del ledger, literal: disparo + sin fill + posición viva.
    def sets_flag(t: Tick) -> bool:
        return bool(
            t.fired
            and (t.filled_qty is None or t.filled_qty == 0.0)
            and t.survived is True
        )

    flag_events = [(i, t) for i, t in enumerate(ticks) if sets_flag(t)]
    real_events = [(i, t) for i, t in flag_events if t.real_touch]
    artifact_events = [(i, t) for i, t in flag_events if t.artifact_touch]
    untouch_events = [(i, t) for i, t in flag_events if not (t.real_touch or t.artifact_touch)]

    ledger_flag = bool(cycle.get("stopFiredNotFilled"))
    reproduced = bool(flag_events)

    # ¿El STOP ejecutó DESPUÉS del primer disparo real sin fill? Un fill de la salida por
    # tesis NO cuenta como stop ejecutado: es la posición saliendo por otra puerta.
    first_index = real_events[0][0] if real_events else None
    stop_fill_index = None
    if first_index is not None:
        stop_fill_index = next(
            (
                i
                for i, t in enumerate(ticks)
                if i > first_index and t.fired and t.filled_qty is not None and t.filled_qty > 0.0
            ),
            None,
        )

    if not ledger_flag:
        bucket = BUCKET_UNFLAGGED
    elif not real_events:
        bucket = BUCKET_METRIC_ARTIFACT if real_touches else BUCKET_PURE_ARTIFACT
    elif stop_fill_index is not None:
        bucket = BUCKET_LATE_FILL
    elif any(t.order_created is True for _, t in real_events):
        bucket = BUCKET_ORDER_NO_FILL
    elif all(t.order_created is False for _, t in real_events):
        bucket = BUCKET_FIRED_NO_ORDER
    else:
        bucket = BUCKET_UNMEASURABLE

    first_touch_is_artifact = bool(
        artifact_touches
        and real_touches
        and min(
            i for i, t in enumerate(ticks) if t.artifact_touch
        )
        < min(i for i, t in enumerate(ticks) if t.real_touch)
    )

    exit_mechanism = str(cycle.get("exitMechanism") or "")
    realized = finite_number(cycle.get("realizedR"))
    stop_at_exit = finite_number(cycle.get("currentStopAtExitR"))
    ledger_touch_days = finite_number(cycle.get("stopTouchDays"))

    return {
        "cycleId": cycle.get("cycleId"),
        "symbol": cycle.get("symbol"),
        "entryDay": cycle.get("entryDay"),
        "exitDay": cycle.get("exitDay"),
        "direction": direction,
        "ledgerFlag": ledger_flag,
        "reproduced": reproduced,
        "bucket": bucket,
        "timelineDays": len(ticks),
        "realTouchDays": len(real_touches),
        "artifactTouchDays": len(artifact_touches),
        "ledgerStopTouchDays": int(ledger_touch_days) if ledger_touch_days is not None else None,
        "firstTouchIsArtifact": first_touch_is_artifact,
        "flagEvents": len(flag_events),
        "flagRealEvents": len(real_events),
        "flagArtifactEvents": len(artifact_events),
        "flagUntouchEvents": len(untouch_events),
        "firedRealDays": len(fired_real),
        "firstFireDay": real_events[0][1].day if real_events else None,
        "stopFillAfterFireDay": (
            ticks[stop_fill_index].day if stop_fill_index is not None else None
        ),
        "lagTicksToStopFill": (
            stop_fill_index - real_events[0][0] if stop_fill_index is not None else None
        ),
        "exitMechanism": exit_mechanism,
        "decisionRoute": cycle.get("decisionRoute"),
        "realizedR": realized,
        "currentStopAtExitR": stop_at_exit,
        "excessLossR": (
            round(realized - stop_at_exit, 6)
            if realized is not None and stop_at_exit is not None
            else None
        ),
        "unprotectedUntilThesis": bool(
            exit_mechanism != "STOP_EJECUTADO" and real_events and stop_fill_index is None
        ),
        "touchDays": [t.day for t in real_touches],
        "firedDays": [t.day for _, t in real_events],
        "artifactDays": [t.day for t in artifact_touches],
    }


def audit(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [classify_cycle(cycle) for cycle in cycles]


def artifact_metrics(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """Cuánto contamina el ``mark = 0.0`` la MÉTRICA de toques (no la marca del ledger).

    Recorre los 192 ciclos (no solo los marcados) y cuenta filas con marca ausente que,
    por ``mark <= stop``, se cuentan hoy como toque. Compara ``stopTouchDays`` publicado
    con el recuento de toques REALES.
    """
    rows_with_missing = 0
    cycles_with_missing = 0
    inflated_cycles = 0
    touch_days_declared = 0
    touch_days_real = 0
    affected: list[dict[str, Any]] = []
    for cycle in cycles:
        direction = str(cycle.get("direction") or "").strip().lower() or None
        ticks = read_ticks(cycle.get("sequence"), direction)
        missing = [t for t in ticks if t.missing_bar]
        if missing:
            rows_with_missing += len(missing)
            cycles_with_missing += 1
        real = sum(1 for t in ticks if t.real_touch)
        declared_value = finite_number(cycle.get("stopTouchDays"))
        declared = int(declared_value) if declared_value is not None else real
        touch_days_declared += declared
        touch_days_real += real
        if declared > real:
            inflated_cycles += 1
            if len(affected) < 20:
                affected.append(
                    {
                        "cycleId": cycle.get("cycleId"),
                        "entryDay": cycle.get("entryDay"),
                        "stopTouchDaysDeclared": declared,
                        "stopTouchDaysReal": real,
                        "missingRows": len(missing),
                    }
                )
    return {
        "totalCycles": len(cycles),
        "missingMarkRows": rows_with_missing,
        "cyclesWithMissingMark": cycles_with_missing,
        "cyclesWithInflatedTouchDays": inflated_cycles,
        "stopTouchDaysDeclared": touch_days_declared,
        "stopTouchDaysReal": touch_days_real,
        "examples": affected,
    }


# ── Journal por ciclo (secuencia día a día) ─────────────────────────────────────────
JOURNAL_SCHEMA = "stop-fired-not-filled-journal-v1"

#: Campos de cada tick que se conservan en el journal (los mismos que viajan en el ledger).
JOURNAL_SEQUENCE_FIELDS = (
    "day",
    "mark",
    "currentStop",
    "orderCreated",
    "filledQty",
    "survived",
    "decisionReasons",
    "decisionLabel",
    "dayFills",
    "dayOrders",
    "maeR",
    "mfeR",
)

#: Columnas de la fidelidad que se adjuntan tal cual (sin reinterpretarlas).
JOURNAL_FIDELITY_FIELDS = (
    "simR",
    "realR",
    "reason",
    "realExitReason",
    "frictionR",
    "riskPctSim",
    "realRiskPct",
)

JOURNAL_CSV_FIELDS = (
    "cycleId",
    "symbolYahoo",
    "entryDay",
    "exitDay",
    "direction",
    "bucket",
    "firstFireDay",
    "stopFillAfterFireDay",
    "lagTicksToStopFill",
    "realTouchDays",
    "artifactTouchDays",
    "ledgerStopTouchDays",
    "exitMechanism",
    "realizedR",
    "currentStopAtExitR",
    "excessLossR",
    "simR",
    "realR",
    "pairStatus",
    "touchDays",
    "firedDays",
    "artifactDays",
    "sequenceJson",
)


def build_journal(
    rows: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
    fidelity: dict[tuple[str, str], dict[str, str]],
    symbol_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Une clasificación + secuencia del ledger + fila de fidelidad, ciclo a ciclo.

    No re-ejecuta el harness ni reinterpreta precios: copia el ``sequence`` que ya viaja
    en el ledger (192/192 ciclos lo traen) y la fila del CSV de fidelidad, y declara el
    ``pairStatus`` cuando no hay pareja. Es la pieza que faltaba para poder analizar los
    26 pares sin volver a correr nada.
    """
    by_id = {str(cycle.get("cycleId")): cycle for cycle in cycles}
    journal: list[dict[str, Any]] = []
    flagged = [row for row in rows if row["ledgerFlag"]]
    for row in sorted(flagged, key=lambda r: (str(r["entryDay"]), str(r["cycleId"]))):
        cycle = by_id.get(str(row["cycleId"])) or {}
        symbol = symbol_map.get(str(row["symbol"]), str(row["symbol"]))
        pair = fidelity.get((symbol, str(row["entryDay"])))
        sequence = [
            {field: tick.get(field) for field in JOURNAL_SEQUENCE_FIELDS}
            for tick in (cycle.get("sequence") or ())
            if isinstance(tick, dict)
        ]
        journal.append(
            {
                "cycleId": row["cycleId"],
                "symbol": row["symbol"],
                "symbolYahoo": symbol,
                "entryDay": row["entryDay"],
                "exitDay": row["exitDay"],
                "direction": row["direction"],
                "strategyVersion": cycle.get("strategyVersion"),
                "bucket": row["bucket"],
                "exitMechanism": row["exitMechanism"],
                "decisionRoute": row["decisionRoute"],
                "realTouchDays": row["realTouchDays"],
                "artifactTouchDays": row["artifactTouchDays"],
                "ledgerStopTouchDays": row["ledgerStopTouchDays"],
                "flagEvents": row["flagEvents"],
                "flagRealEvents": row["flagRealEvents"],
                "flagArtifactEvents": row["flagArtifactEvents"],
                "firstFireDay": row["firstFireDay"],
                "stopFillAfterFireDay": row["stopFillAfterFireDay"],
                "lagTicksToStopFill": row["lagTicksToStopFill"],
                "touchDays": row["touchDays"],
                "firedDays": row["firedDays"],
                "artifactDays": row["artifactDays"],
                "realizedR": row["realizedR"],
                "currentStopAtExitR": row["currentStopAtExitR"],
                "excessLossR": row["excessLossR"],
                "unprotectedUntilThesis": row["unprotectedUntilThesis"],
                "pairStatus": "paired" if pair is not None else "unmatched",
                **{field: (pair or {}).get(field) for field in JOURNAL_FIDELITY_FIELDS},
                "sequence": sequence,
            }
        )
    return journal


def write_journal(entries: list[dict[str, Any]], path: Path, ledger: Path, fidelity_path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "STOP_FIRED_NOT_FILLED_JOURNAL",
        "schema": JOURNAL_SCHEMA,
        "readOnly": True,
        "ledger": str(ledger),
        "fidelity": str(fidelity_path),
        "flagged": len(entries),
        "paired": sum(1 for entry in entries if entry["pairStatus"] == "paired"),
        "unmatched": [
            f"{entry['cycleId']}:{entry['symbolYahoo']}@{entry['entryDay']}"
            for entry in entries
            if entry["pairStatus"] != "paired"
        ],
        "buckets": {
            bucket: sum(1 for entry in entries if entry["bucket"] == bucket)
            for bucket in BUCKET_ORDER
        },
        "cycles": entries,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_journal_csv(entries: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=JOURNAL_CSV_FIELDS)
        writer.writeheader()
        for entry in entries:
            row = {field: entry.get(field) for field in JOURNAL_CSV_FIELDS}
            for field in ("touchDays", "firedDays", "artifactDays"):
                row[field] = ";".join(entry.get(field) or [])
            row["sequenceJson"] = json.dumps(
                entry.get("sequence") or [], ensure_ascii=False, separators=(",", ":")
            )
            writer.writerow(row)
    return path


# ── Cruce con la fidelidad ciclo a ciclo ────────────────────────────────────────────
def load_fidelity(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """``(symbol, entryDay) -> fila`` de ``fidelidad_calibrado.csv`` (si existe)."""
    if not path.exists():
        return {}
    out: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (str(row.get("symbol")), str(row.get("entryDay")))
            out.setdefault(key, row)
    return out


def execution_component(
    rows: list[dict[str, Any]],
    fidelity: dict[tuple[str, str], dict[str, str]],
    symbol_map: dict[str, str],
    total_pairs: int,
) -> dict[str, Any]:
    """Recompone el peso de la ejecución excluyendo los ciclos artefacto.

    El denominador es el MISMO (``total_pairs`` = 182 emparejados) para que el número sea
    comparable con el ``0,0492 R/ciclo`` publicado: lo que cambia es el numerador.
    """
    measured: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in rows:
        if not row["ledgerFlag"]:
            continue
        symbol = symbol_map.get(str(row["symbol"]), str(row["symbol"]))
        pair = fidelity.get((symbol, str(row["entryDay"])))
        if pair is None:
            missing.append(f"{row['cycleId']}:{symbol}@{row['entryDay']}")
            continue
        sim = finite_number(pair.get("simR"))
        real = finite_number(pair.get("realR"))
        if sim is None or real is None:
            missing.append(f"{row['cycleId']}:R_ilegible")
            continue
        measured.append({**row, "symbolYahoo": symbol, "simR": sim, "realR": real})

    def summarize(subset: list[dict[str, Any]]) -> dict[str, Any]:
        diffs = [r["simR"] - r["realR"] for r in subset]
        total = sum(diffs)
        return {
            "n": len(subset),
            "sumSimMinusRealR": round(total, 6),
            "meanSimMinusRealR": round(total / len(subset), 6) if subset else None,
            "perPairOverAll": round(total / total_pairs, 6) if total_pairs else None,
        }

    by_bucket = {
        bucket: summarize([r for r in measured if r["bucket"] == bucket]) for bucket in BUCKET_ORDER
    }
    real_execution = [r for r in measured if r["bucket"] in EXECUTION_BUCKETS]
    artifacts = [r for r in measured if r["bucket"] in ARTIFACT_BUCKETS]
    all_flagged = summarize(measured)
    return {
        "totalPairs": total_pairs,
        "flagged": len(rows) - sum(1 for r in rows if not r["ledgerFlag"]),
        "matched": len(measured),
        "unmatched": missing,
        "byBucket": by_bucket,
        "realExecution": summarize(real_execution),
        "artifacts": summarize(artifacts),
        "published": all_flagged,
        "publishedReference": {"sumSimMinusRealR": 8.9623, "perPairOverAll": 0.0492},
    }


# ── Autoprueba ──────────────────────────────────────────────────────────────────────
def _seq(*rows: dict[str, Any]) -> list[dict[str, Any]]:
    base = {"currentStop": 100.0, "filledQty": 0.0, "dayFills": 0, "dayOrders": 0,
            "decisionLabel": None, "decisionReasons": [], "maeR": None, "mfeR": None,
            "orderCreated": False, "survived": True}
    return [{**base, **row} for row in rows]


def _fired_no_fill(day: str, mark: float, order: bool | None = True) -> dict[str, Any]:
    return {"day": day, "mark": mark, "filledQty": 0.0, "orderCreated": order,
            "decisionLabel": "structural_stop", "decisionReasons": ["structural_stop"]}


def _filled(day: str, mark: float, order: bool = True) -> dict[str, Any]:
    return {"day": day, "mark": mark, "filledQty": 10.0, "orderCreated": order,
            "decisionLabel": "structural_stop",
            "decisionReasons": ["structural_stop", "thesis_invalidation"]}


def _quiet(day: str, mark: float) -> dict[str, Any]:
    return {"day": day, "mark": mark}


def run_selftest() -> int:
    ok = True

    def check(label: str, got: Any, want: Any) -> None:
        nonlocal ok
        if got != want:
            ok = False
            print(f"[selftest] FALLO · {label}: {got!r} != {want!r}")

    # 1. Barra ausente que cruza el stop: no es un toque.
    pure = classify_cycle(
        {
            "cycleId": "A", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "sequence": _seq(_quiet("2022-01-04", 0.0), _quiet("2022-01-05", 101.0)),
        }
    )
    check("artefacto puro", pure["bucket"], BUCKET_PURE_ARTIFACT)
    check("artefacto puro · toques reales", pure["realTouchDays"], 0)
    check("artefacto puro · toques artefacto", pure["artifactTouchDays"], 1)

    # 2. Disparo en barra ausente + disparo real sin fill + fill al tick siguiente:
    #    la posición sobrevive al toque y llena tarde (el caso de los 24).
    filled = classify_cycle(
        {
            "cycleId": "B", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "sequence": _seq(
                {"day": "2022-01-04", "mark": 0.0, "decisionLabel": "structural_stop",
                 "decisionReasons": ["structural_stop"]},
                _fired_no_fill("2022-01-05", 99.0),
                _filled("2022-01-06", 97.0),
            ),
        }
    )
    check("fill posterior", filled["bucket"], BUCKET_LATE_FILL)
    check("fill posterior · lag", filled["lagTicksToStopFill"], 1)
    check("fill posterior · disparos artefacto", filled["flagArtifactEvents"], 1)
    check("fill posterior · primer toque artefacto", filled["firstTouchIsArtifact"], True)

    # 3. Stop disparado, orden creada, sin fill.
    case_c = classify_cycle(
        {
            "cycleId": "C", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "sequence": _seq(_fired_no_fill("2022-01-04", 99.0)),
        }
    )
    check("orden sin fill", case_c["bucket"], BUCKET_ORDER_NO_FILL)
    check("orden sin fill · toque real", case_c["realTouchDays"], 1)

    # 4. Stop disparado y NINGUNA orden creada (caso A del ledger).
    case_a = classify_cycle(
        {
            "cycleId": "D", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "sequence": _seq(_fired_no_fill("2022-01-04", 99.0, order=False)),
        }
    )
    check("stop sin orden", case_a["bucket"], BUCKET_FIRED_NO_ORDER)

    # 5. Toques reales sin disparo + un disparo en barra ausente: artefacto métrico.
    metric = classify_cycle(
        {
            "cycleId": "E", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": True, "exitMechanism": "THESIS_EXIT",
            "sequence": _seq(
                {"day": "2022-01-04", "mark": 0.0, "decisionLabel": "structural_stop",
                 "decisionReasons": ["structural_stop"]},
                _quiet("2022-01-05", 99.5),
            ),
        }
    )
    check("artefacto métrico", metric["bucket"], BUCKET_METRIC_ARTIFACT)
    check("artefacto métrico · toques reales", metric["realTouchDays"], 1)

    # 6. Sin marca: no se inventa un cubo.
    clean = classify_cycle(
        {
            "cycleId": "F", "symbol": "s", "entryDay": "2022-01-03", "direction": LONG,
            "stopFiredNotFilled": False, "exitMechanism": "TIME_EXIT",
            "sequence": _seq(_quiet("2022-01-04", 105.0)),
        }
    )
    check("sin marca", clean["bucket"], BUCKET_UNFLAGGED)

    # 7. SHORT: un 0.0 no cruza el stop por arriba, así que no hay toque artefacto.
    short = classify_cycle(
        {
            "cycleId": "G", "symbol": "s", "entryDay": "2022-01-03", "direction": SHORT,
            "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "sequence": _seq(_quiet("2022-01-04", 0.0)),
        }
    )
    check("short sin toque", short["realTouchDays"], 0)
    check("short sin toque artefacto", short["artifactTouchDays"], 0)

    # 8. Journal: una entrada por ciclo MARCADO, con la secuencia y el pairStatus.
    j_cycles = [
        {
            "cycleId": "H", "symbol": "s1", "entryDay": "2022-01-03", "exitDay": "2022-01-06",
            "direction": LONG, "stopFiredNotFilled": True, "exitMechanism": "STOP_EJECUTADO",
            "strategyVersion": "v283", "sequence": _seq(_fired_no_fill("2022-01-04", 99.0)),
        },
        {
            "cycleId": "I", "symbol": "s2", "entryDay": "2022-02-01", "exitDay": "2022-02-10",
            "direction": LONG, "stopFiredNotFilled": False, "exitMechanism": "TIME_EXIT",
            "sequence": _seq(_quiet("2022-02-02", 105.0)),
        },
    ]
    journal = build_journal(audit(j_cycles), j_cycles, {}, {})
    check("journal · solo marcados", len(journal), 1)
    check("journal · secuencia intacta", len(journal[0]["sequence"]), 1)
    check("journal · dias del disparo", journal[0]["firedDays"], ["2022-01-04"])
    check("journal · sin pareja se declara", journal[0]["pairStatus"], "unmatched")
    check(
        "journal · campos del tick",
        sorted(journal[0]["sequence"][0]),
        sorted(JOURNAL_SEQUENCE_FIELDS),
    )

    print("[selftest] " + ("OK" if ok else "FALLÓ"))
    return 0 if ok else 1


# ── Presentación ────────────────────────────────────────────────────────────────────
def print_table(rows: list[dict[str, Any]], symbol_map: dict[str, str]) -> None:
    flagged = [r for r in rows if r["ledgerFlag"]]
    print(f"\nciclos totales {len(rows)} · con marca {len(flagged)}")
    print("\nReparto por cubo (mutuamente excluyente):")
    counts = {bucket: 0 for bucket in BUCKET_ORDER}
    for row in flagged:
        counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
    for bucket in BUCKET_ORDER:
        print(f"  {bucket:28s} {counts.get(bucket, 0):3d}")

    print("\nDetalle por ciclo:")
    header = (
        f"  {'symbol':10s} {'entryDay':10s} {'cubo':24s} {'real':>4s} {'artf':>4s} "
        f"{'evR':>3s} {'evA':>3s} {'orden':>5s} {'lag':>4s} {'exit':15s} {'realR':>7s}"
    )
    print(header)
    for row in sorted(flagged, key=lambda r: (str(r["entryDay"]), str(r["cycleId"]))):
        symbol = symbol_map.get(str(row["symbol"]), str(row["symbol"]))[:10]
        order = (
            "si"
            if row["bucket"] == BUCKET_ORDER_NO_FILL
            else ("no" if row["bucket"] == BUCKET_FIRED_NO_ORDER else "-")
        )
        realized = row["realizedR"]
        print(
            f"  {symbol:10s} {str(row['entryDay']):10s} {row['bucket']:24s} "
            f"{row['realTouchDays']:4d} {row['artifactTouchDays']:4d} "
            f"{row['flagRealEvents']:3d} {row['flagArtifactEvents']:3d} {order:>5s} "
            f"{str(row['lagTicksToStopFill'] if row['lagTicksToStopFill'] is not None else '-'):>4s} "
            f"{row['exitMechanism'][:15]:15s} "
            f"{(f'{realized:+.3f}' if realized is not None else '-'):>7s}"
        )


def load_symbol_map_if_possible(database_url: str | None, ids: set[str]) -> dict[str, str]:
    """``instruments.id -> yahoo_symbol`` reutilizando el exportador (misma clave que el CSV)."""
    if not ids:
        return {}
    try:
        import importlib.util

        path = Path(__file__).with_name("export_auto_entries.py")
        spec = importlib.util.spec_from_file_location("export_auto_entries", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"no se pudo cargar {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        url = module._database_url(database_url)  # noqa: SLF001 — reutilización deliberada
        return module.load_symbol_map(url, ids)
    except Exception as error:  # noqa: BLE001 — sin base se sigue, solo se pierde el ticker
        print(f"[aviso] sin mapa id->ticker ({error}); se imprime el id del instrumento")
        return {}


# ── CLI ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--ledger",
        default="operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json",
        help="ledger de ciclos (v2_93 --cycles-out)",
    )
    ap.add_argument(
        "--fidelity",
        default="operability_runs/dia-d-auto/fidelidad_calibrado.csv",
        help="cruce ciclo a ciclo sim/real (random_entry_control --fidelity-out)",
    )
    ap.add_argument(
        "--json-out",
        default="operability_runs/dia-d-auto/stop_fired_not_filled_audit.json",
        help="JSON con el reparto y la componente de ejecución corregida",
    )
    ap.add_argument(
        "--journal-out",
        default="operability_runs/dia-d-auto/stop_fired_not_filled_journal_2026-11-09.json",
        help="journal por ciclo con la secuencia dia a dia (JSON)",
    )
    ap.add_argument(
        "--journal-csv",
        default="operability_runs/dia-d-auto/stop_fired_not_filled_journal_2026-11-09.csv",
        help="una fila por ciclo marcado, con la secuencia compacta (CSV)",
    )
    ap.add_argument("--database-url", default=None, help="por defecto DATABASE_URL o .env")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return run_selftest()

    ledger_path = Path(a.ledger)
    if not ledger_path.is_absolute():
        ledger_path = ROOT / ledger_path
    if not ledger_path.exists():
        print(f"# BLOQUEO: no existe el ledger {ledger_path}", file=sys.stderr)
        return 2
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    cycles = payload.get("cycles")
    if not isinstance(cycles, list):
        print(f"# BLOQUEO: {ledger_path} no trae 'cycles'", file=sys.stderr)
        return 2

    rows = audit(cycles)
    ids = {str(r["symbol"]) for r in rows if r["ledgerFlag"] and r["symbol"]}
    symbol_map = load_symbol_map_if_possible(a.database_url, ids)

    fidelity_path = Path(a.fidelity)
    if not fidelity_path.is_absolute():
        fidelity_path = ROOT / fidelity_path
    fidelity = load_fidelity(fidelity_path)
    total_pairs = len(fidelity) or 182

    component = execution_component(rows, fidelity, symbol_map, total_pairs)
    artifacts = artifact_metrics(cycles)
    journal = build_journal(rows, cycles, fidelity, symbol_map)

    print_table(rows, symbol_map)

    print("\nComponente de ejecución sobre el residuo sim−real:")
    for label, block in (
        ("publicado (todos los marcados)", component["published"]),
        ("artefactos (barra ausente)", component["artifacts"]),
        ("ejecución real (orden/stop sin fill)", component["realExecution"]),
    ):
        if block.get("n"):
            print(
                f"  {label:40s} n={block['n']:3d} · suma {block['sumSimMinusRealR']:+.4f} R · "
                f"media {block['meanSimMinusRealR']:+.4f} R · "
                f"sobre {total_pairs} = {block['perPairOverAll']:+.4f} R/ciclo"
            )
    print(
        f"  referencia publicada: suma {component['publishedReference']['sumSimMinusRealR']:+.4f} R · "
        f"sobre {total_pairs} = {component['publishedReference']['perPairOverAll']:+.4f} R/ciclo"
    )
    if component["unmatched"]:
        print(f"  sin pareja en la fidelidad: {len(component['unmatched'])} "
              f"({', '.join(component['unmatched'][:5])}{'…' if len(component['unmatched']) > 5 else ''})")
    print("  desglose por cubo:")
    for bucket in BUCKET_ORDER:
        block = component["byBucket"].get(bucket) or {}
        if block.get("n"):
            print(
                f"    {bucket:26s} n={block['n']:3d} · suma {block['sumSimMinusRealR']:+.4f} R · "
                f"media {block['meanSimMinusRealR']:+.4f} R · "
                f"{block['perPairOverAll']:+.4f} R/ciclo"
            )

    print("\nContaminación de MÉTRICA por marca ausente (mark <= 0), sobre los 192 ciclos:")
    print(
        f"  filas con marca ausente {artifacts['missingMarkRows']} · "
        f"ciclos afectados {artifacts['cyclesWithMissingMark']} · "
        f"ciclos con stopTouchDays inflado {artifacts['cyclesWithInflatedTouchDays']}"
    )
    print(
        f"  stopTouchDays publicado {artifacts['stopTouchDaysDeclared']} · "
        f"real {artifacts['stopTouchDaysReal']}"
    )

    unprotected = [r for r in rows if r["unprotectedUntilThesis"]]
    print(f"\nciclos con el stop real disparado y SIN ejecución hasta salir por otra vía: {len(unprotected)}")
    for row in unprotected:
        symbol = symbol_map.get(str(row["symbol"]), str(row["symbol"]))[:10]
        realized = row["realizedR"]
        print(
            f"  {symbol:10s} {row['entryDay']} -> {row['exitDay']} · "
            f"toques {row['touchDays']} · {row['exitMechanism']} · "
            f"realR {(f'{realized:+.3f}' if realized is not None else '-')}"
        )

    out_path = Path(a.json_out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "kind": "STOP_FIRED_NOT_FILLED_AUDIT",
                "readOnly": True,
                "ledger": str(ledger_path),
                "fidelity": str(fidelity_path),
                "totalCycles": len(rows),
                "flagged": sum(1 for r in rows if r["ledgerFlag"]),
                "buckets": {
                    bucket: sum(1 for r in rows if r["ledgerFlag"] and r["bucket"] == bucket)
                    for bucket in BUCKET_ORDER
                },
                "executionComponent": component,
                "artifactMetrics": artifacts,
                "unprotectedUntilThesis": [
                    {k: r[k] for k in ("cycleId", "entryDay", "exitDay", "touchDays", "exitMechanism")}
                    for r in unprotected
                ],
                "cycles": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nJSON: {out_path}")

    journal_path = Path(a.journal_out)
    if not journal_path.is_absolute():
        journal_path = ROOT / journal_path
    journal_csv_path = Path(a.journal_csv)
    if not journal_csv_path.is_absolute():
        journal_csv_path = ROOT / journal_csv_path
    write_journal(journal, journal_path, ledger_path, fidelity_path)
    write_journal_csv(journal, journal_csv_path)
    paired = sum(1 for entry in journal if entry["pairStatus"] == "paired")
    print(
        f"Journal por ciclo: {len(journal)} marcados · {paired} emparejados · "
        f"{len(journal) - paired} sin pareja"
    )
    for bucket in BUCKET_ORDER:
        count = sum(1 for entry in journal if entry["bucket"] == bucket)
        if count:
            print(f"  {bucket:28s} {count:3d}")
    print(f"  JSON: {journal_path}")
    print(f"  CSV:  {journal_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
