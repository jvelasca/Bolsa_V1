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
from bolsa_application.market_price_snapshot import PRICE_SOURCE_CLOSE, PRICE_SOURCE_LIVE

__all__ = [
    "BUCKET_DATA",
    "BUCKET_GOVERNOR",
    "BUCKET_LIQUIDITY",
    "BUCKET_OTHER",
    "BUCKET_REGIME",
    "BUCKET_RISK",
    "BUCKET_TOP_N",
    "OPERABILITY_BUCKETS",
    "STATE_NO_SIGNAL",
    "STATE_OPERATED",
    "STATE_UNKNOWN",
    "STATE_VETOED",
    "VETO_BUCKET_BY_REASON",
    "build_operability_record",
    "classify_veto_reasons",
    "operability_state",
    "pair_active",
    "pair_capable",
    "parse_journal_reasons",
    "render_operability_table",
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
    # Sin familia propia declarada: se cuenta igual (nunca se descarta).
    "position_exists": BUCKET_OTHER,
}


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

    Regla fail-closed: ``no_signal`` **sólo** si el motor no produjo ni propuestas ni vetos (no
    llegó a considerar candidata). Si hubo vetos, el estado es ``vetoed`` y el porqué vive en
    ``vetoByBucket``: así NO se puede leer "no hay señal" donde en realidad hubo un veto de
    régimen o de ``TOP_N``.
    """
    if _count(record.get("fills")) > 0 or _count(record.get("closed")) > 0:
        return STATE_OPERATED
    if _count(record.get("proposals")) == 0 and _count(record.get("vetoes")) == 0:
        return STATE_NO_SIGNAL
    if not record:
        return STATE_UNKNOWN
    return STATE_VETOED


def build_operability_record(evidence: Mapping[str, Any], *, day: str) -> dict[str, Any]:
    """Traduce el JSON de una corrida del runner a UNA fila diaria de operabilidad."""
    market_regime = _as_mapping(evidence.get("marketRegime"))
    totals = _as_mapping(evidence.get("turnTotals"))
    sample = _as_mapping(evidence.get("sample"))
    reasons = parse_journal_reasons(_as_sequence(evidence.get("journalReasons")))
    buckets = classify_veto_reasons(reasons)
    top_codes = sorted(
        ((code, count) for bucket in buckets.values() for code, count in bucket.items()),
        key=lambda item: (-item[1], item[0]),
    )
    record: dict[str, Any] = {
        "day": str(day),
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
    return "\n".join(lines)
