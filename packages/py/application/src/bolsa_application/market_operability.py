"""V2.77 · AUTO-MATERIAL-5 — journal de OPERABILIDAD del forward PAPER (puro, sin I/O).

Qué resuelve: ``v2.76`` demostró que el forward PAPER ya recibe **precio** y **régimen** de
mercado por el único seam del motor congelado, y que el bloqueo restante está localizado (el
agregado de régimen más conservador puede vetar todo el universo LONG; ``TOP_N`` añade una
segunda compuerta). Pero ese veredicto vivía **disperso** en el JSON de cada corrida y no se
podía leer como una **serie diaria**: no había forma de responder a la pregunta que decide si
la falta de material es **estadística** o **estructuralmente causada por el gobernador**.

Esta pieza traduce el JSON del runner a UNA fila diaria y reparte cada **veto** en su familia
DECLARADA (``regime`` / ``governor`` / ``liquidity`` / ``risk`` / ``top_n`` / ``data`` /
``other``), separando el hecho de MERCADO (``regime_invalid``) del PERMISO del gobernador
(``governor_exit_only``/``governor_halted``) y del tope de EVALUACIÓN (``top_n_excluded``).

Desde ``v2.79`` (``AUTO-MATERIAL-7``) el censo es de **decisiones de ENTRADA**: el histograma sólo
cuenta los eventos ``auto_entry_decision`` (``ENTRY_DECISION_EVENT``) y los motivos de GESTIÓN DE
POSICIÓN (``POSITION_JOURNAL_EVENTS``: protección, materialización, reserva, ciclo de vida…) se
**publican aparte** (``positionEventByCode``), porque un evento de gestión no es una entrada y
contarlo inflaba ``vetoCounted`` (``P3-6``/``H-1``). Ninguna entrada se descarta.

Qué NO hace (reglas duras del repo):

* **No** decide: no toca el motor, el gobernador ni ``TOP_N``; no recalcula el gate ni cambia
  un umbral. Sólo CLASIFICA lo que el motor ya declaró.
* **No** inventa medición: un dato ausente se declara ausente (``None``), nunca ``0``. Un
  código de motivo desconocido cae en ``other`` y se **cuenta igual** (jamás se descarta).
* **No** deduce ``pairActive`` de ``pairCapable``: son dos estados distintos (arquitectura
  lista vs. dos versiones operando) y la nomenclatura los mantiene separados.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_analytics.cognitive.market_regime_gate import (
    map_trial_regime,
    regime_allows_entry_for,
)
from bolsa_analytics.cognitive.opportunity_ranker import TOP_N_EXCLUDED
from bolsa_application.auto_reason_codes import (
    ADAPTIVE_STRATEGY_PAUSED,
    DAY_EXIT_REASONS,
    OPTIMIZER_ENUMERATION_CAP_EXCEEDED,
    OPTIMIZER_LIQUIDITY_BELOW_MINIMUM,
    OPTIMIZER_LIQUIDITY_UNKNOWN,
    OPTIMIZER_NOT_SELECTED,
    OPTIMIZER_REASONS,
    OPTIMIZER_SECTOR_UNMEASURED,
    POSITION_ATTRIBUTION_REASONS,
    POSITION_SKIP_REASONS,
    RESERVATION_ALREADY_LIVE,
    RESERVATION_UNMEASURABLE,
)
from bolsa_application.market_price_snapshot import PRICE_SOURCE_CLOSE, PRICE_SOURCE_LIVE

__all__ = [
    "BUCKET_DATA",
    "BUCKET_GOVERNOR",
    "BUCKET_LIQUIDITY",
    "BUCKET_OTHER",
    "BUCKET_REGIME",
    "BUCKET_RISK",
    "BUCKET_TOP_N",
    "ENTRY_DECISION_EVENT",
    "NON_VETO_REASON_CODES",
    "OPERABILITY_BUCKETS",
    "POSITION_JOURNAL_EVENTS",
    "STATE_NO_SIGNAL",
    "STATE_OPERATED",
    "STATE_UNKNOWN",
    "STATE_VETOED",
    "VETO_BUCKET_BY_REASON",
    "build_operability_record",
    "classify_veto_reasons",
    "collect_journal_reasons",
    "operability_state",
    "pair_active",
    "pair_capable",
    "parse_journal_reasons",
    "render_operability_table",
    "split_journal_reasons",
    "symbols_operable",
    "veto_counted",
]

# ── Familias de no-operación (el vocabulario con el que se lee la tabla) ───────────────────────

BUCKET_REGIME = "regime"
BUCKET_GOVERNOR = "governor"
BUCKET_LIQUIDITY = "liquidity"
BUCKET_RISK = "risk"
BUCKET_TOP_N = "top_n"
BUCKET_DATA = "data"
BUCKET_OTHER = "other"

#: Todas las familias, en orden estable (la tabla las publica aunque estén a cero).
OPERABILITY_BUCKETS: tuple[str, ...] = (
    BUCKET_REGIME,
    BUCKET_GOVERNOR,
    BUCKET_LIQUIDITY,
    BUCKET_RISK,
    BUCKET_TOP_N,
    BUCKET_DATA,
    BUCKET_OTHER,
)

#: Estado primario de un día (separa el operar del no operar y el PORQUÉ del no operar).
STATE_OPERATED = "operated"
STATE_VETOED = "vetoed"
STATE_NO_SIGNAL = "no_signal"
STATE_UNKNOWN = "unknown"

# ── Población del censo (V2.79): una entrada = una decisión ────────────────────────────────────
#: Evento del journal V2 que representa una **DECISIÓN DE ENTRADA** (un veto o una aprobación).
#: Es la ÚNICA población que el censo de vetos puede contar: el histograma por familias mide por
#: qué NO se entró, y una decisión de gestión de una posición viva no es una entrada.
ENTRY_DECISION_EVENT = "auto_entry_decision"

#: Eventos de **GESTIÓN DE POSICIÓN** del journal V2 (decisión de gestión, salto de gestión y
#: evento rico de gestión). Sus motivos son ATRIBUCIONES de una posición viva: se publican por su
#: canal propio (``positionEventByCode``) y **jamás** engordan ``vetoCounted`` (``P3-6``/``H-1``).
#: El literal de cada evento vive en su productor (``auto_v2_entry``/``auto_investment_system``);
#: aquí se fija el contrato del LECTOR y un test lo pinea contra el productor real.
POSITION_JOURNAL_EVENTS: frozenset[str] = frozenset(
    {"auto_position_management", "auto_position_decision", "auto_position_skip"}
)

#: Reparto de los motivos del **optimizador** de cartera (V2.44/AUTO-4). Son decisiones de ENTRADA
#: (la candidata se evaluó y no entró en la combinación elegida, o el optimizador no llegó a
#: decidir). El valor por defecto es ``risk`` (compuertas de cantidad de riesgo y mediciones
#: fallidas, misma convención que ``risk_measurement_*``); las excepciones se declaran aquí para no
#: mezclar liquidez (``liquidity``), dato no verificable (``data``) ni tope de evaluación (``top_n``).
_OPTIMIZER_BUCKET_OVERRIDES: dict[str, str] = {
    OPTIMIZER_NOT_SELECTED: BUCKET_TOP_N,
    OPTIMIZER_ENUMERATION_CAP_EXCEEDED: BUCKET_TOP_N,
    OPTIMIZER_LIQUIDITY_UNKNOWN: BUCKET_LIQUIDITY,
    OPTIMIZER_LIQUIDITY_BELOW_MINIMUM: BUCKET_LIQUIDITY,
    OPTIMIZER_SECTOR_UNMEASURED: BUCKET_DATA,
}

#: Familia declarada de cada código de motivo. Los literales de decisión son los del dueño único
#: (``portfolio_decision_engine.DecisionReasonCode`` / ``_NO_TRADE_REASONS``); ``top_n_excluded``
#: se importa del suyo (``opportunity_ranker``) para que no pueda divergir. Un código que NO esté
#: aquí cae en ``other`` y se cuenta igual: la contabilidad nunca pierde una entrada.
VETO_BUCKET_BY_REASON: dict[str, str] = {
    # Hecho de MERCADO: el régimen operativo (long-only) no admite entrada.
    "regime_invalid": BUCKET_REGIME,
    # Permiso del gobernador (V2.43/AUTO-3): AUTO tiene prohibido abrir. Es DISTINTO del hecho
    # de mercado: el journal debe poder separar "el mercado está bajista" de "AUTO no puede abrir".
    "governor_exit_only": BUCKET_GOVERNOR,
    "governor_halted": BUCKET_GOVERNOR,
    # Liquidez / capacidad del instrumento.
    "liquidity_insufficient": BUCKET_LIQUIDITY,
    "liquidity_unknown": BUCKET_LIQUIDITY,
    # Riesgo, edge, concentración, correlación, R/R, medición, plan y reserva: compuertas de
    # CANTIDAD de riesgo (el instrumento podía operar, el presupuesto no lo autorizó).
    "edge_below_threshold": BUCKET_RISK,
    "risk_reward_below_threshold": BUCKET_RISK,
    "risk_budget_exceeded": BUCKET_RISK,
    "concentration_exceeded": BUCKET_RISK,
    "correlation_conflict": BUCKET_RISK,
    "correlation_unknown": BUCKET_RISK,
    "risk_measurement_partial": BUCKET_RISK,
    "risk_measurement_unknown": BUCKET_RISK,
    "exposure_measurement_partial": BUCKET_RISK,
    "exposure_measurement_unknown": BUCKET_RISK,
    "plan_invalid": BUCKET_RISK,
    "reservation_failed": BUCKET_RISK,
    "open_orders_unmeasurable": BUCKET_RISK,
    # Tope de EVALUACIÓN (V2.40.4): la candidata ni se evaluó. No es un veto de mercado.
    TOP_N_EXCLUDED: BUCKET_TOP_N,
    # Dato no verificable (fail-closed): sector, frescura, geometría de riesgo.
    "sector_unknown": BUCKET_DATA,
    "sector_conflicting": BUCKET_DATA,
    "sector_stale": BUCKET_DATA,
    "sector_exposure_unverifiable": BUCKET_DATA,
    "stale_data": BUCKET_DATA,
    "atr_unknown": BUCKET_DATA,
    # V2.79 — motivos del OPTIMIZADOR y del ADAPTIVE: son decisiones de ENTRADA (la candidata se
    # evaluó y no entró, o su estrategia está pausada) ⇒ vetos con familia, nunca ``other``.
    **{code: _OPTIMIZER_BUCKET_OVERRIDES.get(code, BUCKET_RISK) for code in OPTIMIZER_REASONS},
    ADAPTIVE_STRATEGY_PAUSED: BUCKET_RISK,
    # V2.79 — vetos fail-closed de la espina de reserva (aperturas vetadas): NO son atribuciones.
    RESERVATION_UNMEASURABLE: BUCKET_RISK,
    RESERVATION_ALREADY_LIVE: BUCKET_RISK,
    # Sin familia propia declarada: se cuenta igual (nunca se descarta).
    "position_exists": BUCKET_OTHER,
}

#: Códigos que el journal estampa y NO son vetos: son ATRIBUCIONES de una decisión
#: (``approved``) o de la gestión de una posición viva (motivos de SALIDA, saltos de gestión y el
#: resto de eventos de POSICIÓN: materialización, reserva y ciclo de vida). No pueden engordar
#: ``vetoCounted`` (``P3-6``/``H-1``): un día que SÍ opera lleva ``approved`` y ``risk_exit`` en el
#: MISMO array de motivos y, sin esta separación, caen en ``other`` y se contarían como vetos. Los
#: literales se leen de su dueño (``auto_reason_codes``): aquí no se duplica ninguno.
NON_VETO_REASON_CODES: frozenset[str] = frozenset(
    {"approved", *DAY_EXIT_REASONS, *POSITION_SKIP_REASONS, *POSITION_ATTRIBUTION_REASONS}
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Vista de mapping o vacío (un tipo inesperado no revienta la lectura)."""
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> list[Any]:
    """Lista o vacío (un JSON de forma inesperada no revienta la lectura)."""
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_str_mapping(value: Any) -> dict[str, str]:
    return {str(key): str(item) for key, item in _as_mapping(value).items()}


def _maybe_int(value: Any) -> int | None:
    """Entero o ``None`` (un dato ausente se declara ausente, nunca ``0``)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _count(value: Any) -> int:
    number = _maybe_int(value)
    return number if number is not None and number > 0 else 0


def _entry_payload(entry: Any) -> Mapping[str, Any]:
    """Payload de una entrada del journal (objeto con ``payload`` o mapping), o vacío."""
    payload = entry.get("payload") if isinstance(entry, Mapping) else getattr(entry, "payload", None)
    return payload if isinstance(payload, Mapping) else {}


def collect_journal_reasons(
    entries: Sequence[Any], *, events: frozenset[str] | None = None
) -> dict[str, int]:
    """Agrega los ``reasonCodes`` de los eventos pedidos, sin perder ningún conteo.

    Esta es la ÚNICA puerta por la que se decide **qué población entra en el censo** (``H-1``): con
    ``events`` fijado al evento de ENTRADA, el histograma mide sólo decisiones de entrada y un
    evento de gestión de posición no puede inflar ``vetoCounted``. Con ``events=None`` agrega
    TODAS las entradas (lectura tolerante de filas antiguas sin ``event`` declarado). Una entrada
    con forma inesperada o un motivo vacío se ignora; ningún conteo se descarta.
    """
    counts: dict[str, int] = {}
    for entry in entries or ():
        payload = _entry_payload(entry)
        if events is not None and str(payload.get("event") or "") not in events:
            continue
        for reason in _as_sequence(payload.get("reasonCodes")):
            key = str(reason or "").strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    return counts


def parse_journal_reasons(entries: Sequence[Any]) -> dict[str, int]:
    """Convierte ``["regime_invalid:40", "top_n_excluded:24"]`` en ``{código: conteo}``.

    Acepta el sufijo ``:N`` (el formato del runner) y un código suelto (cuenta 1). Un token
    vacío se ignora; un conteo ilegible cuenta 1 en vez de perderse.
    """
    counts: dict[str, int] = {}
    for entry in entries:
        text = str(entry or "").strip()
        if not text:
            continue
        code, separator, raw_count = text.partition(":")
        code = code.strip()
        if not code:
            continue
        count = _maybe_int(raw_count) if separator else None
        counts[code] = counts.get(code, 0) + (count if count is not None and count > 0 else 1)
    return counts


def split_journal_reasons(
    reasons: Mapping[str, int],
) -> tuple[dict[str, int], dict[str, int]]:
    """Separa los VETOS de las ATRIBUCIONES (``approved`` / salidas / saltos de gestión).

    El journal V2 estampa los motivos de la ENTRADA y de la SALIDA en el mismo array: una
    decisión ``approved`` y una salida ``risk_exit`` NO son vetos de entrada. Clasificarlas
    como tales infla ``vetoCounted`` (``P3-6``) y haría fallar el instrumento precisamente en
    los días que SÍ operan. Devuelve ``(veto_reasons, non_veto_reasons)``; un código
    desconocido NO es no-veto: va al histograma de vetos y cae en ``other`` (nunca se
    descarta: la contabilidad no puede perder una entrada).
    """
    veto: dict[str, int] = {}
    non_veto: dict[str, int] = {}
    for raw_code, raw_count in reasons.items():
        code = str(raw_code or "").strip()
        count = _count(raw_count)
        if not code or count <= 0:
            continue
        if code in NON_VETO_REASON_CODES:
            non_veto[code] = non_veto.get(code, 0) + count
        else:
            veto[code] = veto.get(code, 0) + count
    return veto, non_veto


def classify_veto_reasons(reasons: Mapping[str, int]) -> dict[str, dict[str, int]]:
    """Reparte cada código de motivo en su familia declarada.

    Devuelve SIEMPRE las siete familias (aunque estén vacías) para que la tabla sea estable. Un
    código sin familia conocida cae en ``other`` y se conserva: una entrada del journal no puede
    desaparecer de la contabilidad (fail-closed de la medición).
    """
    buckets: dict[str, dict[str, int]] = {bucket: {} for bucket in OPERABILITY_BUCKETS}
    for raw_code, raw_count in reasons.items():
        code = str(raw_code or "").strip()
        count = _count(raw_count)
        if not code or count <= 0:
            continue
        bucket = VETO_BUCKET_BY_REASON.get(code, BUCKET_OTHER)
        buckets[bucket][code] = buckets[bucket].get(code, 0) + count
    return buckets


def veto_counted(buckets: Mapping[str, Mapping[str, int]]) -> int:
    """Total de vetos contabilizados (la suma de las familias; debe cuadrar con el journal)."""
    return sum(sum(int(n) for n in bucket.values()) for bucket in buckets.values())


def symbols_operable(market_regime: Mapping[str, Any]) -> int | None:
    """Cuántos símbolos del watch admitirían entrada LONG por SÍ MISMOS (o ``None`` si no medible).

    Es la métrica que expone la tensión del gobernador conservador: con el agregado en
    ``BEAR_TREND`` TODAS las entradas están vetadas, aunque varios símbolos estén en ``range`` o
    ``trend_up``. Prefiere ``bySymbol`` (el detalle real); si falta, agrega ``counts``. Sin
    ninguno de los dos, devuelve ``None`` (no medido): jamás se publica un ``0`` inventado.
    """
    by_symbol = _as_str_mapping(market_regime.get("bySymbol"))
    if by_symbol:
        return sum(
            1 for label in by_symbol.values() if regime_allows_entry_for(map_trial_regime(label), "long")
        )
    counts = _as_mapping(market_regime.get("counts"))
    if counts:
        total = 0
        for label, count in counts.items():
            if regime_allows_entry_for(map_trial_regime(str(label)), "long"):
                total += _count(count)
        return total
    return None


def pair_capable(evidence: Mapping[str, Any]) -> bool:
    """El par A/B es POSIBLE: el universo admite repartirse en dos tramos y enrutarse.

    Es la arquitectura lista, NO la operación: con ``pairCapable=true`` y ``pairActive=false`` el
    sistema tiene el mecanismo pero sólo una versión operando (se declara, no se disfraza).
    """
    if "pairCapable" in evidence:
        return bool(evidence.get("pairCapable"))
    watch_size = _maybe_int(evidence.get("watchSize"))
    if watch_size is not None:
        return watch_size >= 2
    return len(_as_sequence(evidence.get("watchA"))) + len(_as_sequence(evidence.get("watchB"))) >= 2


def pair_active(evidence: Mapping[str, Any]) -> bool:
    """El par A/B está OPERANDO: hay segunda versión (ACTIVE) atribuida a su tramo del watch."""
    if "pairActive" in evidence:
        return bool(evidence.get("pairActive"))
    if "pairAvailable" in evidence:  # alias previo (v2.76): se acepta sin renombrar la lectura.
        return bool(evidence.get("pairAvailable"))
    return bool(
        evidence.get("secondaryActive")
        and str(evidence.get("versionB") or "").strip()
        and _as_sequence(evidence.get("watchB"))
    )


def _price_source_counts(value: Any) -> dict[str, int]:
    """Reparto de procedencia del precio (``live``/``close``/``missing``) desde ``priceSources``."""
    counts = {"live": 0, "close": 0, "missing": 0}
    for source in _as_mapping(value).values():
        text = str(source)
        if text == PRICE_SOURCE_LIVE:
            counts["live"] += 1
        elif text == PRICE_SOURCE_CLOSE:
            counts["close"] += 1
        else:
            counts["missing"] += 1
    return counts


def operability_state(record: Mapping[str, Any]) -> str:
    """Estado primario del día a partir de la fila.

    Regla fail-closed: la AUSENCIA de medición gana siempre. Un registro vacío, o uno cuyo
    payload no trae ``turnTotals`` (truncado/malformado), se declara ``unknown`` —"no medido"—
    y NUNCA ``no_signal`` (que es el hecho más tranquilizador y sólo puede afirmarse cuando el
    motor no produjo ni propuestas ni vetos). Un día con vetos es ``vetoed``: así no se puede
    leer "no hay señal" donde en realidad hubo un veto de régimen o de ``TOP_N``.
    """
    if not record or not bool(record.get("measured", True)):
        return STATE_UNKNOWN
    if "proposals" not in record and "vetoes" not in record:
        return STATE_UNKNOWN
    if _count(record.get("fills")) > 0 or _count(record.get("closed")) > 0:
        return STATE_OPERATED
    if _count(record.get("proposals")) == 0 and _count(record.get("vetoes")) == 0:
        return STATE_NO_SIGNAL
    return STATE_VETOED


def build_operability_record(evidence: Mapping[str, Any], *, day: str) -> dict[str, Any]:
    """Traduce el JSON de una corrida del runner a UNA fila diaria de operabilidad."""
    market_regime = _as_mapping(evidence.get("marketRegime"))
    totals = _as_mapping(evidence.get("turnTotals"))
    sample = _as_mapping(evidence.get("sample"))
    reasons = parse_journal_reasons(_as_sequence(evidence.get("journalReasons")))
    position_reasons = parse_journal_reasons(_as_sequence(evidence.get("positionEventReasons")))
    veto_reasons, non_veto_reasons = split_journal_reasons(reasons)
    buckets = classify_veto_reasons(veto_reasons)
    top_codes = sorted(
        ((code, count) for bucket in buckets.values() for code, count in bucket.items()),
        key=lambda item: (-item[1], item[0]),
    )
    record: dict[str, Any] = {
        "day": str(day),
        "measured": bool(totals),
        "regime": str(market_regime.get("aggregateTrialRegime") or ""),
        "operationalRegime": str(market_regime.get("operationalRegime") or ""),
        "entriesAllowedLong": bool(market_regime.get("entriesAllowedLong")),
        "watchSize": _maybe_int(evidence.get("watchSize")),
        "symbolsOperable": symbols_operable(market_regime),
        "decided": _count(totals.get("decided")),
        "proposals": _count(totals.get("proposals")),
        "vetoes": _count(totals.get("vetoes")),
        "fills": _count(totals.get("fills")),
        "orders": _count(totals.get("orders")),
        "opened": _count(totals.get("opened")),
        "closed": _count(totals.get("closed")),
        "measurableCycles": _count(sample.get("measurableCycles")),
        "vetoByBucket": buckets,
        "vetoCounted": veto_counted(buckets),
        "nonVetoByCode": non_veto_reasons,
        "nonVetoCounted": sum(non_veto_reasons.values()),
        "positionEventByCode": position_reasons,
        "positionEventCounted": sum(position_reasons.values()),
        "topVetoCodes": top_codes,
        "priceSources": _price_source_counts(evidence.get("priceSources")),
        "pairCapable": pair_capable(evidence),
        "pairActive": pair_active(evidence),
        "secondaryActive": bool(evidence.get("secondaryActive")),
        "versions": [str(v) for v in _as_sequence(evidence.get("requestedVersions")) if str(v)],
    }
    record["state"] = operability_state(record)
    return record


def _pair_label(record: Mapping[str, Any]) -> str:
    if bool(record.get("pairActive")):
        return "ACTIVO"
    if bool(record.get("pairCapable")):
        return "CAPAZ"
    return "NO"


def _veto_summary(record: Mapping[str, Any]) -> str:
    buckets = _as_mapping(record.get("vetoByBucket"))
    parts: list[str] = []
    for bucket in OPERABILITY_BUCKETS:
        total = sum(_count(count) for count in _as_mapping(buckets.get(bucket)).values())
        if total > 0:
            parts.append(f"{bucket}={total}")
    return " ".join(parts) if parts else "(sin vetos contabilizados)"


def _non_veto_summary(record: Mapping[str, Any]) -> str:
    """Línea declarada de aprobaciones/salidas (``""`` si el día no tuvo ninguna)."""
    counted = _count(record.get("nonVetoCounted"))
    if counted <= 0:
        return ""
    by_code = _as_mapping(record.get("nonVetoByCode"))
    detail = " ".join(
        f"{code}={_count(by_code[code])}" for code in sorted(by_code) if _count(by_code[code]) > 0
    )
    return f"  {record.get('day')}  aprobaciones/salidas: {detail} (NO son vetos)"


def _position_event_summary(record: Mapping[str, Any]) -> str:
    """Línea declarada de eventos de GESTIÓN DE POSICIÓN (``""`` si el día no tuvo ninguno)."""
    counted = _count(record.get("positionEventCounted"))
    if counted <= 0:
        return ""
    by_code = _as_mapping(record.get("positionEventByCode"))
    detail = " ".join(
        f"{code}={_count(by_code[code])}" for code in sorted(by_code) if _count(by_code[code]) > 0
    )
    return f"    eventos/posicion: {detail} (NO son vetos)"


def render_operability_table(records: Sequence[Mapping[str, Any]]) -> str:
    """Tabla textual (determinista) + desglose de vetos por familia, para el journal del operador."""
    headers = ("Dia", "Regimen", "Long", "SimbOper", "Decid", "Prop", "Veto", "Fills", "Ciclos", "Par")
    rows: list[tuple[str, ...]] = []
    for record in records:
        watch = _maybe_int(record.get("watchSize"))
        operable = record.get("symbolsOperable")
        operable_text = f"{operable}/{watch}" if operable is not None and watch is not None else "n/d"
        rows.append(
            (
                str(record.get("day") or ""),
                str(record.get("operationalRegime") or record.get("regime") or ""),
                "SI" if bool(record.get("entriesAllowedLong")) else "NO",
                operable_text,
                str(_count(record.get("decided"))),
                str(_count(record.get("proposals"))),
                str(_count(record.get("vetoes"))),
                str(_count(record.get("fills"))),
                str(_count(record.get("measurableCycles"))),
                _pair_label(record),
            )
        )
    widths = [
        max([len(headers[index]), *(len(row[index]) for row in rows)])
        for index in range(len(headers))
    ]

    def _format(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    lines = [_format(headers), _format(tuple("-" * width for width in widths))]
    lines.extend(_format(row) for row in rows)
    lines.append("")
    lines.append("Vetos por familia (por dia):")
    for record in records:
        lines.append(f"  {record.get('day')}  {_veto_summary(record)}")
        top = _as_sequence(record.get("topVetoCodes"))
        if top:
            detail = " ".join(f"{code}={count}" for code, count in top)
            lines.append(f"    codigos: {detail}")
        non_veto = _non_veto_summary(record)
        if non_veto:
            lines.append(non_veto)
        position_events = _position_event_summary(record)
        if position_events:
            lines.append(position_events)
    return "\n".join(lines)
