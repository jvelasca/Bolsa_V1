"""V2.88.45 · DÍA-D AUTO — QUIRÓFANO DEL ``THESIS_EXIT`` (puro, sin I/O).

Qué es
------
La atribución multirregimen (``dia_d_multi``), su banda venue/sampling (``dia_d_multi_sampling``)
y el diagnóstico del origen de la pérdida (``dia_d_loss_origin``) dijeron *cuánto*, *dónde* y *por
qué clase de decisión* se cierra cada ciclo. Aislaron un hallazgo incómodo: el ``STOP_EJECUTADO``
domina en frecuencia (``93,4 %``) con expectancy bruta ``~0``, mientras el grueso del ``R`` bruto
negativo vive en pocos ``THESIS_EXIT`` (``38`` ciclos, ``expectancyR = -0.7087``, ``hitRate``
``8,3 %``). Este módulo **abre quirúrgicamente** esos ciclos: responde a *dónde viven* los
``THESIS_EXIT`` —estrategia, dirección, año/régimen, edad, geometría, entrada, coste— sin tocar el
motor, y —capa v4— a *qué condición* los disparó: el **nivel de invalidación congelado** (que hoy
**ES el stop inicial**, porque ningún productor manda un nivel de tesis distinto), el **stop vigente
al cierre** y si el peor adverso alcanzó el nivel. Se mide; no se inventa una causa.

Ejes de la descomposición
-------------------------
* **dónde** — ``byStrategy`` / ``byDirection`` / ``byYear`` / ``byRegime`` / ``byOperationalRegime``.
* **cuándo se agotó** — ``byAgeBucket`` (días naturales ``entryDay``→``exitDay``, en cubos duros).
* **cómo se movió** — excursión media/mediana ``maeR``/``mfeR``, captura del MFE y ``leftOnTableR``.
* **cómo entró** — excursión adversa temprana + slippage señal→ejecución.
* **cuánto costó** — fricción en ``R`` y ``R`` neto (suelo declarado si falta fricción ``COMPLETE``).
* **qué la invalidó** (v4) — nivel congelado, stop vigente al cierre y alcance del peor adverso.
* **por qué ruta** (v5) — la ruta de la invalidación (``ruta_mark`` vs ``ruta_mae`` sobre el MAE
  persistido), el primer día en que el nivel se alcanzó y la huella del stop (sin cambio / ratchet
  / break-even). Responde a *por qué el mismo nivel produce* ``THESIS_EXIT`` *y no* ``STOP``.
* **qué hizo el decider** (v6) — la huella de DECISIÓN del toque del stop (``decisionRoute``:
  materializado / orden_creada_sin_fill / stop_evaluado_sin_orden / evaluado sin materializar (hueco)
  / no evaluado / sin toque / sin traza), leída del MISMO
  fotograma del día (``decisionReasons``/``decisionLabel``/``filledQty``/``survived``). Cierra la
  pregunta A/B/C de ``v2.88.47`` sin contrafactual.
* **¿se creó la orden?** (v7) — ``orderCreated`` por ciclo (existencia del INTENT durable de salida)
  SEPARA el caso A (``stop_evaluado_sin_orden``) del caso C (``orden_creada_sin_fill``); deja
  ``stop_evaluado_sin_materializar`` SÓLO como hueco no medido. Cierra A/C sin tocar el motor.
* **cuánta concentración** — símbolos distintos y clusters (top símbolo / top semana ISO).

Reglas duras (heredadas, no se relajan)
---------------------------------------
* Un hueco es ``None``/``NOT_MEASURED``; **nunca** se rellena con ``0``.
* El R neto sólo se afirma con fricción ``COMPLETE``: con ``PARTIAL`` el neto es un **suelo** y se
  declara (jamás se publica el bruto disfrazado de neto).
* La captura del MFE se define sobre el resultado **NO negativo** (``capturedR = max(realizedR, 0)``),
  misma semántica sellada en ``capture_study`` (``v2.88.40``, ``A39-01``): vive en ``[0, +inf)``,
  no cambia de signo y ``leftOnTableR`` **nunca** supera el MFE. Un ``mfeR`` no positivo es un hueco.
* **Advisory y read-only:** no cambia el motor, los umbrales, ``TOP_N`` ni la allocation; no
  introduce contrafactuales ni re-simula salidas alternativas.
* Determinista (sin reloj ni azar global): mismas entradas ⇒ payload byte a byte idéntico.
* Evidencia de **REPLAY/OOS**: no sustituye la ventana PAPER (``P3-2``/``P3-3`` siguen abiertas).

Qué NO es: causal. Es una descomposición **descriptiva** de los ciclos que el motor decidió cerrar
por invalidación de tesis; el motivo crudo es el token colapsado del plan, no la condición que lo
disparó.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any

from bolsa_application.dia_d_auto import finite_number, normalize_day
from bolsa_application.dia_d_exit_mechanism import EXIT_MECHANISM_THESIS
from bolsa_application.dia_d_multi_sampling import (
    DECISION_ROUTE_SIN_TRAZA,
    DECISION_ROUTES,
    INVALIDATION_CONDITION_SIN_GEOMETRIA,
    MIN_CYCLES_FOR_SAMPLING,
    THESIS_ROUTE_SIN_GEOMETRIA,
    TIMELINE_START_FIRST_TICK_AFTER_ENTRY,
)
from bolsa_application.dia_d_multi_uncertainty import MIN_DRAWS_FOR_BAND

#: Versión del esquema del artefacto. Un cambio de forma la sube (v2: bloque ``invalidation``;
#: v3: bloque ``disambiguation`` + ejes ``byRoute``/``byStopPath``; v4: bloque
#: ``decisionCorrelation`` + eje ``byDecisionRoute``; v5: separación A/C en ``decisionRoute``).
SCHEMA_VERSION = "dia-d-thesis-exit-v5"

#: Tipo del artefacto.
KIND = "DIA_D_AUTO_THESIS_EXIT"

#: El mecanismo que este artefacto abre (la etiqueta decisoria del plan).
MECHANISM = EXIT_MECHANISM_THESIS

#: Umbrales declarados de la calidad de entrada (mismos que ``dia_d_loss_origin``).
ENTRY_ADVERSE_HALF_R = -0.5
ENTRY_ADVERSE_ONE_R = -1.0

#: Cubos DURAS de edad del ciclo (días naturales ``entryDay``→``exitDay``), declarados y cerrados.
AGE_BUCKETS: tuple[str, ...] = ("1-3", "4-10", "11-30", ">30", "unknown")

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
    "Diagnostico DESCRIPTIVO, no causal: descompone DONDE viven los THESIS_EXIT, no por que se "
    "invalidó la tesis.",
    "Evidencia de REPLAY/OOS: NO sustituye la ventana PAPER real (P3-2/P3-3 siguen abiertas).",
    "Un hueco es None/NOT_MEASURED; nunca se rellena con 0. La media de una muestra vacia es None.",
    "El R NETO solo se afirma con friccion COMPLETE; con PARTIAL es un SUELO declarado, jamas el "
    "bruto disfrazado de neto.",
    "La CONDICION de invalidacion se mide (capa v4) desde el estado CONGELADO de la posicion: el "
    "nivel de invalidacion ES hoy el stop inicial (ningun productor manda un nivel de tesis "
    "distinto; deuda declarada), asi que un THESIS_EXIT es estructural. El booleano "
    "maeReachedLevel usa el MAE RECONSTRUIDO D1 como APROXIMACION declarada del peor adverso "
    "PERSISTIDO por el motor: no es el mismo numero y no se presenta como tal.",
    "La capa v4 es OPT-IN: exige el estado capturado por la costura inerte (--cycle-detail). Sin "
    "ella, invalidation.measured = 0 y los anclajes quedan None (hueco declarado, nunca 0).",
    "El R de la capa v4 se normaliza con los anclajes PROPIOS de la POSICION (entrada real y riesgo "
    "al nacer). Cuando el stop del round trip (base de R del ledger) difiere del stop congelado de "
    "la posicion, se declara en stopBasisMismatchR: es una discrepancia MEDIDA y NO reconciliada "
    "aqui (afecta a la normalizacion, no al hecho observado del cierre).",
    "La capa v5 (desambiguacion THESIS_EXIT vs STOP) es OPT-IN: exige la costura --cycle-detail con "
    "la SECUENCIA dia a dia por ciclo. Sin ella, thesisExitRoute = sin_geometria y los booleanos "
    "quedan None (hueco declarado, nunca 0).",
    "thesisExitRoute distingue la RUTA de la invalidacion: ruta_mae = el MAE PERSISTIDO "
    "(mfeMae.maeR) cruzo el nivel (un stop ya tocado que el precio recupero); ruta_mark = lo cruzo "
    "el mark del dia. Para un THESIS_EXIT se espera ruta_mae: la precedencia del STRUCTURAL_STOP "
    "sobre THESIS_INVALIDATION y la monotonia del ratchet (current_stop >= nivel) impiden la ruta "
    "del mark. Es una RUTA de evaluacion medida, no una causa de mercado.",
    "structuralStopCandidate=True en un THESIS_EXIT senala duplicidad semantica entre proteccion e "
    "invalidacion de tesis: se DECLARA, no se reconcilia aqui.",
    "firstTouchDay es el primer dia en que el MAE PERSISTIDO alcanzo el nivel (fecha de la "
    "OBSERVACION, no necesariamente del minimo intrabar): es la mejor reconstruccion disponible en "
    "D1 y no se presenta como el instante exacto del toque.",
    "AUTO NO deja una orden STOP en reposo: el stop lo ejecuta el decider D1 (mark vs current_stop). "
    "Por eso no se declara 'existia orden STOP': no aplica a este motor.",
    "La distincion ciclos UNICOS (los THESIS_EXIT) vs observaciones pooled (ciclos x K sorteos) "
    "sigue vigente: la unidad de remuestreo es el ciclo por sorteo; no se suman como operaciones "
    "financieras independientes.",
    "La edad es en DIAS NATURALES entre entryDay y exitDay (el replay es D1): no son barras "
    "efectivas ni intradia, y el dia de entrada puede incluir movimiento previo al fill.",
    "La distancia al objetivo NO es medible (el round trip no guarda el target): se aproxima con "
    "el MFE y la captura, no se presenta como distancia exacta.",
    "La captura del MFE usa la MISMA semantica sellada en capture_study (resultado NO negativo): "
    "vive en [0,+inf), no cambia de signo y leftOnTableR jamas supera el MFE; un mfeR no positivo "
    "no produce captura (hueco declarado).",
    "La concentracion usa la semana ISO de entryDay como cluster declarado; un ciclo sin fecha "
    "legible no se asigna a ninguna semana.",
    "La banda por cubo es la DISPERSION entre los K sorteos del venue (mismo dato, misma "
    "estrategia); NO es el bootstrap de ciclos ni la incertidumbre de mercado.",
    "n pequeno (los THESIS_EXIT son pocos ciclos): los cubos pueden quedar fragility; ninguna "
    "celda con n pequeno se cita como evidencia fuerte.",
    "La capa v6/v7 (correlacion DECISION<->CICLO) es OPT-IN: exige la costura --cycle-detail; sin ella "
    "decisionRoute = sin_traza y los booleanos quedan None (hueco declarado, nunca 0).",
    "decisionRoute NO es contrafactual: materializado = el stop disparo Y el tick produjo fill del "
    "ciclo; orden_creada_sin_fill (caso C) = el stop disparo y el tick ESTRENO un INTENT de salida "
    "del ciclo pero no hubo fill (falla la ejecucion aguas abajo); stop_evaluado_sin_orden (caso A) = "
    "el stop disparo y NO se creo orden (veto/corte del spine antes de _v2_reserve_exit); "
    "stop_no_evaluado = el toque ocurre pero el stop NO aparece en los motivos disparados. La capa "
    "v7 SEPARA A de C leyendo el INTENT durable por ciclo (orderCreated); stop_evaluado_sin_"
    "materializar queda SOLO como hueco declarado cuando no se pudo medir si hubo orden.",
    "orderCreated es POR CICLO: se LEE del diff de _v2_exit_orders antes/despues de auto_turn (solo "
    "lectura, no re-ejecuta la decision). dayOrders/dayFills siguen siendo senal de DIA y no votan en "
    "la ruta.",
    "D47-01 - FRONTERA DE LA SECUENCIA: los fotogramas se capturan al INICIO de cada tick D1, asi "
    "que la secuencia empieza en el PRIMER tick D1 COMPLETO POSTERIOR al dia de entrada "
    "(timelineStartsAt = first_full_tick_after_entry); el dia de ENTRADA NO tiene fotograma. La "
    "secuencia NO es una historia intradia desde el nacimiento y no se presenta como tal.",
    "La huella de decision (decisionReasons/decisionLabel/filledQty/survived/orderCreated) se LEE del "
    "estado ya producido por el worker tras auto_turn; no re-ejecuta la decision ni la altera "
    "(Delta motor = 0).",
    "CONFIRMED NO se emite: sigue reservado a evidencia PAPER.",
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


def _share(values: Sequence[float], predicate: Callable[[float], bool]) -> float | None:
    """Fracción de una muestra que cumple ``predicate`` (``None`` sin muestra; nunca ``0``)."""
    if not values:
        return None
    return sum(1 for value in values if predicate(value)) / len(values)


# ── Derivadas por ciclo (edad, captura, semana ISO) ──────────────────────────────


def _cycle_age_days(row: Mapping[str, Any]) -> int | None:
    """Días naturales ``entryDay``→``exitDay`` (``None`` si una fecha no es legible)."""
    entry = normalize_day(row.get("entryDay"))
    exit_day = normalize_day(row.get("exitDay"))
    if not entry or not exit_day:
        return None
    try:
        return (date.fromisoformat(exit_day) - date.fromisoformat(entry)).days
    except ValueError:
        return None


def _age_bucket(days: int | None) -> str:
    """Cubo de edad declarado (una fecha ilegible o negativa cae en ``unknown``; nunca se inventa)."""
    if days is None or days < 0:
        return "unknown"
    if days <= 3:
        return "1-3"
    if days <= 10:
        return "4-10"
    if days <= 30:
        return "11-30"
    return ">30"


def _iso_week(row: Mapping[str, Any]) -> str | None:
    """Semana ISO (``YYYY-Www``) del ``entryDay`` como cluster declarado (``None`` si ilegible)."""
    entry = normalize_day(row.get("entryDay"))
    if not entry:
        return None
    try:
        iso = date.fromisoformat(entry).isocalendar()
    except ValueError:
        return None
    return f"{iso.year:04d}-W{iso.week:02d}"


def _capture(row: Mapping[str, Any]) -> float | None:
    """Captura del MFE sobre el resultado NO negativo (``max(realizedR, 0) / mfeR``).

    Misma semántica sellada en ``capture_study`` (``v2.88.40``, ``A39-01``): vive en
    ``[0, +inf)`` y **no** cambia de signo; sólo se define con ``mfeR`` estrictamente
    positivo (sin premio previo la captura no está definida y es un hueco).
    """
    realized = finite_number(row.get("realizedR"))
    mfe = finite_number(row.get("mfeR"))
    if realized is None or mfe is None or mfe <= 0.0:
        return None
    return max(realized, 0.0) / mfe


def _left_on_table(row: Mapping[str, Any]) -> float | None:
    """R que quedó sobre la mesa (``max(mfeR - max(realizedR, 0), 0)``) con ``mfeR > 0``.

    Misma semántica sellada en ``capture_study``: acotada a ``[0, +inf)`` y **nunca**
    mayor que el MFE. Un cierre en pérdida deja TODO el MFE sobre la mesa, no
    ``mfeR + |pérdida|`` (que inflaría el premio perdido por el tamaño del fallo).
    """
    realized = finite_number(row.get("realizedR"))
    mfe = finite_number(row.get("mfeR"))
    if realized is None or mfe is None or mfe <= 0.0:
        return None
    return max(mfe - max(realized, 0.0), 0.0)


# ── Condición de la invalidación (capa v4): qué disparó el cierre por tesis ───────


def _invalidation_fold(present: Sequence[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Bloque de la CONDICIÓN de invalidación de un conjunto de ciclos (capa v4, declarada).

    Publica los anclajes EXACTOS leídos del estado congelado de la posición —el nivel
    (``invalidationLevelR``), el stop vigente al cierre (``currentStopAtExitR``) y cuánto se apretó
    por encima del nivel (``stopAboveLevelR``)—, el hecho APROXIMADO de si el peor adverso alcanzó
    el nivel (``maeVsLevelR``/``maeReachedLevel``, con el MAE reconstruido D1 como aproximación
    declarada), la discrepancia entre la base de R del ledger y el stop congelado de la posición
    (``stopBasisMismatchR``) y el histograma del token ``thesisExitCondition``. Un hueco es
    ``None``, nunca ``0``.
    """
    rows = [row for group in present for row in group]
    levels = [value for row in rows if (value := finite_number(row.get("invalidationLevelR"))) is not None]
    stops = [value for row in rows if (value := finite_number(row.get("currentStopAtExitR"))) is not None]
    above = [value for row in rows if (value := finite_number(row.get("stopAboveLevelR"))) is not None]
    mae_vs = [value for row in rows if (value := finite_number(row.get("maeVsLevelR"))) is not None]
    mismatch = [
        value for row in rows if (value := finite_number(row.get("stopBasisMismatchR"))) is not None
    ]
    equal = [
        bool(row.get("levelEqualsInitialStop"))
        for row in rows
        if isinstance(row.get("levelEqualsInitialStop"), bool)
    ]
    reached = [
        bool(row.get("maeReachedLevel"))
        for row in rows
        if isinstance(row.get("maeReachedLevel"), bool)
    ]
    conditions: dict[str, int] = {}
    for row in rows:
        token = str(row.get("thesisExitCondition") or "").strip() or INVALIDATION_CONDITION_SIN_GEOMETRIA
        conditions[token] = conditions.get(token, 0) + 1
    return {
        "cycles": len(rows),
        "measured": len(levels),
        "levelEqualsInitialStop": {
            "count": sum(equal),
            "measured": len(equal),
            "share": (sum(equal) / len(equal)) if equal else None,
        },
        "maeReachedLevel": {
            "count": sum(reached),
            "measured": len(reached),
            "share": (sum(reached) / len(reached)) if reached else None,
        },
        "invalidationLevelR": {"mean": _mean(levels), "median": _median(levels), "measured": len(levels)},
        "currentStopAtExitR": {"mean": _mean(stops), "median": _median(stops), "measured": len(stops)},
        "stopAboveLevelR": {"mean": _mean(above), "median": _median(above), "measured": len(above)},
        "maeVsLevelR": {"mean": _mean(mae_vs), "median": _median(mae_vs), "measured": len(mae_vs)},
        "stopBasisMismatchR": {
            "mean": _mean(mismatch),
            "median": _median(mismatch),
            "measured": len(mismatch),
            "shareNonZero": _share(mismatch, lambda value: value > 0.0),
        },
        "condition": {token: conditions[token] for token in sorted(conditions)},
    }


# ── Desambiguación THESIS_EXIT vs STOP (capa v5): por qué ruta se invalidó ────────

#: Orden declarado de las rutas de la parada (``byStopPath``); un hueco cae en ``unknown``.
STOP_PATHS: tuple[str, ...] = ("sin_cambio", "ratchet", "breakeven", "unknown")


def _boolean_block(values: Sequence[bool]) -> dict[str, Any]:
    """Recuento de un booleano MEDIDO (``share`` ``None`` sin muestra; nunca ``0`` inventado)."""
    return {
        "count": sum(values),
        "measured": len(values),
        "share": (sum(values) / len(values)) if values else None,
    }


def _stop_path(row: Mapping[str, Any]) -> str:
    """Ruta del STOP declarada: sin cambio, ratchet (subió sin break-even) o break-even.

    Un hueco (``stopChanged`` no medido) cae en ``unknown``: no se inventa que el stop se movió.
    """
    changed = row.get("stopChanged")
    if not isinstance(changed, bool):
        return "unknown"
    if not changed:
        return "sin_cambio"
    breakeven = row.get("breakevenReached")
    if isinstance(breakeven, bool) and breakeven:
        return "breakeven"
    return "ratchet"


def _disambiguation_fold(present: Sequence[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Bloque de la RUTA de invalidación de un conjunto de ciclos (capa v5, declarada).

    Publica el histograma de ``thesisExitRoute`` (``ruta_mark``/``ruta_mae``/``ruta_ambas``/
    ``sin_geometria``), su cruce con ``maeReachedLevel``, el primer día en que el MAE persistido
    alcanzó el nivel (``daysToFirstTouch``), y los booleanos que separan un stop sin tocar de uno
    ya ejecutado (``structuralStopCandidate``/``touchBeforeExit``/``stopChanged``/
    ``breakevenReached``/``stopAboveLevel``). Un hueco es ``None``, nunca ``0``.
    """
    rows = [row for group in present for row in group]
    routes: dict[str, int] = {}
    cross: dict[str, dict[str, int]] = {}
    for row in rows:
        token = str(row.get("thesisExitRoute") or "").strip() or THESIS_ROUTE_SIN_GEOMETRIA
        routes[token] = routes.get(token, 0) + 1
        bucket = cross.setdefault(token, {"reached": 0, "notReached": 0, "unknown": 0})
        reached = row.get("maeReachedLevel")
        if isinstance(reached, bool):
            bucket["reached" if reached else "notReached"] += 1
        else:
            bucket["unknown"] += 1

    def _bools(key: str) -> list[bool]:
        return [bool(row[key]) for row in rows if isinstance(row.get(key), bool)]

    def _nums(key: str) -> list[float]:
        return [value for row in rows if (value := finite_number(row.get(key))) is not None]

    days = [
        float(row["daysToFirstTouch"])
        for row in rows
        if isinstance(row.get("daysToFirstTouch"), int)
    ]
    min_marks = _nums("minMarkR")
    maes = _nums("persistedMaeR")
    mae_exit = _nums("persistedMaeAtExitR")
    return {
        "cycles": len(rows),
        "route": {token: routes[token] for token in sorted(routes)},
        "routeByMaeReached": {token: cross[token] for token in sorted(cross)},
        "structuralStopCandidate": _boolean_block(_bools("structuralStopCandidate")),
        "touchBeforeExit": _boolean_block(_bools("touchBeforeExit")),
        "stopChanged": _boolean_block(_bools("stopChanged")),
        "breakevenReached": _boolean_block(_bools("breakevenReached")),
        "stopAboveLevel": _boolean_block(_bools("stopAboveLevel")),
        "minMarkR": {"mean": _mean(min_marks), "median": _median(min_marks), "measured": len(min_marks)},
        "persistedMaeR": {"mean": _mean(maes), "median": _median(maes), "measured": len(maes)},
        "persistedMaeAtExitR": {
            "mean": _mean(mae_exit),
            "median": _median(mae_exit),
            "measured": len(mae_exit),
        },
        "daysToFirstTouch": {
            "mean": _mean(days),
            "median": _median(days),
            "measured": len(days),
        },
        "firstTouchMeasured": sum(1 for row in rows if row.get("firstTouchDay")),
    }


def _decision_correlation_fold(present: Sequence[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Bloque de la CORRELACIÓN DECISIÓN↔CICLO de un conjunto de ciclos (capa v6/v7, declarada).

    Publica el histograma de ``decisionRoute`` (``materializado``/``orden_creada_sin_fill``/
    ``stop_evaluado_sin_orden``/``stop_evaluado_sin_materializar``/``stop_no_evaluado``/``sin_toque``/
    ``sin_traza``), su cruce con ``structuralStopCandidate`` y los booleanos que separan «el decider
    evaluó el stop» (``stopEvaluatedOnTouch``) de «el decider corrió sin tocar el stop»
    (``deciderRanOnTouch``) y «el stop disparó sin materializar» (``stopFiredNotFilled``), más los
    días con toque del stop (``stopTouchDays``). En la capa v7 ``orden_creada_sin_fill`` (caso C) y
    ``stop_evaluado_sin_orden`` (caso A) están SEPARADOS; ``stop_evaluado_sin_materializar`` queda
    SÓLO como hueco (no se pudo medir si hubo orden). Declara la frontera de la secuencia
    (``timelineStartsAt``, ``D47-01``). Un hueco es ``None``, nunca ``0``.
    """
    rows = [row for group in present for row in group]
    routes: dict[str, int] = {}
    cross: dict[str, dict[str, int]] = {}
    for row in rows:
        token = str(row.get("decisionRoute") or "").strip() or DECISION_ROUTE_SIN_TRAZA
        routes[token] = routes.get(token, 0) + 1
        bucket = cross.setdefault(token, {"candidate": 0, "notCandidate": 0, "unknown": 0})
        candidate = row.get("structuralStopCandidate")
        if isinstance(candidate, bool):
            bucket["candidate" if candidate else "notCandidate"] += 1
        else:
            bucket["unknown"] += 1

    def _bools(key: str) -> list[bool]:
        return [bool(row[key]) for row in rows if isinstance(row.get(key), bool)]

    def _nums(key: str) -> list[float]:
        return [value for row in rows if (value := finite_number(row.get(key))) is not None]

    touch_days = _nums("stopTouchDays")
    return {
        "cycles": len(rows),
        "route": {token: routes[token] for token in sorted(routes)},
        "routeByStructuralStopCandidate": {token: cross[token] for token in sorted(cross)},
        "stopEvaluatedOnTouch": _boolean_block(_bools("stopEvaluatedOnTouch")),
        "deciderRanOnTouch": _boolean_block(_bools("deciderRanOnTouch")),
        "stopFiredNotFilled": _boolean_block(_bools("stopFiredNotFilled")),
        "stopTouchDays": {
            "mean": _mean(touch_days),
            "median": _median(touch_days),
            "measured": len(touch_days),
        },
        "timelineStartsAt": TIMELINE_START_FIRST_TICK_AFTER_ENTRY,
    }


# ── Plegado de un conjunto de ciclos (con dispersión entre sorteos + fragilidad) ──


def _fold(draw_rows: Sequence[Sequence[Mapping[str, Any]]], draws_total: int) -> dict[str, Any]:
    """Bloque de UN conjunto de ciclos: R bruto/neto, excursión, entrada y fragilidad.

    ``draw_rows`` es la lista —por sorteo del venue— de las filas del cubo. Un cubo ausente en un
    sorteo sencillamente no vota; nunca aporta un ``0``. La dispersión es ENTRE sorteos.
    """
    present = [list(rows) for rows in draw_rows if rows]
    cycles = sum(len(rows) for rows in present)

    gross_totals: list[float] = []
    gross_exps: list[float] = []
    hits: list[float] = []
    net_totals: list[float] = []
    net_exps: list[float] = []
    friction_means: list[float] = []
    mae_means: list[float] = []
    mfe_means: list[float] = []
    capture_means: list[float] = []
    left_means: list[float] = []
    adverse_means: list[float] = []
    slip_means: list[float] = []

    pooled_mae: list[float] = []
    pooled_mfe: list[float] = []
    pooled_capture: list[float] = []
    pooled_left: list[float] = []
    pooled_adverse: list[float] = []
    pooled_slip: list[float] = []

    measurement = {"COMPLETE": 0, "PARTIAL": 0, "UNKNOWN": 0}
    net_measured = 0
    net_unmeasured = 0
    cycles_per_draw: list[int] = []

    for rows in present:
        gross = [value for row in rows if (value := finite_number(row.get("realizedR"))) is not None]
        net = [value for row in rows if (value := finite_number(row.get("netRealizedR"))) is not None]
        fr = [value for row in rows if (value := finite_number(row.get("frictionR"))) is not None]
        mae = [value for row in rows if (value := finite_number(row.get("maeR"))) is not None]
        mfe = [value for row in rows if (value := finite_number(row.get("mfeR"))) is not None]
        capture = [value for row in rows if (value := _capture(row)) is not None]
        left = [value for row in rows if (value := _left_on_table(row)) is not None]
        adverse = [
            value for row in rows if (value := finite_number(row.get("entryAdverseR"))) is not None
        ]
        slip = [
            value for row in rows if (value := finite_number(row.get("entrySlippageBps"))) is not None
        ]
        for row in rows:
            key = str(row.get("frictionMeasurement") or "UNKNOWN")
            if key in measurement:
                measurement[key] += 1
        net_measured += len(net)
        net_unmeasured += len(gross) - len(net)
        if not gross:
            continue
        cycles_per_draw.append(len(gross))
        gross_totals.append(sum(gross))
        gross_exps.append(sum(gross) / len(gross))
        hits.append(sum(1 for value in gross if value > 0.0) / len(gross))
        if net:
            net_totals.append(sum(net))
            net_exps.append(sum(net) / len(net))
        if fr:
            friction_means.append(sum(fr) / len(fr))
        if mae:
            mae_means.append(sum(mae) / len(mae))
        if mfe:
            mfe_means.append(sum(mfe) / len(mfe))
        if capture:
            capture_means.append(sum(capture) / len(capture))
        if left:
            left_means.append(sum(left) / len(left))
        if adverse:
            adverse_means.append(sum(adverse) / len(adverse))
        if slip:
            slip_means.append(sum(slip) / len(slip))
        pooled_mae += mae
        pooled_mfe += mfe
        pooled_capture += capture
        pooled_left += left
        pooled_adverse += adverse
        pooled_slip += slip

    draws_with_cell = len(present)
    reasons: list[str] = []
    if draws_with_cell < MIN_DRAWS_FOR_BAND:
        reasons.append("insufficient_draws")
    if cycles_per_draw and min(cycles_per_draw) < MIN_CYCLES_FOR_SAMPLING:
        reasons.append("few_cycles_per_draw")
    if net_unmeasured:
        reasons.append("net_partial")

    return {
        "drawsWithCell": draws_with_cell,
        "drawsTotal": draws_total,
        "cycles": cycles,
        "realizedRGross": {
            "total": _dispersion(gross_totals),
            "expectancyR": _dispersion(gross_exps),
            "hitRate": _dispersion(hits),
        },
        "realizedRNet": {
            "total": _dispersion(net_totals),
            "expectancyR": _dispersion(net_exps),
            "cyclesMeasured": net_measured,
            "cyclesUnmeasured": net_unmeasured,
        },
        "frictionR": {"mean": _dispersion(friction_means)},
        "frictionMeasurement": measurement,
        "excursion": {
            "maeR": {
                "mean": _mean(pooled_mae),
                "median": _median(pooled_mae),
                "measured": len(pooled_mae),
                "meanAcrossDraws": _dispersion(mae_means),
            },
            "mfeR": {
                "mean": _mean(pooled_mfe),
                "median": _median(pooled_mfe),
                "measured": len(pooled_mfe),
                "meanAcrossDraws": _dispersion(mfe_means),
            },
            "capture": {
                "mean": _mean(pooled_capture),
                "median": _median(pooled_capture),
                "measured": len(pooled_capture),
                "meanAcrossDraws": _dispersion(capture_means),
            },
            "leftOnTableR": {
                "mean": _mean(pooled_left),
                "median": _median(pooled_left),
                "measured": len(pooled_left),
                "meanAcrossDraws": _dispersion(left_means),
            },
        },
        "entryQuality": {
            "adverseR": {
                "mean": _mean(pooled_adverse),
                "median": _median(pooled_adverse),
                "shareBelowHalfR": _share(pooled_adverse, lambda value: value < ENTRY_ADVERSE_HALF_R),
                "shareBelowOneR": _share(pooled_adverse, lambda value: value < ENTRY_ADVERSE_ONE_R),
                "measured": len(pooled_adverse),
                "meanAcrossDraws": _dispersion(adverse_means),
            },
            "slippageBps": {
                "mean": _mean(pooled_slip),
                "median": _median(pooled_slip),
                "measured": len(pooled_slip),
                "meanAcrossDraws": _dispersion(slip_means),
            },
        },
        "invalidation": _invalidation_fold(present),
        "disambiguation": _disambiguation_fold(present),
        "decisionCorrelation": _decision_correlation_fold(present),
        "fragility": {"fragile": bool(reasons), "reasons": reasons},
    }


# ── Selección y agrupación ───────────────────────────────────────────────────────


def _thesis_rows(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Ciclos de UN sorteo con mecanismo ``THESIS_EXIT`` (los demás no votan)."""
    return [
        row
        for row in (ledger.get("cycles") or ())
        if isinstance(row, Mapping) and str(row.get("exitMechanism") or "") == MECHANISM
    ]


def _fold_dimension(
    per_draw_rows: Sequence[Sequence[Mapping[str, Any]]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    label_key: str,
    draws_total: int,
    order: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Una fila por etiqueta con su bloque plegado (dispersión entre sorteos + fragilidad)."""
    labels: set[str] = set()
    per_draw_grouped: list[dict[str, list[Mapping[str, Any]]]] = []
    for rows in per_draw_rows:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(key_fn(row), []).append(row)
        per_draw_grouped.append(grouped)
        labels.update(grouped)

    def _order_key(label: str) -> tuple[int, str]:
        if order is not None and label in order:
            return (list(order).index(label), "")
        return (len(order) if order is not None else 0, str(label))

    rendered: list[dict[str, Any]] = []
    for label in sorted(labels, key=_order_key):
        per_draw_lists = [grouped.get(label, []) for grouped in per_draw_grouped]
        block = _fold(per_draw_lists, draws_total)
        block[label_key] = label
        rendered.append(block)
    return rendered


def _coverage_from(per_draw_rows: Sequence[Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Cobertura mínima: años presentes, ciclos THESIS_EXIT y fricción COMPLETE medida."""
    years: list[str] = []
    seen: set[str] = set()
    cycles = 0
    with_detail = 0
    for rows in per_draw_rows:
        for row in rows:
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
        "drawsTotal": len(per_draw_rows),
        "cyclesTotal": cycles,
        "cyclesWithCompleteFriction": with_detail,
        "detailCaptured": with_detail > 0,
    }


# ── Presentación auxiliar: motivos crudos y concentración ────────────────────────


def _raw_reason_tokens(all_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Frecuencia del motivo CRUDO por ciclo (su token colapsado; nunca se inventa)."""
    counts: dict[str, int] = {}
    for row in all_rows:
        token = str(row.get("exitReason") or "").strip() or "SIN_MECANISMO"
        counts[token] = counts.get(token, 0) + 1
    return {token: counts[token] for token in sorted(counts)}


def _top_share(counter: Mapping[str, int], total: int) -> tuple[str | None, float | None]:
    """Clave más frecuente y su cuota (empate resuelto por orden alfabético; ``None`` sin muestra)."""
    if not counter or total <= 0:
        return None, None
    top = max(sorted(counter), key=lambda key: counter[key])
    return top, counter[top] / total


def _concentration(all_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Concentración declarada: símbolos distintos y clusters (top símbolo / top semana ISO)."""
    total = len(all_rows)
    symbols: dict[str, int] = {}
    weeks: dict[str, int] = {}
    for row in all_rows:
        symbol = str(row.get("symbol") or "").strip()
        if symbol:
            symbols[symbol] = symbols.get(symbol, 0) + 1
        week = _iso_week(row)
        if week:
            weeks[week] = weeks.get(week, 0) + 1
    top_symbol, top_symbol_share = _top_share(symbols, total)
    top_week, top_week_share = _top_share(weeks, total)
    return {
        "distinctSymbols": len(symbols),
        "topSymbol": top_symbol,
        "topSymbolShare": top_symbol_share,
        "topWeek": top_week,
        "topWeekShare": top_week_share,
    }


# ── Artefacto canónico ───────────────────────────────────────────────────────────


def build_thesis_exit_artifact(
    *,
    draw_ledgers: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Payload canónico del quirófano ``THESIS_EXIT`` (puro y determinista).

    ``draw_ledgers`` son los ``K`` ledgers de ciclos (``dia-d-multi-cycle-ledger-v7``). Selecciona
    los ciclos cerrados por invalidación de tesis y los pliega por **estrategia**, **dirección**,
    **año**, **régimen**, **régimen operativo** y **cubo de edad**, cada uno con su **dispersión
    entre sorteos** y su **fragilidad** declarada. Añade la geometría (MAE/MFE, captura,
    ``leftOnTableR``), la calidad de entrada, el coste (bruto/neto/suelo), la **condición de la
    invalidación** (capa v4: nivel congelado, stop vigente al cierre, alcance del peor adverso),
    la **desambiguación** de la ruta (capa v5) y la **correlación DECISIÓN↔CICLO** (capa v6:
    ``decisionRoute`` y la huella de decisión del toque del stop) con la **existencia de orden**
    (capa v7: ``orderCreated`` separa A de C), los motivos crudos y la concentración. Un hueco queda
    ``None``, nunca ``0``.
    """
    ordered = list(draw_ledgers or ())
    draws_total = len(ordered)
    per_draw_rows = [_thesis_rows(ledger) for ledger in ordered]
    all_rows = [row for rows in per_draw_rows for row in rows]

    resolved_coverage = dict(coverage) if coverage is not None else _coverage_from(per_draw_rows)
    global_block = _fold(per_draw_rows, draws_total)
    global_block["label"] = MECHANISM

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "readOnly": True,
        "basis": "entryDay",
        "mechanism": MECHANISM,
        "draws": draws_total,
        "axes": [
            "strategy",
            "direction",
            "year",
            "regime",
            "operationalRegime",
            "ageBucket",
            "excursion",
            "entry",
            "cost",
            "invalidation",
            "disambiguation",
            "decisionCorrelation",
            "route",
            "stopPath",
            "decisionRoute",
        ],
        "coverage": resolved_coverage,
        "global": global_block,
        "byStrategy": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("strategyVersion") or "sin_version").strip() or "sin_version",
            label_key="strategy",
            draws_total=draws_total,
        ),
        "byDirection": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("direction") or "").strip() or "unknown",
            label_key="direction",
            draws_total=draws_total,
        ),
        "byYear": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("year") or "").strip() or "sin_ano",
            label_key="year",
            draws_total=draws_total,
        ),
        "byRegime": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("regime") or "").strip() or "sin_regimen",
            label_key="regime",
            draws_total=draws_total,
        ),
        "byOperationalRegime": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("operationalRegime") or "").strip() or "sin_regimen_operativo",
            label_key="operationalRegime",
            draws_total=draws_total,
        ),
        "byAgeBucket": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: _age_bucket(_cycle_age_days(row)),
            label_key="ageBucket",
            draws_total=draws_total,
            order=AGE_BUCKETS,
        ),
        "byRoute": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("thesisExitRoute") or "").strip()
            or THESIS_ROUTE_SIN_GEOMETRIA,
            label_key="route",
            draws_total=draws_total,
        ),
        "byStopPath": _fold_dimension(
            per_draw_rows,
            key_fn=_stop_path,
            label_key="stopPath",
            draws_total=draws_total,
            order=STOP_PATHS,
        ),
        "byDecisionRoute": _fold_dimension(
            per_draw_rows,
            key_fn=lambda row: str(row.get("decisionRoute") or "").strip()
            or DECISION_ROUTE_SIN_TRAZA,
            label_key="decisionRoute",
            draws_total=draws_total,
            order=DECISION_ROUTES,
        ),
        "rawReasonTokens": _raw_reason_tokens(all_rows),
        "concentration": _concentration(all_rows),
        "recompileNote": (
            "Este artefacto consume los ciclos con exitMechanism=THESIS_EXIT del ledger v7: exige "
            "que el ledger traiga el detalle (--cycle-detail), la identidad de estrategia/direccion, "
            "la geometria de la invalidacion (invalidationByCycle), la secuencia (cycleTimeline) y la "
            "huella de decision (decisionReasons/decisionLabel/filledQty/survived/orderCreated). Sin "
            "detalle, los ciclos quedan SIN_MECANISMO/la invalidation y la decision quedan sin medir "
            "(se declara, no se rellena)."
        ),
        "meta": {str(key): value for key, value in (meta or {}).items()},
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


__all__ = [
    "AGE_BUCKETS",
    "DEFAULT_LIMITS",
    "ENTRY_ADVERSE_HALF_R",
    "ENTRY_ADVERSE_ONE_R",
    "KIND",
    "MECHANISM",
    "SCHEMA_VERSION",
    "STOP_PATHS",
    "build_thesis_exit_artifact",
]
