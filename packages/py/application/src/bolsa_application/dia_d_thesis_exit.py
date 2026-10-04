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
motor. **NO** responde a *por qué* se invalidó la tesis: el journal sólo publica el token colapsado
``thesis_exit`` (ver límites).

Ejes de la descomposición
-------------------------
* **dónde** — ``byStrategy`` / ``byDirection`` / ``byYear`` / ``byRegime`` / ``byOperationalRegime``.
* **cuándo se agotó** — ``byAgeBucket`` (días naturales ``entryDay``→``exitDay``, en cubos duros).
* **cómo se movió** — excursión media/mediana ``maeR``/``mfeR``, captura del MFE y ``leftOnTableR``.
* **cómo entró** — excursión adversa temprana + slippage señal→ejecución.
* **cuánto costó** — fricción en ``R`` y ``R`` neto (suelo declarado si falta fricción ``COMPLETE``).
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
from bolsa_application.dia_d_multi_sampling import MIN_CYCLES_FOR_SAMPLING
from bolsa_application.dia_d_multi_uncertainty import MIN_DRAWS_FOR_BAND

#: Versión del esquema del artefacto. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-thesis-exit-v1"

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
    "El motivo crudo de estos ciclos es el token COLAPSADO 'thesis_exit': no revela la condicion "
    "de invalidacion (recuperarla exigiria capturar el contexto del plan, que hoy no llega al "
    "journal); es una fase futura, no esta.",
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

    ``draw_ledgers`` son los ``K`` ledgers de ciclos (``dia-d-multi-cycle-ledger-v3``). Selecciona
    los ciclos cerrados por invalidación de tesis y los pliega por **estrategia**, **dirección**,
    **año**, **régimen**, **régimen operativo** y **cubo de edad**, cada uno con su **dispersión
    entre sorteos** y su **fragilidad** declarada. Añade la geometría (MAE/MFE, captura,
    ``leftOnTableR``), la calidad de entrada, el coste (bruto/neto/suelo), los motivos crudos y la
    concentración. Un hueco queda ``None``, nunca ``0``.
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
        "rawReasonTokens": _raw_reason_tokens(all_rows),
        "concentration": _concentration(all_rows),
        "recompileNote": (
            "Este artefacto consume los ciclos con exitMechanism=THESIS_EXIT del ledger v3: exige "
            "que el ledger traiga el detalle (--cycle-detail) y la identidad de estrategia/direccion. "
            "Sin detalle, los ciclos quedan SIN_MECANISMO y no entran aqui (se declara, no se rellena)."
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
    "build_thesis_exit_artifact",
]
