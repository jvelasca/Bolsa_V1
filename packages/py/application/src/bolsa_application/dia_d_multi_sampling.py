"""V2.88.43 · DÍA-D AUTO — DE LA BANDA DEL VENUE A LA BANDA TOTAL: bootstrap de CICLOS (puro).

Qué es
------
La banda del sorteo del venue (``dia_d_multi_uncertainty``, ``dia-d-multi-band-v1``) mide
cuánto mueve el resultado la realización del venue simulador: ``K`` corridas del MISMO harness
con el ancla temporal del ``fill_seed`` desplazada. Faltaba la OTRA mitad de la incertidumbre
del instrumento: cuánto puede variar el resultado según **qué operaciones entran en la muestra**
(el muestreo de ciclos). Este módulo añade esa mitad con un **bootstrap no paramétrico** sobre
los ciclos observados y compone ambas en la **banda TOTAL**.

Ejes declarados (no son lo mismo)
---------------------------------
* **venue** — ``Var_k`` entre los ``K`` re-sorteos del venue (mismo dato, misma estrategia).
* **sampling** — bootstrap de la muestra de ciclos DENTRO de cada sorteo (con reemplazo, ``n``
  fijo), promediado sobre los sorteos.
* **total** — ley de la varianza total: ``totalVar = venueVar + samplingVar`` (los dos ejes se
  tratan como ortogonales; la interacción real se aproxima por el pool ``K × B``).

De dónde salen los ciclos
-------------------------
El artefacto ``dia-d-multi-v1`` **no** conserva los ciclos individuales (sólo agregados +
``concentration`` top-k). Esta capa consume un **ledger de ciclos** por sorteo
(``dia-d-multi-cycle-ledger-v1``), que ``v2_93``/``v2_94`` pueden persistir reutilizando las
``K`` pasadas que ya ejecutan (coste extra de harness ``= 0``).

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* Un cubo que no aparece en un sorteo baja ``drawsWithCell`` (no se inventa un valor).
* La capa es **advisory y read-only**: no cambia el motor, los umbrales, ``TOP_N`` ni la
  allocation; es un **observador** del mismo instrumento.
* El artefacto es **determinista** (semilla declarada + PRNG propio, sin reloj ni azar global):
  mismas ``K`` semillas y mismo ``B`` ⇒ payload byte a byte idéntico.
* La banda se cita **entera o no se cita**; la unidad de remuestreo es el **ciclo**.
* ``K`` sorteos **no** son ``K`` muestras independientes de mercado: son ``K`` realizaciones del
  mismo experimento histórico con distinto sorteo del venue.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.applied_cost import applied_cost_from_fills
from bolsa_application.dia_d_attribution import (
    SIN_REGIMEN,
    cycle_key,
    index_excursions,
    regime_key_reader,
)
from bolsa_application.dia_d_auto import finite_number, normalize_day
from bolsa_application.dia_d_exit_mechanism import (
    EXIT_MECHANISM_SIN_MECANISMO,
    classify_exit_mechanism,
)
from bolsa_application.dia_d_longitudinal import (
    DEFAULT_ENTRY_WINDOW_DAYS,
    LONG,
    SHORT,
    Excursion,
    infer_direction,
)
from bolsa_application.dia_d_multi import (
    SIN_OPERATIONAL,
    SIN_YEAR,
    operational_regime_key_reader,
    year_key_reader,
)
from bolsa_application.dia_d_multi_uncertainty import (
    CI95_Z,
    DIM_GLOBAL,
    DIM_OPERATIONAL,
    DIM_REGIME,
    DIM_YEAR,
    DIM_YEAR_REGIME,
    MIN_DRAWS_FOR_BAND,
)

#: Versión del esquema del ledger de ciclos (una fila por ciclo; sin agregados).
#: v2 (V2.88.44) añade —de forma ADITIVA— el mecanismo de salida, la fricción aplicada en R, el
#: R neto y la excursión adversa TEMPRANA post-entrada. Un lector de v1 ignora los campos nuevos.
#: v3 (V2.88.45) añade —también ADITIVA— la identidad de la ESTRATEGIA (``strategyVersion``) y la
#: DIRECCIÓN inferida (``direction``) del ciclo, que el diagnóstico quirúrgico necesita para saber
#: *dónde* vive cada cierre. Un lector de v1/v2 ignora los campos nuevos.
#: v4 (V2.88.46) añade —ADITIVA— la GEOMETRÍA de la INVALIDACIÓN DE LA TESIS (``invalidationPrice``,
#: ``currentStopAtExit``, ``initialStop`` y sus distancias en R, más los booleanos
#: ``levelEqualsInitialStop``/``maeReachedLevel`` y el token ``thesisExitCondition``). Responde a
#: *qué condición* disparó un ``THESIS_EXIT``, sin tocar el motor (el nivel se lee del estado de la
#: posición congelado al nacer y de la excursión ya medida). Un lector de v1/v2/v3 ignora lo nuevo.
LEDGER_SCHEMA_VERSION = "dia-d-multi-cycle-ledger-v4"

#: Tipo del ledger de ciclos (la muestra cruda de UN sorteo).
LEDGER_KIND = "DIA_D_AUTO_MULTI_CYCLE_LEDGER"

#: Versión del esquema del artefacto de muestreo/total. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-multi-sampling-v1"

#: Tipo del artefacto (la banda de muestreo y la total).
KIND = "DIA_D_AUTO_MULTI_SAMPLING"

#: Remuestreos del bootstrap por defecto (``B``). Declarado: con otro ``B`` la banda cambia.
DEFAULT_RESAMPLES = 2000

#: Semilla declarada del bootstrap (fija; viaja en el artefacto).
DEFAULT_SEED = 20261003

#: Ciclos mínimos por sorteo para que el bootstrap de una celda no sea anecdótico.
MIN_CYCLES_FOR_SAMPLING = 5

#: Métricas remuestreadas (todas publicadas con su banda total, o ``None`` sin muestra).
METRICS: tuple[str, ...] = ("expectancyR", "realizedRTotal", "hitRate")

#: Orden determinista de las dimensiones en la salida.
_DIM_ORDER: tuple[str, ...] = (
    DIM_GLOBAL,
    DIM_YEAR,
    DIM_REGIME,
    DIM_OPERATIONAL,
    DIM_YEAR_REGIME,
)

#: Ejes de la descomposición de incertidumbre (declarados, no negociables).
AXES: tuple[str, ...] = ("venue", "sampling", "total")

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "El bootstrap mide la incertidumbre de MUESTREO DE CICLOS (con reemplazo, n fijo), no la "
    "independencia de mercado ni el futuro.",
    "Los K sorteos del venue NO son K muestras independientes de mercado: son K realizaciones del "
    "MISMO experimento historico con distinto sorteo del venue.",
    "La banda total combina venue y sampling por ley de varianza total (totalVar = venueVar + "
    "samplingVar): los ejes se tratan como ortogonales y la interaccion real se aproxima por el "
    "pool K x B, no por un modelo explicito.",
    "La unidad de remuestreo es el CICLO; el n de cada celda y sorteo se mantiene (bootstrap).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. Un cubo ausente en un sorteo baja "
    "drawsWithCell, no se inventa.",
    "Un cubo puede aparecer en pocos sorteos o con pocos ciclos: fragility declara el n efectivo "
    "y por que la banda puede ser enganosamente estrecha (no se oculta).",
    "Determinismo: mismo B y misma semilla => payload identico (PRNG propio, sin reloj ni azar "
    "global). Determinismo NO es validez.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas). "
    "CONFIRMED sigue reservado a evidencia PAPER.",
    "La unidad es el CICLO; la atribucion temporal es por entryDay (dia de decision).",
    "El regimen es el agregado trial por dia; el sector es el del catalogo ACTUAL (no point-in-time).",
)


# ── PRNG determinista (propio, sin dependencias; estable entre versiones) ──────────

_MASK64 = 0xFFFFFFFFFFFFFFFF
_GOLDEN = 0x9E3779B97F4A7C15


def _mix64(state: int) -> tuple[int, int]:
    """SplitMix64: ``(estado_siguiente, valor)`` de 64 bits (determinista, sin azar global)."""
    state = (state + _GOLDEN) & _MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return state, (z ^ (z >> 31)) & _MASK64


def _seed_state(*parts: Any) -> int:
    """Estado inicial de 64 bits a partir de una clave estable (``sha256``, sin azar)."""
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


# ── Estadística declarada (None cuando no hay muestra; nunca 0) ────────────────────


def _mean(values: Sequence[float]) -> float | None:
    """Media de una muestra o ``None`` si está vacía."""
    return sum(values) / len(values) if values else None


def _pop_variance(values: Sequence[float]) -> float | None:
    """Varianza POBLACIONAL de una muestra (``None`` si vacía; ``0.0`` si ``n = 1``)."""
    if not values:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _percentile(ordered: Sequence[float], quantile: float) -> float | None:
    """Percentil con interpolación lineal entre rangos (determinista; ``None`` si vacío)."""
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = quantile * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _band(pool: Sequence[float]) -> dict[str, Any] | None:
    """Banda empírica de un pool: ``mean``/``p2_5``/``p97_5``/``stdev``/``n`` (``None`` vacío)."""
    ordered = sorted(pool)
    if not ordered:
        return None
    mean = _mean(ordered)
    assert mean is not None
    return {
        "n": len(ordered),
        "mean": mean,
        "p2_5": _percentile(ordered, 0.025),
        "p97_5": _percentile(ordered, 0.975),
        "stdev": math.sqrt(_pop_variance(ordered) or 0.0),
    }


def _crosses_zero(low: float | None, high: float | None) -> bool | None:
    """``True`` si la banda abarca el cero; ``None`` si no hay banda."""
    if low is None or high is None:
        return None
    return bool(low < 0.0 < high)


def _axis_validity(
    *,
    mean: float | None,
    crosses: bool | None,
    se: float | None,
    draws_with_cell: int,
) -> dict[str, Any]:
    """Citabilidad de UN eje con el criterio sellado por ``W3.3`` (evaluado, no narrado)."""
    if mean is None or se is None or crosses is None:
        return {"crossesZeroR": crosses, "pointCitable": False, "se": se, "note": "sin_muestra"}
    if draws_with_cell < MIN_DRAWS_FOR_BAND:
        return {"crossesZeroR": crosses, "pointCitable": False, "se": se, "note": "insufficient_draws"}
    point_citable = (not crosses) and abs(mean) > CI95_Z * se
    return {"crossesZeroR": crosses, "pointCitable": bool(point_citable), "se": se, "note": None}


# ── Ledger de ciclos (la muestra cruda de UN sorteo) ──────────────────────────────


def _excursion_mae_mfe(row: Any) -> tuple[float | None, float | None]:
    """MAE/MFE (R) de una excursión (``Excursion`` o su ``to_dict``); ``None`` si no es medible."""
    if isinstance(row, Excursion):
        return finite_number(row.mae_r), finite_number(row.mfe_r)
    if isinstance(row, Mapping):
        return finite_number(row.get("maeR")), finite_number(row.get("mfeR"))
    return None, None


def _cycle_id(trip: Mapping[str, Any]) -> str:
    """Identidad del ciclo financiero del round trip (``""`` si no la trae)."""
    return str(trip.get("cycleId") or trip.get("cycle_id") or "").strip()


def _fill_cycle_id(fill: Any) -> str:
    return str(getattr(fill, "cycle_id", None) or "").strip()


def _fills_by_cycle(cost_rows: Sequence[Any]) -> dict[str, list[Any]]:
    """``{cycle_id: [fills]}`` de los fills que declaran su ciclo (nunca se inventa uno)."""
    grouped: dict[str, list[Any]] = {}
    for fill in cost_rows or ():
        cycle = _fill_cycle_id(fill)
        if cycle:
            grouped.setdefault(cycle, []).append(fill)
    return grouped


def _reason_by_cycle(cost_rows: Sequence[Any], close_rows: Sequence[Any]) -> dict[str, str]:
    """``{cycle_id: reason}`` uniendo el motivo de cierre por ``executionId`` (jamás por símbolo).

    La fila ``position_close`` del journal NO trae el ciclo: trae el ``executionId`` de la primera
    pata aplicada de la salida. El fill durable de esa pata SÍ trae el ``cycle_id`` (heredado de la
    posición), así que el emparejamiento es por identidad de ejecución. Sin esa pata el motivo
    queda sin ciclo y se declara hueco, no se reparte a ciegas.
    """
    cycle_by_execution: dict[str, str] = {}
    for fill in cost_rows or ():
        execution = str(getattr(fill, "execution_id", None) or "").strip()
        fill_cycle = _fill_cycle_id(fill)
        if execution and fill_cycle:
            cycle_by_execution[execution] = fill_cycle
    reasons: dict[str, str] = {}
    for row in close_rows or ():
        reason: Any
        if isinstance(row, Mapping):
            execution = str(row.get("executionId") or row.get("execution_id") or "").strip()
            reason = row.get("reason")
        else:
            execution = str(getattr(row, "execution_id", None) or "").strip()
            reason = getattr(row, "reason", None)
        close_cycle = cycle_by_execution.get(execution)
        if close_cycle and close_cycle not in reasons:
            reasons[close_cycle] = str(reason or "")
    return reasons


def _entry_side(trip: Mapping[str, Any]) -> str | None:
    """Lado de ENTRADA inferido de la geometría (largo⇒``buy``; corto⇒``sell``)."""
    direction = infer_direction(entry=trip.get("entryPrice"), stop=trip.get("stop"))
    if direction == LONG:
        return "buy"
    if direction is None:
        return None
    return "sell"


def _risk_cash(trip: Mapping[str, Any], fills: Sequence[Any], entry_side: str | None) -> float | None:
    """Riesgo al nacer en MONEDA (``|entry − stop| × qty``) para pasar fricción de moneda a R."""
    entry = finite_number(trip.get("entryPrice"))
    stop = finite_number(trip.get("stop"))
    if entry is None or stop is None or entry_side is None:
        return None
    qty = 0.0
    measured = False
    for fill in fills:
        if str(getattr(fill, "side", None) or "").strip().lower() != entry_side:
            continue
        quantity = finite_number(getattr(fill, "quantity", None))
        if quantity is None or quantity <= 0:
            continue
        qty += quantity
        measured = True
    if not measured or qty <= 0:
        return None
    return abs(entry - stop) * qty


def _entry_slippage_bps(fills: Sequence[Any], entry_side: str | None) -> float | None:
    """Desvío medio (bps, ponderado por cantidad) del precio de entrada contra su mid.

    Mide la fricción de ENTRADA que este simulador aplicó (``|price − reference_mid| / mid``), la
    misma magnitud que ``applied_cost`` pero por pata de entrada. Sin referencia utilizable es un
    hueco declarado (nunca ``0``: diría "entrada sin coste").
    """
    if entry_side is None:
        return None
    weighted = 0.0
    weight = 0.0
    measured = False
    for fill in fills:
        if str(getattr(fill, "side", None) or "").strip().lower() != entry_side:
            continue
        price = finite_number(getattr(fill, "price", None))
        reference = finite_number(getattr(fill, "reference_mid", None))
        quantity = finite_number(getattr(fill, "quantity", None))
        if price is None or reference is None or reference <= 0 or quantity is None or quantity <= 0:
            continue
        measured = True
        weighted += abs(price - reference) / reference * 10_000.0 * quantity
        weight += quantity
    if not measured or weight <= 0:
        return None
    return weighted / weight


# ── Geometría de la invalidación de la tesis (capa v4, aditiva) ───────────────────

#: Tokens DECLARADOS de la condición de invalidación (contrato de observabilidad, cerrado).
#: ``nivel_igual_stop``: el nivel congelado ES el stop inicial de la posición (hoy, la regla
#: estructural: ningún productor manda un ``invalidationPrice`` distinto). ``nivel_distinto_stop``:
#: el nivel congelado NO coincide con el stop inicial capturado — se declara, no se reconcilia.
INVALIDATION_CONDITION_SIN_GEOMETRIA = "sin_geometria"
INVALIDATION_CONDITION_NIVEL_DISTINTO_STOP = "nivel_distinto_stop"
INVALIDATION_CONDITION_NIVEL_IGUAL_STOP = "nivel_igual_stop"
INVALIDATION_CONDITIONS: frozenset[str] = frozenset(
    {
        INVALIDATION_CONDITION_SIN_GEOMETRIA,
        INVALIDATION_CONDITION_NIVEL_DISTINTO_STOP,
        INVALIDATION_CONDITION_NIVEL_IGUAL_STOP,
    }
)

#: Tolerancia RELATIVA para afirmar "el nivel es el stop inicial" (nunca una igualdad de ``float``).
_INVALIDATION_REL_TOL = 1e-9


def _adverse_r(
    price: Any,
    *,
    entry: float | None,
    risk: float | None,
    direction: str | None,
) -> float | None:
    """Distancia en R en la dirección ADVERSA (``<= 0`` en el lado de la pérdida).

    El convenio es el MISMO que ``exit_plan.worst_adverse_price``: para un largo el precio adverso
    está POR DEBAJO de la entrada (R negativo) y para un corto POR ENCIMA. ``None`` cuando falta
    algún ancla (entrada, riesgo) o el riesgo no es positivo: la geometría no se inventa.
    """
    value = finite_number(price)
    if value is None or entry is None or risk is None or risk <= 0.0:
        return None
    if direction == LONG:
        return (value - entry) / risk
    if direction == SHORT:
        return (entry - value) / risk
    return None


def _invalidation_fields(
    *,
    entry: float | None,
    initial_stop: float | None,
    direction: str | None,
    risk: float | None,
    level: float | None,
    current_stop: float | None,
    mae_r: float | None,
    position_entry: float | None = None,
    position_initial_stop: float | None = None,
    position_initial_risk: float | None = None,
) -> dict[str, Any]:
    """Geometría de la invalidación de UN ciclo (capa v4, aditiva; pura y determinista).

    Publica el nivel congelado (``invalidationPrice``), el stop VIGENTE al cierre
    (``currentStopAtExit``) y sus posiciones en R adverso, más los dos hechos que explican por qué
    el cierre es ``THESIS_EXIT`` y no ``STRUCTURAL_STOP``: si el stop se apretó POR ENCIMA del nivel
    congelado (``stopAboveLevelR``) y si el peor adverso alcanzó el nivel (``maeReachedLevel``, con
    el MAE reconstruido D1 como APROXIMACIÓN declarada del persistido).

    La normalización en R usa los anclajes PROPIOS de la POSICIÓN capturados por la costura
    (``actual_entry``/``initial_risk`` al nacer), y sólo cae a los del round trip
    (``entryPrice``/``stop``) si no llegaron: el nivel se congela contra el stop de la posición, no
    contra la base de R que el ledger use para ``realizedR``. Cuando ambas bases difieren se
    publica ``stopBasisMismatchR`` (>0 ⇒ discrepancia declarada, NO reconciliada aquí).

    Un ancla ilegible queda ``None`` (nunca ``0``); sin nivel o sin stop vigente la condición es
    ``sin_geometria`` y los booleanos son ``None``: la condición de invalidación NO se inventa.
    """
    basis_entry = position_entry if position_entry is not None else entry
    basis_risk = (
        position_initial_risk
        if position_initial_risk is not None and position_initial_risk > 0.0
        else risk
    )
    level_r = _adverse_r(level, entry=basis_entry, risk=basis_risk, direction=direction)
    current_stop_r = _adverse_r(current_stop, entry=basis_entry, risk=basis_risk, direction=direction)
    reference_stop = position_initial_stop if position_initial_stop is not None else initial_stop
    level_equals_initial_stop: bool | None = None
    if level is not None and reference_stop is not None:
        level_equals_initial_stop = abs(level - reference_stop) <= _INVALIDATION_REL_TOL * max(
            1.0, abs(reference_stop)
        )
    stop_above_level_r = (
        current_stop_r - level_r
        if current_stop_r is not None and level_r is not None
        else None
    )
    mae_vs_level_r = level_r - mae_r if level_r is not None and mae_r is not None else None
    mae_reached_level = mae_vs_level_r >= 0.0 if mae_vs_level_r is not None else None
    stop_basis_mismatch_r: float | None = None
    if (
        position_initial_stop is not None
        and initial_stop is not None
        and basis_risk is not None
        and basis_risk > 0.0
    ):
        stop_basis_mismatch_r = abs(initial_stop - position_initial_stop) / basis_risk
    if level_r is None or current_stop_r is None:
        condition = INVALIDATION_CONDITION_SIN_GEOMETRIA
    elif level_equals_initial_stop:
        condition = INVALIDATION_CONDITION_NIVEL_IGUAL_STOP
    else:
        condition = INVALIDATION_CONDITION_NIVEL_DISTINTO_STOP
    return {
        "invalidationPrice": level,
        "initialStop": position_initial_stop,
        "currentStopAtExit": current_stop,
        "invalidationLevelR": level_r,
        "currentStopAtExitR": current_stop_r,
        "stopAboveLevelR": stop_above_level_r,
        "levelEqualsInitialStop": level_equals_initial_stop,
        "stopBasisMismatchR": stop_basis_mismatch_r,
        "maeVsLevelR": mae_vs_level_r,
        "maeReachedLevel": mae_reached_level,
        "thesisExitCondition": condition,
    }


def build_cycle_ledger(
    *,
    round_trips: Sequence[Mapping[str, Any]],
    excursions_rows: Sequence[Excursion | Mapping[str, Any]] = (),
    entry_excursions_rows: Sequence[Excursion | Mapping[str, Any]] = (),
    regime_by_day: Mapping[str, Any] | None = None,
    operational_regime_by_day: Mapping[str, Any] | None = None,
    cost_rows: Sequence[Any] = (),
    close_rows: Sequence[Any] = (),
    invalidation_by_cycle: Mapping[str, Mapping[str, Any]] | None = None,
    entry_window_days: int = DEFAULT_ENTRY_WINDOW_DAYS,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Ledger de ciclos de UN sorteo (puro y determinista: sin reloj ni azar).

    Una fila por ciclo con su ``realizedR`` y su excursión (MAE/MFE) unida por ``cycle_key``, más
    las etiquetas declaradas (``year``/``regime``/``operationalRegime``). La capa v2 añade —de
    forma ADITIVA— el **mecanismo de salida** (``exitMechanism``/``exitReason``), la **fricción
    aplicada** (``frictionCost``/``frictionR``/``frictionMeasurement``), el **R neto**
    (``netRealizedR``) y la **excursión adversa temprana** post-entrada (``entryAdverseR``/
    ``entryAdverseWindowDays``/``entryAdverseGap``), además del desvío de entrada en bps. La capa
    v3 añade —también ADITIVA— la **estrategia** (``strategyVersion``) y la **dirección**
    (``direction``, inferida de ``stop`` vs ``entry``; ``None`` si la geometría es imposible). La
    capa v4 añade —ADITIVA— la **geometría de la invalidación de la tesis**: ``invalidationPrice``,
    ``initialStop`` (el de la POSICIÓN), ``currentStopAtExit``, ``invalidationLevelR``/
    ``currentStopAtExitR``/``stopAboveLevelR``/``stopBasisMismatchR``/``maeVsLevelR``, los booleanos
    ``levelEqualsInitialStop``/``maeReachedLevel`` y el token ``thesisExitCondition``.
    ``invalidation_by_cycle`` es la captura —opt-in, inerte— del estado congelado de la posición por
    ``cycle_id`` (entrada real, stop y riesgo al nacer, nivel congelado y stop vigente); sin ella los
    campos v4 quedan hueco declarado.

    Reglas duras: un valor ilegible queda ``None`` (nunca ``0``); el R neto sólo se afirma con
    fricción ``COMPLETE`` (con ``PARTIAL`` es un SUELO y se declara el hueco, jamás se publica el
    R bruto haciéndolo pasar por neto); un motivo de cierre ausente es ``SIN_MECANISMO``. El orden
    es determinista por ``(entryDay, symbol, exitDay)``.
    """
    indexed = index_excursions(excursions_rows)
    entry_indexed = index_excursions(entry_excursions_rows)
    year_reader = year_key_reader()
    trial_reader = regime_key_reader(regime_by_day or {})
    operational_reader = operational_regime_key_reader(operational_regime_by_day or {})
    ordered = sorted(
        (dict(trip) for trip in round_trips or ()),
        key=lambda trip: (
            normalize_day(trip.get("entryDay")) or "",
            str(trip.get("symbol") or ""),
            normalize_day(trip.get("exitDay")) or "",
        ),
    )
    fills_by_cycle = _fills_by_cycle(cost_rows)
    reasons_by_cycle = _reason_by_cycle(cost_rows, close_rows)
    measured_cycle_ids = [cycle for trip in ordered if (cycle := _cycle_id(trip))]
    costs = applied_cost_from_fills(
        measured_cycle_ids,
        cost_rows or (),
        closed_cycle_ids=measured_cycle_ids,
    )
    window_days = max(1, int(entry_window_days))
    cycles: list[dict[str, Any]] = []
    for trip in ordered:
        mae, mfe = _excursion_mae_mfe(indexed.get(cycle_key(trip)))
        early = entry_indexed.get(cycle_key(trip))
        early_mae, _early_mfe = _excursion_mae_mfe(early)
        early_reason = None
        if early is None:
            early_reason = "sin_excursion_temprana"
        else:
            record = early.to_dict() if isinstance(early, Excursion) else early
            if early_mae is None:
                early_reason = str(record.get("reason") or "").strip() or "sin_excursion_temprana"

        realized = finite_number(trip.get("realizedR"))
        cycle = _cycle_id(trip)
        cost = costs.get(cycle) if cycle else None
        friction = finite_number(cost.friction) if cost is not None else None
        entry_side = _entry_side(trip)
        direction = infer_direction(entry=trip.get("entryPrice"), stop=trip.get("stop"))
        fills = fills_by_cycle.get(cycle, []) if cycle else []
        risk_cash = _risk_cash(trip, fills, entry_side)
        friction_r = None
        if friction is not None and risk_cash is not None and risk_cash > 0:
            friction_r = friction / risk_cash
        # El R NETO sólo se afirma con fricción COMPLETE: con PARTIAL lo medido es un SUELO, y
        # publicar ``bruto − suelo`` como neto lo haría pasar por completo. Se declara el hueco.
        net = None
        if (
            realized is not None
            and friction_r is not None
            and cost is not None
            and cost.measurement == "COMPLETE"
        ):
            net = realized - friction_r
        reason = reasons_by_cycle.get(cycle, "") if cycle else ""
        mechanism, evidence = classify_exit_mechanism(reason)
        slippage = _entry_slippage_bps(fills, entry_side)
        capture = (invalidation_by_cycle.get(cycle) if (invalidation_by_cycle and cycle) else None) or {}
        entry_price = finite_number(trip.get("entryPrice"))
        initial_stop = finite_number(trip.get("stop"))
        risk = (
            abs(entry_price - initial_stop)
            if entry_price is not None and initial_stop is not None and entry_price != initial_stop
            else None
        )
        invalidation = _invalidation_fields(
            entry=entry_price,
            initial_stop=initial_stop,
            direction=direction,
            risk=risk,
            level=finite_number(capture.get("invalidationPrice")),
            current_stop=finite_number(capture.get("currentStop")),
            mae_r=mae,
            position_entry=finite_number(capture.get("actualEntry")),
            position_initial_stop=finite_number(capture.get("initialStop")),
            position_initial_risk=finite_number(capture.get("initialRisk")),
        )
        cycles.append(
            {
                "symbol": str(trip.get("symbol") or "").strip(),
                "entryDay": normalize_day(trip.get("entryDay")) or "",
                "exitDay": normalize_day(trip.get("exitDay")) or "",
                "realizedR": realized,
                "maeR": mae,
                "mfeR": mfe,
                "year": year_reader(trip) or "",
                "regime": trial_reader(trip) or "",
                "operationalRegime": operational_reader(trip) or "",
                # ── Capa v3 (quirófano de la pérdida): dónde vive el ciclo ────────────
                "strategyVersion": (
                    str(trip.get("strategyVersion")).strip()
                    if trip.get("strategyVersion") is not None
                    and str(trip.get("strategyVersion")).strip()
                    else None
                ),
                "direction": direction,
                # ── Capa v4 (condición de la invalidación): qué disparó el THESIS_EXIT ──
                "entryPrice": entry_price,
                "stop": initial_stop,
                **invalidation,
                # ── Capa v2 (diagnóstico de la pérdida) ────────────────────────────────
                "exitMechanism": mechanism,
                "exitReason": evidence or (EXIT_MECHANISM_SIN_MECANISMO if not reason else reason),
                "frictionCost": friction,
                "frictionR": friction_r,
                "frictionMeasurement": str(cost.measurement) if cost is not None else "UNKNOWN",
                "netRealizedR": net,
                "entryAdverseR": early_mae,
                "entryAdverseWindowDays": window_days,
                "entryAdverseGap": early_reason,
                "entrySlippageBps": slippage,
                "entrySlippageGap": (
                    None
                    if slippage is not None
                    else ("sin_fills_del_ciclo" if not fills else "sin_referencia_entrada")
                ),
            }
        )
    return {
        "schemaVersion": LEDGER_SCHEMA_VERSION,
        "kind": LEDGER_KIND,
        "readOnly": True,
        "basis": "entryDay",
        "cycles": cycles,
        "meta": {str(key): value for key, value in (meta or {}).items()},
    }


# ── Plegado de los K sorteos en cubos ────────────────────────────────────────────


def _label(value: Any, fallback: str) -> str:
    """Etiqueta declarada de una dimensión: texto no vacío o el cubo ``fallback``."""
    text = str(value if value is not None else "").strip()
    return text or fallback


def _cell_cycles(ledger: Mapping[str, Any]) -> dict[tuple[str, str, str], list[float]]:
    """Ciclos MEDIBLES de un sorteo por cubo: ``{(dim, year, regime): [realizedR]}``.

    Un ciclo sin ``realizedR`` finito no vota (no se rellena con ``0``). Un mismo ciclo entra en
    GLOBAL, su AÑO, su RÉGIMEN, su RÉGIMEN OPERATIVO y su celda AÑO × RÉGIMEN.
    """
    cells: dict[tuple[str, str, str], list[float]] = {}
    for row in ledger.get("cycles") or ():
        realized = finite_number(row.get("realizedR"))
        if realized is None:
            continue
        year = _label(row.get("year"), SIN_YEAR)
        regime = _label(row.get("regime"), SIN_REGIMEN)
        operational = _label(row.get("operationalRegime"), SIN_OPERATIONAL)
        cells.setdefault((DIM_GLOBAL, "", ""), []).append(realized)
        cells.setdefault((DIM_YEAR, year, ""), []).append(realized)
        cells.setdefault((DIM_REGIME, "", regime), []).append(realized)
        cells.setdefault((DIM_OPERATIONAL, "", operational), []).append(realized)
        cells.setdefault((DIM_YEAR_REGIME, year, regime), []).append(realized)
    return cells


def _bootstrap(
    values: Sequence[float],
    *,
    resamples: int,
    seed: int,
    label: str,
) -> tuple[list[float], list[float]]:
    """Bootstrap con reemplazo de ``values``: ``(medias, tasas de acierto)`` de ``B`` remuestras.

    Determinista: el estado del PRNG se deriva de ``(seed, label)``. Se mantiene el ``n`` observado
    (cada remuestra tiene el mismo tamaño que la muestra) y se devuelven las dos estadísticas del
    MISMO remuestreo (no se remuestrea dos veces).
    """
    n = len(values)
    if n == 0 or resamples <= 0:
        return [], []
    positives = [1.0 if value > 0.0 else 0.0 for value in values]
    state = _seed_state(seed, label)
    means: list[float] = []
    hits: list[float] = []
    for _ in range(resamples):
        total = 0.0
        wins = 0.0
        for _ in range(n):
            state, z = _mix64(state)
            index = z % n
            total += values[index]
            wins += positives[index]
        means.append(total / n)
        hits.append(wins / n)
    return means, hits


def _metric_block(
    *,
    draw_values: Sequence[float],
    resample_values: Sequence[Sequence[float]],
    draws_with_cell: int,
) -> dict[str, Any]:
    """Banda y descomposición de varianza de UNA métrica (venue / sampling / total).

    ``venueVar`` = dispersión entre sorteos; ``samplingVar`` = media de la dispersión bootstrap
    dentro de cada sorteo; ``totalVar = venueVar + samplingVar``. Los SE se normalizan por ``K``
    (``sqrt(var / K)``). La banda TOTAL son los percentiles 2.5/97.5 del pool ``K × B``; la de
    SAMPLING aísla el eje centrando cada remuestra en la media global.
    """
    grand_mean = _mean(draw_values)
    venue_var = _pop_variance(draw_values)
    per_draw_sampling = [
        variance for rv in resample_values if (variance := _pop_variance(rv)) is not None
    ]
    sampling_var = _mean(per_draw_sampling)
    total_var = (
        venue_var + sampling_var
        if venue_var is not None and sampling_var is not None
        else None
    )
    draws_positive = max(1, int(draws_with_cell))
    venue_se = math.sqrt(venue_var / draws_positive) if venue_var is not None else None
    sampling_se = math.sqrt(sampling_var / draws_positive) if sampling_var is not None else None
    total_se = math.sqrt(total_var / draws_positive) if total_var is not None else None

    pool = [value for rv in resample_values for value in rv]
    total_band = _band(pool)
    sampling_pool: list[float] = []
    if grand_mean is not None:
        for draw_value, rv in zip(draw_values, resample_values, strict=True):
            sampling_pool.extend(grand_mean + (value - draw_value) for value in rv)
    sampling_band = _band(sampling_pool)

    venue_low = min(draw_values) if draw_values else None
    venue_high = max(draw_values) if draw_values else None
    share = None
    if total_var is not None and total_var > 0.0 and venue_var is not None and sampling_var is not None:
        share = {"venue": venue_var / total_var, "sampling": sampling_var / total_var}

    return {
        "mean": grand_mean,
        "venue": {
            "min": venue_low,
            "max": venue_high,
            "var": venue_var,
            "se": venue_se,
            "crossesZeroR": _crosses_zero(venue_low, venue_high),
        },
        "sampling": {
            "var": sampling_var,
            "se": sampling_se,
            "band": sampling_band,
            "crossesZeroR": _crosses_zero(
                sampling_band["p2_5"] if sampling_band else None,
                sampling_band["p97_5"] if sampling_band else None,
            ),
        },
        "total": {
            "var": total_var,
            "se": total_se,
            "band": total_band,
            "crossesZeroR": _crosses_zero(
                total_band["p2_5"] if total_band else None,
                total_band["p97_5"] if total_band else None,
            ),
        },
        "varianceShare": share,
    }


def _render_cell(
    key: tuple[str, str, str],
    *,
    per_draw_values: Sequence[Sequence[float]],
    resamples: int,
    seed: int,
    draws_with_cell: int,
    draws_total: int,
) -> dict[str, Any]:
    """Cubo con su banda TOTAL por métrica, su descomposición y su fragilidad declarada."""
    dimension, year, regime = key
    # Sólo los sorteos que MIDEN la celda votan: un cubo ausente no aporta un ``0``.
    present = [values for values in per_draw_values if values]
    draw_cycle_counts = [len(values) for values in present]
    draw_means = [value for values in present if (value := _mean(values)) is not None]
    # Un bootstrap por (cubo, sorteo): las tres métricas salen del MISMO remuestreo.
    bootstraps = [
        _bootstrap(values, resamples=resamples, seed=seed, label=f"{dimension}|{year}|{regime}|{i}")
        for i, values in enumerate(present)
    ]
    expectancy_resamples = [means for means, _hits in bootstraps]
    hit_resamples = [hits for _means, hits in bootstraps]
    total_resamples = [
        [len(values) * value for value in means]
        for values, (means, _hits) in zip(present, bootstraps, strict=True)
    ]
    metrics = {
        "expectancyR": _metric_block(
            draw_values=draw_means,
            resample_values=expectancy_resamples,
            draws_with_cell=draws_with_cell,
        ),
        "realizedRTotal": _metric_block(
            draw_values=[sum(values) for values in present],
            resample_values=total_resamples,
            draws_with_cell=draws_with_cell,
        ),
        "hitRate": _metric_block(
            draw_values=[
                (sum(1 for value in values if value > 0.0) / len(values)) if values else 0.0
                for values in present
            ],
            resample_values=hit_resamples,
            draws_with_cell=draws_with_cell,
        ),
    }

    reasons: list[str] = []
    if draws_with_cell < MIN_DRAWS_FOR_BAND:
        reasons.append("insufficient_draws")
    if draw_cycle_counts and min(draw_cycle_counts) < MIN_CYCLES_FOR_SAMPLING:
        reasons.append("few_cycles_per_draw")

    total_metric = metrics["realizedRTotal"]
    # La citabilidad del cubo se ancla al criterio de la banda de R total (el MISMO de ``W3.3``),
    # evaluado por eje: venue (dispersión entre sorteos), sampling (bootstrap) y total (ambos).
    axis_validity = {
        axis: _axis_validity(
            mean=total_metric["mean"],
            crosses=total_metric[axis]["crossesZeroR"],
            se=total_metric[axis]["se"],
            draws_with_cell=draws_with_cell,
        )
        for axis in AXES
    }
    cell: dict[str, Any] = {
        "drawsWithCell": draws_with_cell,
        "drawsTotal": draws_total,
        "cycles": {
            "total": sum(draw_cycle_counts) if draw_cycle_counts else 0,
            "minPerDraw": min(draw_cycle_counts) if draw_cycle_counts else None,
            "maxPerDraw": max(draw_cycle_counts) if draw_cycle_counts else None,
            "meanPerDraw": _mean([float(count) for count in draw_cycle_counts]),
        },
        "metrics": metrics,
        "validity": {
            "venuePointCitable": axis_validity["venue"]["pointCitable"],
            "samplingPointCitable": axis_validity["sampling"]["pointCitable"],
            "totalPointCitable": axis_validity["total"]["pointCitable"],
            "venue": axis_validity["venue"],
            "sampling": axis_validity["sampling"],
            "total": axis_validity["total"],
        },
        "fragility": {"fragile": bool(reasons), "reasons": reasons},
    }
    if dimension == DIM_YEAR:
        cell["year"] = year
    elif dimension in (DIM_REGIME, DIM_OPERATIONAL):
        cell["regime"] = regime
    elif dimension == DIM_YEAR_REGIME:
        cell["year"] = year
        cell["regime"] = regime
    return cell


def _sort_key(key: tuple[str, str, str]) -> tuple[int, str, str]:
    """Orden determinista de los cubos: por dimensión, luego año, luego régimen."""
    dimension, year, regime = key
    return (_DIM_ORDER.index(dimension), year, regime)


# ── Cobertura declarada (años × sorteos) ─────────────────────────────────────────


def _coverage_from_ledgers(ledgers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Cobertura mínima derivada de los ledgers: por año, en cuántos sorteos aparece con ciclos."""
    years: list[str] = []
    seen: set[str] = set()
    per_draw: list[set[str]] = []
    for ledger in ledgers:
        draw_years: set[str] = set()
        for row in ledger.get("cycles") or ():
            year = str(row.get("year") or "").strip()
            if year:
                draw_years.add(year)
                if year not in seen:
                    seen.add(year)
                    years.append(year)
        per_draw.append(draw_years)
    years.sort()
    per_year = [
        {
            "year": year,
            "measured": sum(1 for draw_years in per_draw if year in draw_years),
            "empty": 0,
            "notMeasured": 0,
            "reasons": [],
        }
        for year in years
    ]
    return {"yearsRequested": years, "drawsTotal": len(ledgers), "perYear": per_year}


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_sampling_artifact(
    *,
    draw_ledgers: Sequence[Mapping[str, Any]],
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    venue_band: Mapping[str, Any] | None = None,
    coverage: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico del bootstrap de ciclos y de la banda TOTAL (puro y determinista).

    ``draw_ledgers`` son los ``K`` ledgers de ciclos (uno por sorteo del venue). Pliega cada cubo
    con la descomposición venue/sampling/total por métrica, la banda TOTAL (percentiles del pool
    ``K × B``) y la fragilidad declarada. Un cubo sin muestra no aparece; un hueco queda ``None``,
    nunca ``0``.
    """
    ordered = list(draw_ledgers or ())
    draws_total = len(ordered)
    resamples = max(0, int(resamples))
    folded = [_cell_cycles(ledger) for ledger in ordered]

    keys: set[tuple[str, str, str]] = set()
    for cells in folded:
        keys.update(cells)

    rendered: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key in sorted(keys, key=_sort_key):
        per_draw_values = [cells.get(key, []) for cells in folded]
        draws_with_cell = sum(1 for values in per_draw_values if values)
        rendered[key] = _render_cell(
            key,
            per_draw_values=per_draw_values,
            resamples=resamples,
            seed=seed,
            draws_with_cell=draws_with_cell,
            draws_total=draws_total,
        )

    def _dimension(dimension: str) -> list[dict[str, Any]]:
        return [rendered[key] for key in sorted(rendered, key=_sort_key) if key[0] == dimension]

    empty_cell = {
        "drawsWithCell": 0,
        "drawsTotal": draws_total,
        "cycles": {"total": 0, "minPerDraw": None, "maxPerDraw": None, "meanPerDraw": None},
        "metrics": {
            metric: {
                "mean": None,
                "venue": {"min": None, "max": None, "var": None, "se": None, "crossesZeroR": None},
                "sampling": {"var": None, "se": None, "band": None, "crossesZeroR": None},
                "total": {"var": None, "se": None, "band": None, "crossesZeroR": None},
                "varianceShare": None,
            }
            for metric in METRICS
        },
        "validity": {
            "venuePointCitable": False,
            "samplingPointCitable": False,
            "totalPointCitable": False,
            "venue": {"crossesZeroR": None, "pointCitable": False, "se": None, "note": "sin_muestra"},
            "sampling": {"crossesZeroR": None, "pointCitable": False, "se": None, "note": "sin_muestra"},
            "total": {"crossesZeroR": None, "pointCitable": False, "se": None, "note": "sin_muestra"},
        },
        "fragility": {"fragile": True, "reasons": ["insufficient_draws"]},
    }
    global_cell = rendered.get((DIM_GLOBAL, "", ""), empty_cell)

    resolved_coverage: Mapping[str, Any] | None = coverage
    if resolved_coverage is None and venue_band is not None:
        resolved_coverage = venue_band.get("coverage") if isinstance(venue_band, Mapping) else None
    if resolved_coverage is None:
        resolved_coverage = _coverage_from_ledgers(ordered)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "basis": "entryDay",
        "resamplingUnit": "cycle",
        "draws": draws_total,
        "resamples": resamples,
        "seed": int(seed),
        "axes": list(AXES),
        "metrics": list(METRICS),
        "coverage": dict(resolved_coverage),
        "global": global_cell,
        "byYear": _dimension(DIM_YEAR),
        "byRegime": _dimension(DIM_REGIME),
        "byOperationalRegime": _dimension(DIM_OPERATIONAL),
        "byYearByRegime": _dimension(DIM_YEAR_REGIME),
        "venueBandCrossCheck": _venue_band_cross_check(global_cell, venue_band),
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


def _venue_band_cross_check(
    global_cell: Mapping[str, Any], venue_band: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Autochequeo: la componente venue del cubo GLOBAL vs la banda del venue sellada (tolerante).

    No es un gate: declara si la lectura del venue de esta capa coincide con el artefacto
    ``dia-d-multi-band-v1`` cuando se le pasa, para que no compare accidentalmente otra cosa.
    """
    if not isinstance(venue_band, Mapping):
        return {"available": False, "note": "no se cruzó contra una banda del venue sellada"}
    reference = venue_band.get("global") or {}
    reference_validity = reference.get("validity") or {}
    metric = (global_cell.get("metrics") or {}).get("realizedRTotal") or {}
    venue = metric.get("venue") or {}
    drifted = [
        name
        for name, left, right in (
            ("crossesZeroR", venue.get("crossesZeroR"), reference_validity.get("crossesZeroR")),
            (
                "pointCitable",
                (global_cell.get("validity") or {}).get("venuePointCitable"),
                reference_validity.get("pointCitable"),
            ),
        )
        if left != right
    ]
    return {
        "available": True,
        "evidenceDrift": bool(drifted),
        "driftedKeys": drifted,
        "referenceDraws": venue_band.get("draws"),
        "referenceSe": reference_validity.get("se"),
    }


__all__ = [
    "AXES",
    "DEFAULT_LIMITS",
    "DEFAULT_RESAMPLES",
    "DEFAULT_SEED",
    "INVALIDATION_CONDITIONS",
    "INVALIDATION_CONDITION_NIVEL_DISTINTO_STOP",
    "INVALIDATION_CONDITION_NIVEL_IGUAL_STOP",
    "INVALIDATION_CONDITION_SIN_GEOMETRIA",
    "KIND",
    "LEDGER_KIND",
    "LEDGER_SCHEMA_VERSION",
    "METRICS",
    "MIN_CYCLES_FOR_SAMPLING",
    "SCHEMA_VERSION",
    "build_cycle_ledger",
    "build_sampling_artifact",
]
