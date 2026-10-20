"""Evidencia funcional AUTO por valor de ESTUDIO — lector durable de la cadena de 9 etapas.

Qué cierra
----------
El monitor canónico (``auto_operational_monitor``) **ya** sabe leer las NUEVE etapas
(``SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT →
CYCLE_CLOSED``) desde los hechos durables. Pero el **artefacto** DÍA-D (``v2_89``) y la
evidencia por valor solo proyectaban **cuatro** de esas etapas en el lado EJECUTADO
(``RESERVATION``/``FILL``/``PROTECTION``/``CYCLE_CLOSED``) y declaraban ``SIGNAL``/``TOP_N``/
``RISK``/``ORDER``/``SETTLEMENT`` como huecos.

Este módulo es el **lector ÚNICO** que proyecta la cadena COMPLETA por ciclo sobre
``read_operational_monitor`` (sin reimplementar el motor ni un segundo FIFO de P&L) y la
compone **por valor de ESTUDIO**, contrastando la estrategia **EJECUTADA** (identidad que el
ciclo sella: ``strategyPresetKey``/``strategyVersion``) con la **MEJOR PUNTUADA** del selector
cross-asset (foto durable ``top3_opportunities``).

Reglas duras (idénticas a la casa)
----------------------------------
* Un paso SIN traza durable se declara ``None`` (hueco); **jamás** un ``0`` (un ``0`` sería
  una medición: "no pasó nada", que no es lo mismo que "no lo sé").
* La identidad de la estrategia EJECUTADA se LEE del hecho durable del ciclo; nunca se
  infiere del ranking. Sin identidad declarada se viaja ``None`` (la UI dice «Sin dato»).
* Read-only: solo ``SELECT``. No escribe en la BD ni sintetiza pasos.

Camino obligatorio: ``DOMAIN EVENT → PERSISTED OPERATIONAL STATE → CANONICAL DTO → UI``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_application.auto_operational_monitor import (
    OPERATIONAL_STEPS,
    STEP_ABSENT,
    STEP_PENDING,
    STEP_REACHED,
    STEP_UNKNOWN,
    read_operational_monitor,
)
from bolsa_application.dia_d_cycle_verification import (
    DiaDCycleFacts,
    build_dia_d_cycle_verification_draft,
)

#: Resolutores canónicos del informe por valor de ESTUDIO (fuente única): se reutilizan tal cual
#: para no re-derivar ni la clave canónica del ciclo ni la identidad única/AMBIGUA del valor.
#: Se importan por su nombre de módulo (privados de ``estudio_audit``) porque el plan de la
#: evidencia exige REUTILIZAR ese resolutor, no duplicarlo.
from bolsa_application.estudio_audit import (
    _cycles_for_symbol,
    _strategy_for_symbol,
)

__all__ = [
    "CANONICAL_STEPS",
    "STEP_ABSENT",
    "STEP_PENDING",
    "STEP_REACHED",
    "STEP_UNKNOWN",
    "best_scored_asset",
    "build_chain_evidence_artifact",
    "chain_gaps",
    "dia_d_link",
    "executed_identity",
    "executed_rank",
    "executed_vs_dia_d",
    "pnl_reconciliation",
    "read_dia_d_verifications",
    "read_estudio_chain_evidence",
    "read_top3_snapshot",
    "resolve_dia_d_cycle_facts",
    "resolve_executed_vs_best",
    "value_strategy",
]

#: Cadena canónica (misma tupla que el monitor: fuente única, no se duplica).
CANONICAL_STEPS: tuple[str, ...] = OPERATIONAL_STEPS

#: Claves de hecho del paso ``TOP_N`` que declaran el puesto y el score del ciclo.
_RANK_KEY = "rank"
_SCORE_KEY = "score"

#: Quantum del DINERO (``NUMERIC(18, 6)`` en el ledger): la conciliación de P&L se exige
#: EXACTA al quantum representable del dinero, no a la aritmética interna de mayor precisión.
_MONEY = Decimal("0.000001")


def _steps_index(cycle: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(cycle, Mapping):
        return {}
    return {
        str(step.get("id")): step
        for step in (cycle.get("steps") or [])
        if isinstance(step, Mapping) and step.get("id")
    }


def _fact_value(step: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(step, Mapping):
        return None
    for fact in step.get("facts") or []:
        if isinstance(fact, Mapping) and str(fact.get("key")) == key:
            return fact.get("value")
    return None


def _step_state(step: Mapping[str, Any] | None) -> str:
    if not isinstance(step, Mapping):
        return STEP_UNKNOWN
    state = step.get("state")
    return str(state) if state else STEP_UNKNOWN


def project_cycle_steps(cycle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Proyección por paso de la cadena: ``1`` si el hecho durable lo enciende, ``None`` si no.

    Es la reducción COMPARABLE y honesta del lado EJECUTADO: ``1`` = hay hecho durable que
    sostiene la etapa; ``None`` = hueco declarado. Nunca ``0`` (que afirmaría "no ocurrió" sin
    evidencia). El estado crudo (``reached``/``unknown``/``absent``/``pending``) y la nota se
    exponen aparte en ``detail`` para no perder información.
    """
    index = _steps_index(cycle)
    return {
        step: (1 if _step_state(index.get(step)) == STEP_REACHED else None)
        for step in CANONICAL_STEPS
    }


def chain_gaps(cycle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Etapas encendidas y no encendidas (con su estado) del ciclo. Sin ``unknown`` silencioso."""
    index = _steps_index(cycle)
    reached: list[str] = []
    not_reached: dict[str, str] = {}
    for step in CANONICAL_STEPS:
        state = _step_state(index.get(step))
        if state == STEP_REACHED:
            reached.append(step)
        else:
            not_reached[step] = state
    return {
        "reached": reached,
        "notReached": not_reached,
        "complete": not not_reached,
        "steps": len(CANONICAL_STEPS),
    }


def _positive_int(value: Any) -> int | None:
    """Entero ``> 0`` de un valor cuantificable; ``None`` si no lo es (nunca ``0``)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _identity_measurement(*, preset_measured: bool, version_measured: bool) -> MeasurementStatus:
    """Estado de medición de la IDENTIDAD ESTRATÉGICA (preset + versión) en tri-estado.

    ``COMPLETE`` = se pudieron contrastar **los dos** términos de la identidad; ``PARTIAL`` =
    solo uno; ``UNKNOWN`` = ninguno. La distinción no es cosmética: ``COMPLETE`` se lee como
    «la identidad está medida», y declararlo con medio término afirmaría una cobertura que no
    existe. Un valor ausente **nunca** se convierte en ``False`` ni en coincidencia; el hueco
    se declara.
    """
    if preset_measured and version_measured:
        return MEASUREMENT_COMPLETE
    if preset_measured or version_measured:
        return MEASUREMENT_PARTIAL
    return MEASUREMENT_UNKNOWN


def executed_rank(cycle: Mapping[str, Any] | None) -> int | None:
    """Puesto de la estrategia EJECUTADA en el ranking del valor, o ``None`` (hueco).

    Se lee del hecho durable ``TOP_N`` del ciclo (``payload.rank``). Sin él la ausencia se
    declara; nunca se asume ``1``.
    """
    index = _steps_index(cycle)
    return _positive_int(_fact_value(index.get("TOP_N"), _RANK_KEY))


def executed_identity(cycle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Identidad de la estrategia EJECUTADA sellada por el ciclo (o huecos declarados).

    ``source`` distingue de dónde salió cada campo para que el auditor sepa que NO es una
    inferencia del ranking: la identidad exacta (``strategyPresetKey``) y el sello opaco
    (``strategyVersion``) vienen del hecho durable del ciclo.
    """
    if not isinstance(cycle, Mapping):
        return {
            "strategyPresetKey": None,
            "strategyVersion": None,
            "rank": None,
            "score": None,
            "measurement": MEASUREMENT_UNKNOWN,
        }
    preset = cycle.get("strategyPresetKey")
    version = cycle.get("strategyVersion")
    preset_text = str(preset).strip() if preset is not None else ""
    version_text = str(version).strip() if version is not None else ""
    rank = executed_rank(cycle)
    score = _fact_value(_steps_index(cycle).get("TOP_N"), _SCORE_KEY)
    # La identidad se mide sobre lo DECLARADO (preset/versión). El puesto es un hecho
    # SEPARADO: medirlo no completa la identidad, pero sí la deja en ``PARTIAL`` porque el
    # bloque publica algo medido y algo no medido. ``COMPLETE`` exige los dos términos.
    measurement = _identity_measurement(
        preset_measured=bool(preset_text),
        version_measured=bool(version_text),
    )
    if measurement == MEASUREMENT_UNKNOWN and rank is not None:
        measurement = MEASUREMENT_PARTIAL
    return {
        "strategyPresetKey": preset_text or None,
        "strategyVersion": version_text or None,
        "rank": rank,
        "score": score,
        "measurement": measurement,
    }


def best_scored_asset(
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Mejor oportunidad PUNTUADA del selector cross-asset (fila de ``rank == 1``), o ``None``.

    Se lee de la foto durable ``top3_opportunities`` (una por barra). Es la referencia de
    "mejor puntuada"; **no** es la ejecutada (esa la declara el ciclo). ``None`` si el snapshot
    no trae la fila de rank 1: la ausencia se declara, no se inventa.
    """
    if not isinstance(snapshot, Mapping):
        return None
    rows = snapshot.get("rows")
    if not isinstance(rows, Sequence):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _positive_int(row.get("rank")) == 1:
            return dict(row)
    return None


def resolve_executed_vs_best(
    *,
    executed: Mapping[str, Any] | None,
    best_scored: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Veredicto ``executed vs best scored`` con la doctrina ``UNKNOWN ≠ 0``.

    Distingue dos ángulos que el usuario no debe confundir:

    * ``executedIsTopRanked`` — la estrategia EJECUTADA del ciclo era la de **mejor puesto del
      ranking del valor** (``rank == 1`` en el hecho durable). ``True``/``False``/``None`` (sin
      ``rank`` declarado no se puede afirmar).
    * ``executedIsBestScoredAsset`` — el instrumento del ciclo es el **activo mejor puntuado**
      del selector cross-asset (``top3_opportunities`` rank 1). ``True``/``False``/``None`` (sin
      foto durable, hueco).

    Nunca se afirma ``False`` sin término de comparación (mismo criterio que el emparejamiento
    exacto de ``auto-operation-strategy.ts``): un hueco es ``None``/"no se puede emparejar".
    """
    executed_map = executed if isinstance(executed, Mapping) else {}
    rank = executed_map.get("rank")
    executed_is_top_ranked: bool | None
    if isinstance(rank, int) and rank > 0:
        executed_is_top_ranked = rank == 1
    else:
        executed_is_top_ranked = None

    instrument_id = executed_map.get("instrumentId")
    instrument_text = str(instrument_id).strip() if instrument_id is not None else ""
    best_asset = best_scored.get("assetId") if isinstance(best_scored, Mapping) else None
    best_text = str(best_asset).strip() if best_asset is not None else ""
    if instrument_text and best_text:
        executed_is_best_scored_asset: bool | None = instrument_text == best_text
    else:
        executed_is_best_scored_asset = None

    # V2.88.153 — identidad de la estrategia MEJOR PUNTUADA. Desde la migración 057 la foto
    # durable del TOP3 sella el preset/versión del candidato ganador; antes era ``NULL``. El
    # emparejamiento exige AMBOS términos: sin uno, el veredicto es un hueco declarado
    # (``None``), nunca una coincidencia ni una divergencia inventadas.
    best_preset = (
        str(best_scored.get("strategyPresetKey") or "").strip()
        if isinstance(best_scored, Mapping)
        else ""
    )
    best_version = (
        str(best_scored.get("strategyVersion") or "").strip()
        if isinstance(best_scored, Mapping)
        else ""
    )
    executed_preset = str(executed_map.get("strategyPresetKey") or "").strip()
    executed_version = str(executed_map.get("strategyVersion") or "").strip()
    preset_match: bool | None = (
        executed_preset == best_preset if (executed_preset and best_preset) else None
    )
    version_match: bool | None = (
        executed_version == best_version if (executed_version and best_version) else None
    )

    return {
        "executedIsTopRanked": executed_is_top_ranked,
        "executedIsBestScoredAsset": executed_is_best_scored_asset,
        "executedRank": rank if isinstance(rank, int) else None,
        "bestScoredAssetId": best_text or None,
        # La identidad se publica TAL CUAL la declara la foto (o ``None`` si no la declara): no
        # se deduce del ticker ni del rank. Las fotos anteriores a la 057 viajan como hueco.
        "bestScoredPresetKey": best_preset or None,
        "bestScoredStrategyVersion": best_version or None,
        "executedPresetKey": executed_preset or None,
        "executedStrategyVersion": executed_version or None,
        "presetMatch": preset_match,
        "versionMatch": version_match,
        "measurement": (
            MEASUREMENT_COMPLETE
            if (executed_is_top_ranked is not None or executed_is_best_scored_asset is not None)
            else MEASUREMENT_UNKNOWN
        ),
        # Medición de la IDENTIDAD, separada del veredicto rank/activo: un hueco de identidad no
        # degrada una comparación de puesto que sí se pudo hacer, pero tampoco se disfraza.
        # Tri-estado: ``COMPLETE`` solo con preset Y versión contrastados; ``PARTIAL`` con uno;
        # ``UNKNOWN`` con ninguno. Declarar ``COMPLETE`` con medio término afirmaría una
        # identidad completa que no se midió.
        "strategyMeasurement": _identity_measurement(
            preset_measured=preset_match is not None,
            version_measured=version_match is not None,
        ),
    }


def value_strategy(cycles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Identidad EJECUTADA que declara el VALOR, con los resolutores canónicos reutilizados.

    Reutiliza ``estudio_audit._cycles_for_symbol`` (clave canónica ``cycleId``, orden NATURAL y
    deduplicación declarada) y ``estudio_audit._strategy_for_symbol`` (identidad única o
    **AMBIGUA**) — el MISMO resolutor con el que se atribuye el dinero por valor, para que la
    evidencia no derive una segunda verdad. Un valor cuyos ciclos declaran identidades distintas
    NO elige «ganadora»: ``presetKey``/``version`` viajan ``None`` con su bandera de ambigüedad.
    """
    rows, unlinked, duplicates = _cycles_for_symbol(list(cycles))
    return {
        "cycles": rows,
        "unlinkedCycles": unlinked,
        "duplicateCycles": duplicates,
        **_strategy_for_symbol(rows),
    }


def value_strategy_from_dia_d(verifications: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Identidad que declaran las verificaciones DÍA-D del valor (fuente durable INDEPENDIENTE).

    Mismo resolutor canónico (identidad única o ambigua) sobre OTRA fuente durable: sirve de
    contraste independiente de la identidad sellada por los ciclos.
    """
    rows: list[dict[str, Any]] = []
    for verification in verifications:
        if not isinstance(verification, Mapping):
            continue
        rows.append(
            {
                "strategyPresetKey": verification.get("strategyPresetKey"),
                "strategyVersion": verification.get("strategyVersion"),
            }
        )
    return {"verifications": len(rows), **_strategy_for_symbol(rows)}


def executed_vs_dia_d(
    *,
    executed: Mapping[str, Any] | None,
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Coincidencia de identidad entre el ciclo EJECUTADO y su verificación DÍA-D.

    Dos fuentes durables **INDEPENDIENTES**: el hecho de decisión del ciclo
    (``strategyPresetKey``) y la fila ``dia_d_cycle_verifications``. Con la misma clave EXACTA la
    coincidencia es ``True``; con claves distintas es ``False``; sin alguna de las dos no se puede
    afirmar (``None``). Nunca se fabrica un ``False`` a partir de una sola parte.
    """
    executed_map = executed if isinstance(executed, Mapping) else {}
    cycle_preset = executed_map.get("strategyPresetKey")
    cycle_text = str(cycle_preset).strip() if cycle_preset is not None else ""
    dia_d_preset = (
        verification.get("strategyPresetKey") if isinstance(verification, Mapping) else None
    )
    dia_d_text = str(dia_d_preset).strip() if dia_d_preset is not None else ""
    if cycle_text and dia_d_text:
        matches: bool | None = cycle_text == dia_d_text
    else:
        matches = None
    return {
        "matches": matches,
        "cyclePresetKey": cycle_text or None,
        "diaDPresetKey": dia_d_text or None,
        "measurement": MEASUREMENT_COMPLETE if matches is not None else MEASUREMENT_UNKNOWN,
    }


def dia_d_link(
    *,
    cycle: Mapping[str, Any] | None,
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Declara si el ciclo puede ENLAZAR una verificación DÍA-D, reutilizando el builder puro.

    Reutiliza ``build_dia_d_cycle_verification_draft`` (el MISMO helper con el que la app escribe
    el borrador de ``upsert``, sin duplicar sus precondiciones): compone el borrador con los
    hechos durables disponibles y publica ``linkable``. Un borrador incompleto NO se fabrica —
    viaja ``None`` con ``linkable=False`` (``UNKNOWN ≠ 0``) y el ciclo declara el hueco.
    """
    cycle_map = cycle if isinstance(cycle, Mapping) else {}
    verification_map = verification if isinstance(verification, Mapping) else {}
    payload: dict[str, Any] = {
        "cycleId": cycle_map.get("cycleId"),
        "instrumentId": cycle_map.get("instrumentId"),
        "symbol": verification_map.get("symbol"),
        "diaD": verification_map.get("diaD"),
        "endDate": verification_map.get("endDate"),
        "mode": verification_map.get("mode"),
        "strategyPresetKey": verification_map.get("strategyPresetKey")
        or cycle_map.get("strategyPresetKey"),
        "strategyVersion": verification_map.get("strategyVersion")
        or cycle_map.get("strategyVersion"),
        "band": verification_map.get("band"),
        "result": verification_map.get("result"),
    }
    draft = build_dia_d_cycle_verification_draft(payload)
    return {
        "linkable": draft is not None,
        "draft": draft,
        "measurement": MEASUREMENT_COMPLETE if draft is not None else MEASUREMENT_UNKNOWN,
    }


def _decimal_or_none(value: Any) -> Any:
    """``Decimal`` del valor si es cuantificable; ``None`` si no (nunca ``0`` de relleno)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def pnl_reconciliation(cycle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Conciliación de P&L del ciclo: cierre reconstruido (``CYCLE_CLOSED``) vs liquidación.

    El ``CYCLE_CLOSED`` lo reconstruye ``cycles_from_fills`` y el ``SETTLEMENT`` lo declara el
    hecho durable; deben cuadrar al **quantum del dinero** (``NUMERIC(18,6)``). Sin ambas
    cifras la conciliación es un hueco (``None``), nunca un ``True`` optimista.
    """
    index = _steps_index(cycle)
    closed_pnl = _decimal_or_none(_fact_value(index.get("CYCLE_CLOSED"), "pnl"))
    settlement_pnl = _decimal_or_none(_fact_value(index.get("SETTLEMENT"), "pnl"))
    if closed_pnl is None or settlement_pnl is None:
        reconciled: bool | None = None
    else:
        reconciled = closed_pnl.quantize(_MONEY, rounding=ROUND_HALF_UP) == settlement_pnl.quantize(
            _MONEY, rounding=ROUND_HALF_UP
        )
    return {
        "cycleClosedPnl": None if closed_pnl is None else str(closed_pnl),
        "settlementPnl": None if settlement_pnl is None else str(settlement_pnl),
        "reconciled": reconciled,
        "measurement": MEASUREMENT_COMPLETE if reconciled is not None else MEASUREMENT_UNKNOWN,
    }


def _day_of(instant: Any) -> str | None:
    """Día ``YYYY-MM-DD`` de una marca temporal durable; ``None`` si no se puede afirmar."""
    text = str(instant or "").strip()
    if len(text) < 10:
        return None
    day = text[:10]
    try:
        _ = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return None
    return day


def _cycle_day(cycle: Mapping[str, Any] | None, step_id: str) -> str | None:
    """Día del hecho durable de ``step_id`` (``at``); ``None`` si la etapa no lo declara."""
    step = _steps_index(cycle).get(step_id)
    return _day_of(step.get("at")) if isinstance(step, Mapping) else None


def _cycle_view(
    cycle: Mapping[str, Any], *, best_scored: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Fila de evidencia de UN ciclo: identidad + cadena + ejecutada vs mejor puntuada."""
    steps = project_cycle_steps(cycle)
    executed = executed_identity(cycle)
    executed_with_instrument = {
        **executed,
        "instrumentId": cycle.get("instrumentId"),
        "cycleId": cycle.get("cycleId"),
        "opportunityId": cycle.get("opportunityId"),
        "direction": cycle.get("direction"),
    }
    return {
        "cycleId": cycle.get("cycleId"),
        "instrumentId": cycle.get("instrumentId"),
        "direction": cycle.get("direction"),
        "closed": cycle.get("closed"),
        "opportunityId": cycle.get("opportunityId"),
        # Día de ENTRADA durable (``at`` de la reserva) y de cierre (``closedAt`` del
        # resultado). Son hechos: sin ellos la UI no inventa la fecha del DÍA-D del valor.
        "entryDay": _cycle_day(cycle, "RESERVATION"),
        "exitDay": _day_of(
            (cycle.get("result") or {}).get("closedAt")
            if isinstance(cycle.get("result"), Mapping)
            else None
        ),
        "executed": executed,
        "bestScored": dict(best_scored) if isinstance(best_scored, Mapping) else None,
        "executedVsBest": resolve_executed_vs_best(
            executed=executed_with_instrument, best_scored=best_scored
        ),
        "steps": steps,
        "chain": chain_gaps(cycle),
        "pnl": pnl_reconciliation(cycle),
        "diaD": cycle.get("diaD"),
        "executedVsDiaD": executed_vs_dia_d(executed=executed, verification=cycle.get("diaD")),
        "diaDLink": dia_d_link(cycle=cycle, verification=cycle.get("diaD")),
        "result": cycle.get("result"),
        "notes": list(cycle.get("notes") or []),
    }


def build_chain_evidence_artifact(
    *,
    account_id: str,
    estudio: Mapping[str, Any] | None,
    cycles: Sequence[Mapping[str, Any]],
    best_scored: Mapping[str, Any] | None = None,
    as_of: str | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Artefacto canónico de la evidencia de cadena por valor de ESTUDIO (puro y determinista).

    Agrupa los ciclos por valor de ESTUDIO y, por ciclo, publica la cadena de 9 etapas, la
    identidad EJECUTADA y el veredicto contra la mejor puntuada. No rellena ceros: un valor sin
    ciclos declara ``cycles=[]`` y ``complete=False`` con su hueco.
    """
    estudio_ids: list[str] = []
    if isinstance(estudio, Mapping):
        raw_ids = estudio.get("instrumentIds")
        if isinstance(raw_ids, Sequence) and not isinstance(raw_ids, (str, bytes)):
            estudio_ids = [str(i) for i in raw_ids if i]

    by_instrument: dict[str, list[Mapping[str, Any]]] = {}
    for cycle in cycles:
        if not isinstance(cycle, Mapping):
            continue
        key = str(cycle.get("instrumentId") or "").strip()
        by_instrument.setdefault(key, []).append(cycle)

    values: list[dict[str, Any]] = []
    for instrument_id in estudio_ids:
        raw_cycles = by_instrument.get(instrument_id, [])
        cycle_views = [_cycle_view(cycle, best_scored=best_scored) for cycle in raw_cycles]
        complete = bool(cycle_views) and all(view["chain"]["complete"] for view in cycle_views)
        values.append(
            {
                "instrumentId": instrument_id,
                "cycles": cycle_views,
                "measured": bool(cycle_views),
                "complete": complete,
                "unmeasured": [] if cycle_views else ["no_cycles_for_value"],
                # Identidad EJECUTADA que declara el VALOR (resolutor canónico reutilizado sobre
                # los hechos durables de sus ciclos) y contraste INDEPENDIENTE con lo que sellan
                # sus verificaciones DÍA-D.
                "strategy": value_strategy(raw_cycles),
                "strategyDiaD": value_strategy_from_dia_d(
                    [view["diaD"] for view in cycle_views if isinstance(view.get("diaD"), Mapping)]
                ),
            }
        )

    # Ciclos cuyo instrumento NO está en ESTUDIO (universo declarado): no se descartan en
    # silencio; se declaran aparte como ciclos fuera del universo.
    estudio_set = set(estudio_ids)
    outside = [
        _cycle_view(cycle, best_scored=best_scored)
        for instrument_id, raw in by_instrument.items()
        if instrument_id not in estudio_set
        for cycle in raw
    ]

    measured = sum(1 for value in values if value["measured"])
    complete_values = sum(1 for value in values if value["complete"])
    all_cycles = [view for value in values for view in value["cycles"]] + outside
    best_scored_block: dict[str, Any] | None = None
    if isinstance(best_scored, Mapping):
        # V2.88.153 — la foto cross-asset YA sella la identidad del candidato ganador desde la
        # migración 057. Se publica lo que la fila declare; el hueco (``None``) solo significa
        # «la foto no lo declara» (fotos históricas), nunca una identidad inferida.
        best_preset = str(best_scored.get("strategyPresetKey") or "").strip()
        best_version = str(best_scored.get("strategyVersion") or "").strip()
        best_scored_block = {
            **dict(best_scored),
            "bestScoredPresetKey": best_preset or None,
            "bestScoredStrategyVersion": best_version or None,
            # La foto se mide por lo que DECLARA: ``COMPLETE`` exige preset y versión;
            # ``PARTIAL`` una sola; ``UNKNOWN`` ninguna (históricas pre-057). Es la misma
            # regla que ``resolve_executed_vs_best``, no una segunda verdad.
            "strategyMeasurement": _identity_measurement(
                preset_measured=bool(best_preset),
                version_measured=bool(best_version),
            ),
        }
    return {
        "kind": "AUTO_ESTUDIO_CHAIN_EVIDENCE",
        "readOnly": True,
        "schemaVersion": "auto-estudio-chain-v1",
        "accountId": account_id,
        "asOf": as_of or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "estudio": {
            "status": (estudio or {}).get("status") if isinstance(estudio, Mapping) else None,
            "values": len(estudio_ids),
        },
        "summary": {
            "values": len(estudio_ids),
            "measured": measured,
            "complete": complete_values,
            "cycles": len(all_cycles),
            "cyclesComplete": sum(1 for view in all_cycles if view["chain"]["complete"]),
            "bestScoredPresent": best_scored is not None,
        },
        "bestScored": best_scored_block,
        "values": values,
        "cyclesOutsideEstudio": outside,
        "meta": {str(k): v for k, v in (meta or {}).items()},
        "limits": [str(item) for item in (limits or ())],
    }


async def read_top3_snapshot(
    session: Any,
    account_id: str,
) -> dict[str, Any] | None:
    """Lee (read-only) la foto durable MÁS RECIENTE del selector cross-asset del motor.

    Devolve ``{"runId", "rows":[{assetId, rank, combined, components, regime,
    strategyPresetKey, strategyVersion}]}`` o ``None`` si no hay ninguna foto (hueco declarado,
    nunca una lista vacía disfrazada de medición). ``strategyPresetKey``/``strategyVersion``
    (V2.88.153) viajan desde la fila; ``None`` cuando la foto no los declara (históricas).
    """
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import Top3OpportunityRow

    try:
        rows = (
            await session.execute(
                select(
                    Top3OpportunityRow.run_id,
                    Top3OpportunityRow.rank,
                    Top3OpportunityRow.asset_id,
                    Top3OpportunityRow.combined,
                    Top3OpportunityRow.components,
                    Top3OpportunityRow.regime,
                    Top3OpportunityRow.strategy_preset_key,
                    Top3OpportunityRow.strategy_version,
                )
                .where(Top3OpportunityRow.run_id.like(f"top3-{account_id}-%"))
                .order_by(Top3OpportunityRow.run_id.desc(), Top3OpportunityRow.rank.asc())
            )
        ).all()
    except Exception:  # noqa: BLE001 — sin foto el hueco se declara, nunca se finge.
        return None
    if not rows:
        return None
    newest_run = str(rows[0][0])
    run_rows = [row for row in rows if str(row[0]) == newest_run]
    return {
        "runId": newest_run,
        "rows": [
            {
                "assetId": asset_id,
                "rank": rank,
                "combined": combined,
                "components": dict(components or {})
                if isinstance(components, Mapping)
                else components,
                "regime": regime,
                "strategyPresetKey": str(preset).strip() if preset is not None else None,
                "strategyVersion": str(version).strip() if version is not None else None,
            }
            for _run, rank, asset_id, combined, components, regime, preset, version in run_rows
        ],
    }


async def read_dia_d_verifications(
    session: Any,
    account_id: str,
    *,
    cycle_ids: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Lee (read-only) las verificaciones DÍA-D enlazadas a ciclos, indexadas por ``cycleId``.

    Cierra el último eslabón de la cadena (``verificación DÍA D``). Sin verificación para un
    ciclo, ese ciclo simplemente **no aparece** en el mapa: la ausencia se declara (``diaD=None``
    en la evidencia), nunca se finge.
    """
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import DiaDCycleVerificationRow

    stmt = select(
        DiaDCycleVerificationRow.cycle_id,
        DiaDCycleVerificationRow.dia_d,
        DiaDCycleVerificationRow.end_date,
        DiaDCycleVerificationRow.mode,
        DiaDCycleVerificationRow.band,
        DiaDCycleVerificationRow.strategy_preset_key,
        DiaDCycleVerificationRow.strategy_version,
        DiaDCycleVerificationRow.result,
        DiaDCycleVerificationRow.instrument_id,
        DiaDCycleVerificationRow.symbol,
        DiaDCycleVerificationRow.created_at,
    ).where(DiaDCycleVerificationRow.account_id == account_id)
    if cycle_ids:
        stmt = stmt.where(DiaDCycleVerificationRow.cycle_id.in_(list(cycle_ids)))
    try:
        rows = (
            await session.execute(stmt.order_by(DiaDCycleVerificationRow.created_at.asc()))
        ).all()
    except Exception:  # noqa: BLE001 — sin lectura el eslabón se declara ausente.
        return {}
    out: dict[str, dict[str, Any]] = {}
    for (
        cycle_id,
        dia_d,
        end_date,
        mode,
        band,
        preset,
        version,
        result,
        instrument_id,
        symbol,
        _created,
    ) in rows:
        key = str(cycle_id).strip() if cycle_id is not None else ""
        if not key:
            continue
        # La ÚLTIMA verificación del ciclo manda (se sobrescribe en orden ascendente de fecha).
        out[key] = {
            "diaD": dia_d,
            "endDate": end_date,
            "mode": mode,
            "band": band,
            "strategyPresetKey": preset,
            "strategyVersion": version,
            "instrumentId": instrument_id,
            "symbol": symbol,
            "result": dict(result) if isinstance(result, Mapping) else result,
        }
    return out


def canonical_instrument_identity(
    raw_instrument_id: Any,
    catalog_row: Sequence[Any] | None,
) -> tuple[str | None, str | None]:
    """Canoniza la identidad del instrumento a la del **catálogo** (``(id, symbol)``).

    El motor identifica el instrumento por su ``id``, pero los entornos de **siembra/legacy**
    (p. ej. el seed del harness E2E) pueden usar el propio **SÍMBOLO** como ``instrument_id``.
    Cuando el catálogo conoce el instrumento —por ``id`` **o** por ``symbol``— la identidad
    persistida se canoniza a su **id de catálogo**: la MISMA que usa el resto del producto
    (``/instruments/<id>/…``) y la que el navegador declara como contraste en el DTO DÍA-D.

    Sin fila de catálogo se conserva el valor **CRUDO** y el símbolo es un **hueco declarado**:
    nunca se inventa una identidad (doctrina ``UNKNOWN ≠ 0``).

    Falsable: ``canonical_instrument_identity("ACS", ("uuid-1", "ACS")) == ("uuid-1", "ACS")``;
    ``canonical_instrument_identity("ACS", None) == ("ACS", None)``.
    """
    raw = str(raw_instrument_id or "").strip() or None
    if catalog_row is None:
        return raw, None
    catalog_id = str(catalog_row[0] or "").strip() or None
    raw_symbol = catalog_row[1]
    symbol = str(raw_symbol).strip() if raw_symbol else None
    return catalog_id or raw, symbol


async def resolve_dia_d_cycle_facts(
    session: Any,
    account_id: str,
    *,
    cycle_id: str,
) -> DiaDCycleFacts | None:
    """Identidad DURABLE del ciclo AUTO para anclar la verificación DÍA-D (``None`` si no existe).

    Resuelve, ACOTADO POR CUENTA, el instrumento (de la reserva de entrada del ciclo), su
    símbolo (del catálogo) y la identidad EXACTA de la estrategia ejecutada que sella el ciclo
    (``strategyPresetKey``/``strategyVersion``, leída del hecho durable, NUNCA del navegador).
    La identidad del instrumento se **canoniza** al id del catálogo cuando el catálogo lo conoce
    (siembra/legacy pueden usar el símbolo como id); sin fila se conserva el valor crudo.
    Un ``cycleId`` sin reserva durable en esa cuenta ⇒ ``None`` (el llamante declara ``404``).
    """
    import sqlalchemy as sa

    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    key = str(cycle_id or "").strip()
    if not key or not account_id:
        return None
    reservations = await PostgresReservationStore(
        session, autocommit=False
    ).list_by_cycle_ids(account_id, [key], limit=1)
    if not reservations:
        return None

    raw_instrument_id = str(reservations[0].instrument_id or "").strip() or None
    catalog_row: Sequence[Any] | None = None
    if raw_instrument_id:
        try:
            # El motor identifica el instrumento por su id, pero los entornos de siembra/legacy
            # pueden usar el propio símbolo como id: se aceptan las DOS costuras y, con fila de
            # catálogo, la identidad se canoniza a su id (nunca se inventa: sin fila se conserva
            # el valor crudo y el símbolo es un hueco declarado).
            catalog_row = (
                await session.execute(
                    sa.select(InstrumentRow.id, InstrumentRow.symbol)
                    .where(
                        sa.or_(
                            InstrumentRow.id == raw_instrument_id,
                            InstrumentRow.symbol == raw_instrument_id,
                        )
                    )
                    .limit(1)
                )
            ).first()
        except Exception:  # noqa: BLE001 — catálogo ilegible: crudo + huecos declarados.
            catalog_row = None
    instrument_id, symbol = canonical_instrument_identity(raw_instrument_id, catalog_row)

    monitor = await read_operational_monitor(session, account_id, cycle_id=key, limit=1)
    cycle = next(
        (
            row
            for row in (monitor.get("cycles") or [])
            if str(row.get("cycleId")) == key
        ),
        None,
    )
    cycle_map = cycle if isinstance(cycle, Mapping) else {}
    preset = cycle_map.get("strategyPresetKey")
    version = cycle_map.get("strategyVersion")
    return DiaDCycleFacts(
        cycle_id=key,
        instrument_id=instrument_id,
        symbol=symbol,
        strategy_preset_key=str(preset).strip() if preset is not None and str(preset).strip() else None,
        strategy_version=str(version).strip() if version is not None and str(version).strip() else None,
    )


async def read_estudio_chain_evidence(
    session: Any,
    account_id: str,
    *,
    engine_id: str = "auto-sim",
    limit: int = 100,
    cycle_id: str | None = None,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    """Lee la cadena durable completa por ciclo y la foto del selector (para ejecutada vs mejor).

    Reutiliza ``read_operational_monitor`` como fuente ÚNICA de los hechos durables (no hay un
    segundo lector ni un segundo FIFO de P&L) y añade la foto ``top3_opportunities`` para
    contrastar con la mejor puntuada. Anota, además, la verificación DÍA-D de cada ciclo (el
    último eslabón). ``session`` es una ``AsyncSession`` de SQLAlchemy.
    """
    monitor = await read_operational_monitor(
        session,
        account_id,
        engine_id=engine_id,
        limit=limit,
        cycle_id=cycle_id,
        instrument_id=instrument_id,
    )
    snapshot = None if cycle_id else await read_top3_snapshot(session, account_id)

    raw_cycles = monitor.get("cycles") or []
    cycle_ids = [str(c.get("cycleId")) for c in raw_cycles if c.get("cycleId")]
    dia_d_by_cycle = await read_dia_d_verifications(
        session, account_id, cycle_ids=cycle_ids or None
    )
    cycles: list[dict[str, Any]] = []
    for cycle in raw_cycles:
        if not isinstance(cycle, Mapping):
            continue
        enriched = dict(cycle)
        enriched["diaD"] = dia_d_by_cycle.get(str(cycle.get("cycleId")))
        cycles.append(enriched)
    return {
        "monitor": monitor,
        "cycles": cycles,
        "bestScored": best_scored_asset(snapshot),
        "top3": snapshot,
        "diaDByCycle": dia_d_by_cycle,
    }


async def day_durable_chain_counts(
    session: Any,
    account_id: str,
    day: str,
) -> dict[str, int | None]:
    """Cuenta los hechos durables de la cadena para el día ``day`` (``[00:00, +24h)`` UTC).

    Devuelve un entero por etapa contable (``SIGNAL``/``TOP_N``/``RISK``/``ORDER``/``SETTLEMENT``)
    —compatible con el lado DECLARADO del artefacto DÍA-D, que también son cuentas— o ``None``
    si la lectura de la fuente falla (hueco declarado, nunca un ``0`` fabricado). Se usa para
    cerrar los huecos que ``v2_89`` declaraba en el lado EJECUTADO.
    """
    from sqlalchemy import func, select

    from bolsa_infrastructure.database.models.tables import (
        DecisionJournalEntryRow,
        PortfolioReservationRow,
        Top3OpportunityRow,
    )

    start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    end = start + timedelta(days=1)

    async def _count_event(event_type: str) -> int | None:
        try:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(DecisionJournalEntryRow)
                    .where(
                        DecisionJournalEntryRow.account_id == account_id,
                        DecisionJournalEntryRow.event_type == event_type,
                        DecisionJournalEntryRow.created_at >= start,
                        DecisionJournalEntryRow.created_at < end,
                    )
                )
                or 0
            )
        except Exception:  # noqa: BLE001 — fuente ilegible: hueco declarado.
            return None

    async def _count_top3() -> int | None:
        try:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(Top3OpportunityRow)
                    .where(
                        Top3OpportunityRow.run_id.like(f"top3-{account_id}-%"),
                        Top3OpportunityRow.created_at >= start,
                        Top3OpportunityRow.created_at < end,
                    )
                )
                or 0
            )
        except Exception:  # noqa: BLE001 — fuente ilegible: hueco declarado.
            return None

    async def _count_risked_reservations() -> int | None:
        try:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(PortfolioReservationRow)
                    .where(
                        PortfolioReservationRow.account_id == account_id,
                        PortfolioReservationRow.created_at >= start,
                        PortfolioReservationRow.created_at < end,
                        PortfolioReservationRow.reserved_risk.is_not(None),
                    )
                )
                or 0
            )
        except Exception:  # noqa: BLE001 — fuente ilegible: hueco declarado.
            return None

    return {
        "SIGNAL": await _count_event("auto_entry_decision"),
        "TOP_N": await _count_top3(),
        "RISK": await _count_risked_reservations(),
        "ORDER": await _count_event("auto_entry_order"),
        "SETTLEMENT": await _count_event("auto_cycle_settlement"),
    }
