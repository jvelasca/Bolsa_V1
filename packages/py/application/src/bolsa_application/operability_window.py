"""V2.81 · AUTO-MATERIAL-9 — MARKET WINDOW (serie diaria de la ventana de operación).

Qué resuelve: la auditoría de ``v2.79`` dejó claro que el siguiente avance ya no es añadir
arquitectura, sino **observar** al AUTO funcionando durante una ventana real (≥4 días de
calendario). El censo de operabilidad de ``v2.77``/``v2.79`` se lee del JSON del runner; esta
pieza construye la **serie temporal diaria** a partir del **journal durable** (y del material de
riesgo por ciclo), para poder reconstruir cada día con su linaje.

Desde ``v2.80`` (``AUTO-MATERIAL-8``) la fila diaria ya separa ENTRADA de POSICIÓN y el gate es
honesto. Desde ``v2.81`` (``AUTO-MATERIAL-9``) la MISMA fila publica además el **funnel de
operabilidad** (``build_operability_funnel``: dónde pierde oportunidades el AUTO, escalón a
escalón, con la procedencia y el hueco declarados), la **permanencia de las propuestas sin
desenlace** (``unresolved_age``) y un **informe HTML** autocontenido
(``render_window_html``) reutilizable como artefacto ``operability-window.{json,html}``.

Una fila por día, con las dimensiones que el operador necesita para separar las causas de que el
AUTO no opere (mercado / gobernador / ``TOP_N`` / riesgo / reserva / dato), separando SIEMPRE los
dos canales que ``v2.79`` ya distingue:

* **ENTRADA** — decisiones de entrada (vetos puros + aprobaciones).
* **POSICIÓN** — eventos de gestión de una posición viva (NUNCA son vetos).

Reglas duras (las mismas del instrumento):

* **No se inventa medición.** Un dato ausente se declara ``None`` (o ``UNKNOWN``), jamás un ``0``
  de relleno. Una dimensión que esta fuente no puede medir (p. ej. ``priceSources`` desde el
  journal durable) queda declarada, no aproximada.
* **No se decide.** No se toca el motor, el gobernador ni ``TOP_N``; sólo se AGREGA lo que el
  journal y el material de riesgo ya declararon. El censo reutiliza las MISMAS puertas que
  ``market_operability`` (``collect_journal_reasons`` / ``split_journal_reasons`` /
  ``classify_veto_reasons``) para no abrir un segundo camino que pudiera divergir.
* **El veredicto es honesto.** Sin ≥4 días de calendario, ≥2 episodios de régimen y ≥32 ciclos
  medibles, la ventana NO está lista: se declara ``INCONCLUSIVE``, nunca un ``READY`` fabricado.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import measured_r
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.auto_reason_codes import (
    RESERVATION_ALREADY_LIVE,
    RESERVATION_UNMEASURABLE,
)
from bolsa_application.market_operability import (
    BUCKET_OTHER,
    BUCKET_RISK,
    BUCKET_TOP_N,
    ENTRY_DECISION_EVENT,
    POSITION_JOURNAL_EVENTS,
    classify_veto_reasons,
    collect_journal_reasons,
    operability_state,
    other_veto_count,
    pair_active,
    pair_capable,
    reason_catalog_coverage,
    split_journal_reasons,
    symbols_operable,
    veto_counted,
)
from bolsa_application.market_price_snapshot import PRICE_SOURCE_CLOSE, PRICE_SOURCE_LIVE

__all__ = [
    "FUNNEL_STEPS",
    "MARKET_WINDOW_INCONCLUSIVE",
    "MARKET_WINDOW_MIN_CYCLES",
    "MARKET_WINDOW_MIN_DAYS",
    "MARKET_WINDOW_MIN_EPISODES",
    "MARKET_WINDOW_READY",
    "UNRESOLVED_AGE_BUCKETS",
    "build_operability_funnel",
    "build_window_row",
    "render_window_html",
    "render_window_series",
    "unresolved_age",
    "window_gate",
]

#: Umbrales de la ventana (los del repo: NO se bajan para forzar una corrida).
MARKET_WINDOW_MIN_DAYS = 4
MARKET_WINDOW_MIN_EPISODES = 2
MARKET_WINDOW_MIN_CYCLES = 32

#: Veredicto del gate: la ventana aún no acredita diversidad de mercado.
MARKET_WINDOW_INCONCLUSIVE = "INCONCLUSIVE"
MARKET_WINDOW_READY = "READY"

#: Orden canónico del funnel de operabilidad, de arriba a abajo: en qué escalón se pierde cada
#: oportunidad (universo → dato → régimen → señal → TOP_N → riesgo → reserva → orden → fill → ciclo).
#: Es la métrica que decide si el cuello de botella es de MERCADO, de GOBERNADOR, de ``TOP_N`` o de
#: RIESGO: sin ella, todos los «no opera» se leen igual.
FUNNEL_STEPS: tuple[str, ...] = (
    "universe",
    "marketData",
    "regimeAllowed",
    "signals",
    "topN",
    "risk",
    "reservation",
    "orders",
    "fills",
    "cycles",
)

#: Códigos de veto que emite la ESPINA DE RESERVA (una apertura vetada): el escalón RESERVATION.
#: Se importan del dueño para que no puedan divergir del vocabulario de ``market_operability``.
_RESERVATION_VETO_CODES: frozenset[str] = frozenset(
    {RESERVATION_ALREADY_LIVE, RESERVATION_UNMEASURABLE, "reservation_failed"}
)

#: Cubos del histograma de permanencia (dwell) de las propuestas sin desenlace (``unresolved_age``).
UNRESOLVED_AGE_BUCKETS: tuple[str, ...] = ("lt1m", "1to5m", "5to20m", "gt20m", "unknown")
_AGE_LT_1M = timedelta(minutes=1)
_AGE_LT_5M = timedelta(minutes=5)
_AGE_LT_20M = timedelta(minutes=20)


def _count(value: Any) -> int:
    """Conteo entero o ``0`` (un valor ausente/ilegible NO se cuenta)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value) if value > 0 else 0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _field(raw: Any, name: str) -> Any:
    """Campo ``name`` de un ``Mapping`` o de un objeto, o ``None`` (mismo contrato que el lector)."""
    if isinstance(raw, Mapping):
        return raw.get(name)
    return getattr(raw, name, None)


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _maybe_int(value: Any) -> int | None:
    """Entero o ``None``: un dato ausente se declara ausente, nunca ``0`` (``bool`` NO es cuenta)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _step(count: Any, source: str) -> dict[str, Any]:
    """Un escalón del funnel: conteo, PROCEDENCIA declarada y si se llegó a medir."""
    number = _maybe_int(count)
    return {"count": number, "source": source, "measured": number is not None}


def _after(base: int | None, lost: int) -> int | None:
    """Escalón siguiente = anterior menos lo perdido; ``None`` si el anterior no se midió."""
    return None if base is None else max(0, base - lost)


def _payload_of(raw: Any) -> Mapping[str, Any]:
    """Payload de una entrada del journal (objeto con ``payload`` o mapping)."""
    payload = raw.get("payload") if isinstance(raw, Mapping) else getattr(raw, "payload", None)
    return payload if isinstance(payload, Mapping) else {}


def _instant(raw: Any) -> datetime | None:
    """Instante durable de una entrada (``created_at`` o su alias en el payload), o ``None``."""
    value: Any = _field(raw, "created_at")
    if value is None:
        value = _field(raw, "createdAt")
    if value is None:
        payload = _payload_of(raw)
        value = payload.get("createdAt") or payload.get("asOf") or payload.get("timestamp")
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _bucket_total(buckets: Mapping[str, Any], name: str) -> int:
    return sum(_count(count) for count in _as_mapping(buckets.get(name)).values())


def unresolved_age(entries: Sequence[Any]) -> dict[str, Any]:
    """(PURA) Permanencia de las PROPUESTAS (``approved``) sin desenlace registrado.

    Es el matiz que el contador ``unresolved`` no da (auditoría §22): una propuesta que se resuelve
    en dos segundos es normal; una que sigue ``unresolved`` veinte minutos delata un problema de
    integración. La referencia es el **último instante durable del día** (no ``now``): así una
    ventana de cuatro días no infla los días antiguos. Cubos: ``lt1m``/``1to5m``/``5to20m``/``gt20m``.

    Límite declarado (``resolutionJoined=false``): NO hay join propuesta→fill por identidad, así
    que esto mide la PERMANENCIA desde la propuesta dentro del día, no el ciclo de vida de una
    propuesta concreta. Con timestamps ilegibles el histograma se declara **no medido** (``None``),
    nunca un ``0`` de relleno.
    """
    proposals = 0
    unreadable = 0
    instants: list[datetime] = []
    all_instants: list[datetime] = []
    for entry in entries or ():
        moment = _instant(entry)
        if moment is not None:
            all_instants.append(moment)
        payload = _payload_of(entry)
        if str(payload.get("event") or "") != ENTRY_DECISION_EVENT:
            continue
        reasons = {str(reason or "").strip() for reason in _as_sequence(payload.get("reasonCodes"))}
        if "approved" not in reasons:
            continue
        proposals += 1
        if moment is None:
            unreadable += 1
        else:
            instants.append(moment)

    reference = max(all_instants) if all_instants else None
    reference_text = reference.isoformat() if reference else None
    if proposals == 0:
        return {
            "measured": True,
            "proposals": 0,
            "reference": reference_text,
            "resolutionJoined": False,
            "buckets": {name: 0 for name in UNRESOLVED_AGE_BUCKETS},
        }
    if reference is None or unreadable > 0:
        return {
            "measured": False,
            "proposals": proposals,
            "reference": reference_text,
            "resolutionJoined": False,
            "buckets": {name: None for name in UNRESOLVED_AGE_BUCKETS},
        }
    buckets = {name: 0 for name in UNRESOLVED_AGE_BUCKETS}
    for moment in instants:
        age = reference - moment
        if age < timedelta(0):
            buckets["unknown"] += 1
        elif age < _AGE_LT_1M:
            buckets["lt1m"] += 1
        elif age < _AGE_LT_5M:
            buckets["1to5m"] += 1
        elif age < _AGE_LT_20M:
            buckets["5to20m"] += 1
        else:
            buckets["gt20m"] += 1
    return {
        "measured": True,
        "proposals": proposals,
        "reference": reference_text,
        "resolutionJoined": False,
        "buckets": buckets,
    }


def build_operability_funnel(
    row: Mapping[str, Any], *, evidence: Mapping[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    """(PURA) Funnel de operabilidad de UN día: dónde se pierde cada oportunidad.

    Cada escalón se publica como ``{"count": int | None, "source": str, "measured": bool}``. Los
    escalones superiores (``universe``/``marketData``/``regimeAllowed``/``orders``) sólo existen con
    la EVIDENCIA del runner (``--forward``); sin ella se declaran ``None`` —jamás un ``0``—. Los
    escalones durables (``signals``→``reservation``) son la aritmética **declarada** del censo de
    ENTRADA: ``decided`` menos lo que cada familia de veto quitó. Si un prerrequisito no se midió,
    los escalones que dependen de él también quedan ``None`` (no se fabrica una caída de cero).
    """
    evidence = _as_mapping(evidence)
    measured_day = bool(row.get("measured"))
    buckets = _as_mapping(row.get("vetoByBucket"))

    universe: int | None = None
    market_data: int | None = None
    regime_allowed: int | None = None
    orders: int | None = None
    if evidence:
        universe = _maybe_int(evidence.get("watchSize"))
        sources = _as_mapping(evidence.get("priceSources"))
        if sources:
            market_data = sum(
                1
                for source in sources.values()
                if str(source) in (PRICE_SOURCE_LIVE, PRICE_SOURCE_CLOSE)
            )
        else:
            market_data = _maybe_int(_as_mapping(evidence.get("sample")).get("pricesServed"))
        regime_allowed = symbols_operable(_as_mapping(evidence.get("marketRegime")))
        orders = _maybe_int(_as_mapping(evidence.get("turnTotals")).get("orders"))

    decided = _count(row.get("decided")) if measured_day else None
    signals = decided
    top_n = _after(signals, _bucket_total(buckets, BUCKET_TOP_N))
    risk = _after(top_n, _bucket_total(buckets, BUCKET_RISK))
    reservation_lost = sum(
        _count(count)
        for code, count in _as_mapping(buckets.get(BUCKET_RISK)).items()
        if code in _RESERVATION_VETO_CODES
    )
    reservation = _after(risk, reservation_lost)
    fills = _maybe_int(row.get("fills")) if measured_day else None
    cycles = _maybe_int(row.get("measurableCycles")) if measured_day else None

    return {
        "universe": _step(universe, "evidence.watchSize"),
        "marketData": _step(market_data, "evidence.priceSources | sample.pricesServed"),
        "regimeAllowed": _step(regime_allowed, "evidence.marketRegime (symbols_operable)"),
        "signals": _step(signals, "journal auto_entry_decision (decided)"),
        "topN": _step(top_n, "signals - veto top_n"),
        "risk": _step(risk, "topN - veto risk"),
        "reservation": _step(reservation, "risk - veto de reserva"),
        "orders": _step(orders, "evidence.turnTotals.orders"),
        "fills": _step(fills, "material durable (fills)"),
        "cycles": _step(cycles, "material durable (measurableCycles)"),
    }


def _price_source_counts(value: Any) -> dict[str, int] | None:
    """Reparto de procedencia del precio, o ``None`` si no se aportó (no medido, nunca ``0``)."""
    sources = _as_mapping(value)
    if not sources:
        return None
    counts = {"live": 0, "close": 0, "missing": 0}
    for source in sources.values():
        text = str(source)
        if text == PRICE_SOURCE_LIVE:
            counts["live"] += 1
        elif text == PRICE_SOURCE_CLOSE:
            counts["close"] += 1
        else:
            counts["missing"] += 1
    return counts


def _cycle_ids(cycles: Sequence[Any]) -> list[str]:
    return sorted({_text(_field(row, "cycleId")) for row in cycles if _text(_field(row, "cycleId"))})


def _regimes(cycles: Sequence[Any]) -> list[str]:
    """Regímenes DECLARADOS por los ciclos del día (nunca un ``UNKNOWN`` de relleno)."""
    found = {_text(_field(row, "regime")) for row in cycles}
    found.discard("")
    return sorted(found)


def _versions(cycles: Sequence[Any], declared: Sequence[str]) -> list[str]:
    found = {_text(value) for value in declared}
    found |= {_text(_field(row, "strategyVersion")) for row in cycles}
    found.discard("")
    return sorted(found)


def _instruments(cycles: Sequence[Any], declared: Sequence[str]) -> list[str]:
    found = {_text(value) for value in declared}
    for row in cycles:
        found.add(_text(_field(row, "instrumentId")))
    found.discard("")
    return sorted(found)


def build_window_row(
    day: str,
    *,
    account: str = "",
    entries: Sequence[Any] = (),
    position_entries: Sequence[Any] = (),
    cycles: Sequence[Any] = (),
    fills: int | None = None,
    price_sources: Mapping[str, str] | None = None,
    versions: Sequence[str] = (),
    symbols_observed: int | None = None,
    instruments: Sequence[str] = (),
    captured_at: str = "",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """(PURA) UNA fila diaria de la ventana, con su linaje y sus huecos declarados.

    ``entries`` son las entradas del journal del día (se filtran por el evento de ENTRADA); si no
    se pasan ``position_entries`` aparte, la MISMA secuencia se usa también para el canal de
    POSICIÓN (un solo stream sirve). ``cycles`` son los ciclos con evidencia de riesgo de ese día
    (su R sale del MISMO lector que el informe: ``measured_r``).

    ``evidence`` es el JSON del runner (``--forward``, OPCIONAL): cuando se aporta, enriquece la
    procedencia del precio, el par A/B, ``symbolsObserved`` y los escalones superiores del funnel.
    Sin él, esos campos se declaran ``None`` —el journal durable no puede medirlos— y la fila
    sigue publicando su linaje y sus canales.
    """
    position_source = list(position_entries) if position_entries else list(entries)
    entry_reasons = collect_journal_reasons(entries, events=frozenset({ENTRY_DECISION_EVENT}))
    position_reasons = collect_journal_reasons(position_source, events=POSITION_JOURNAL_EVENTS)
    veto_reasons, non_veto_reasons = split_journal_reasons(entry_reasons)
    buckets = classify_veto_reasons(veto_reasons)
    other_count = other_veto_count(buckets)
    observed = (
        {code for bucket in buckets.values() for code in bucket}
        | set(non_veto_reasons)
        | set(position_reasons)
    )

    measured_r_values = [r for row in cycles if (r := measured_r(row)) is not None]
    r_sum: float | None = None
    r_mean: float | None = None
    if measured_r_values:
        r_sum = sum(measured_r_values)
        r_mean = r_sum / len(measured_r_values)
    regimes = _regimes(cycles)
    day_measured = bool(entries) or bool(position_source) or bool(cycles) or fills is not None

    evidence_mapping = _as_mapping(evidence)
    if symbols_observed is None and evidence_mapping:
        symbols_observed = _maybe_int(evidence_mapping.get("watchSize"))
    effective_price_sources = price_sources
    if effective_price_sources is None and evidence_mapping:
        effective_price_sources = _as_mapping(evidence_mapping.get("priceSources")) or None
    pair_capable_value = pair_capable(evidence_mapping) if evidence_mapping else None
    pair_active_value = pair_active(evidence_mapping) if evidence_mapping else None

    row: dict[str, Any] = {
        "day": str(day),
        "account": str(account),
        "capturedAt": str(captured_at),
        "measured": day_measured,
        "regime": regimes[0] if len(regimes) == 1 else None,
        "regimes": regimes,
        "regimeMeasurement": MEASUREMENT_COMPLETE if regimes else MEASUREMENT_UNKNOWN,
        "symbolsObserved": symbols_observed,
        "instruments": _instruments(cycles, instruments),
        "versions": _versions(cycles, versions),
        "cycleIds": _cycle_ids(cycles),
        "decided": sum(entry_reasons.values()),
        "proposals": _count(non_veto_reasons.get("approved")),
        "vetoes": sum(veto_reasons.values()),
        "fills": fills,
        "cycles": len(cycles),
        "measurableCycles": len(measured_r_values),
        "rSum": r_sum,
        "rMean": r_mean,
        "rMeasurement": MEASUREMENT_COMPLETE if measured_r_values else MEASUREMENT_UNKNOWN,
        "vetoByBucket": buckets,
        "vetoCounted": veto_counted(buckets),
        "otherCount": other_count,
        "contractViolation": other_count > 0,
        "reasonCatalogCoverage": reason_catalog_coverage(observed),
        "nonVetoByCode": non_veto_reasons,
        "nonVetoCounted": sum(non_veto_reasons.values()),
        "positionEventByCode": position_reasons,
        "positionEventCounted": sum(position_reasons.values()),
        "priceSources": _price_source_counts(effective_price_sources),
        # Sin evidencia del runner no son medibles desde el journal durable: se declaran ausentes.
        "pairCapable": pair_capable_value,
        "pairActive": pair_active_value,
        "unresolvedAge": unresolved_age(entries) if day_measured else {
            "measured": False,
            "proposals": None,
            "reference": None,
            "resolutionJoined": False,
            "buckets": {name: None for name in UNRESOLVED_AGE_BUCKETS},
        },
    }
    row["state"] = operability_state(
        {
            "measured": day_measured,
            "proposals": row["proposals"],
            "vetoes": row["vetoes"],
            "fills": fills if fills is not None else 0,
            "closed": len(cycles),
        }
    )
    row["funnel"] = build_operability_funnel(row, evidence=evidence_mapping)
    return row


def window_gate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """(PURA) ¿acredita la ventana diversidad de mercado? (≥4 días, ≥2 episodios, ≥32 ciclos).

    Cuenta **cubos de CALENDARIO** (días distintos), NO número de filas: cuatro corridas del mismo
    día son un solo cubo. Los episodios son los regímenes DISTINTOS declarados por los ciclos. Los
    ciclos son los MEDIBLES (con R), no las filas. Si algo falta, el veredicto es ``INCONCLUSIVE``.
    """
    days = {day for row in rows if (day := _text(row.get("day")))}
    episodes: set[str] = set()
    for row in rows:
        for regime in _as_sequence(row.get("regimes")):
            text = _text(regime)
            if text:
                episodes.add(text)
        single = _text(row.get("regime"))
        if single:
            episodes.add(single)
    cycles = sum(_count(row.get("measurableCycles")) for row in rows)
    ready = (
        len(days) >= MARKET_WINDOW_MIN_DAYS
        and len(episodes) >= MARKET_WINDOW_MIN_EPISODES
        and cycles >= MARKET_WINDOW_MIN_CYCLES
    )
    return {
        "days": len(days),
        "episodes": len(episodes),
        "cycles": cycles,
        "minDays": MARKET_WINDOW_MIN_DAYS,
        "minEpisodes": MARKET_WINDOW_MIN_EPISODES,
        "minCycles": MARKET_WINDOW_MIN_CYCLES,
        "dayList": sorted(days),
        "regimes": sorted(episodes),
        "measured": bool(rows),
        "ready": ready,
        "verdict": MARKET_WINDOW_READY if ready else MARKET_WINDOW_INCONCLUSIVE,
    }


def _number(value: Any) -> str:
    return "n/d" if value is None else f"{float(value):.4f}"


def _veto_summary(row: Mapping[str, Any]) -> str:
    buckets = _as_mapping(row.get("vetoByBucket"))
    parts = [
        f"{bucket}={sum(_count(count) for count in _as_mapping(buckets.get(bucket)).values())}"
        for bucket in ("regime", "governor", "liquidity", "risk", "top_n", "data", "other")
        if sum(_count(count) for count in _as_mapping(buckets.get(bucket)).values()) > 0
    ]
    return " ".join(parts) if parts else "(sin vetos contabilizados)"


def _code_line(label: str, by_code: Any) -> str:
    codes = _as_mapping(by_code)
    detail = " ".join(f"{code}={_count(codes[code])}" for code in sorted(codes) if _count(codes[code]) > 0)
    return f"    {label}: {detail}" if detail else ""


def render_window_series(rows: Sequence[Mapping[str, Any]]) -> str:
    """Tabla diaria determinista + desglose por familia + canal de POSICIÓN separado."""
    headers = ("Dia", "Regimen", "ENTRY", "VETOS", "FILLS", "CYCLES", "R", "Estado")
    table: list[tuple[str, ...]] = []
    for row in rows:
        table.append(
            (
                str(row.get("day") or ""),
                str(row.get("regime") or "-"),
                str(_count(row.get("decided"))),
                str(_count(row.get("vetoCounted"))),
                "n/d" if row.get("fills") is None else str(_count(row.get("fills"))),
                str(_count(row.get("measurableCycles"))),
                _number(row.get("rMean")),
                str(row.get("state") or ""),
            )
        )
    widths = [
        max([len(headers[index]), *(len(cells[index]) for cells in table)])
        for index in range(len(headers))
    ]

    def _format(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    lines = [_format(headers), _format(tuple("-" * width for width in widths))]
    lines.extend(_format(cells) for cells in table)
    lines.append("")
    lines.append("Vetos por familia (por dia):")
    for row in rows:
        lines.append(f"  {row.get('day')}  {_veto_summary(row)}")
        non_veto = _code_line("aprobaciones/salidas (NO son vetos)", row.get("nonVetoByCode"))
        if non_veto:
            lines.append(non_veto)
        position = _code_line("eventos/posicion (NO son vetos)", row.get("positionEventByCode"))
        if position:
            lines.append(position)
        if bool(row.get("contractViolation")):
            others = _as_mapping(_as_mapping(row.get("vetoByBucket")).get(BUCKET_OTHER))
            detail = " ".join(f"{code}={_count(others[code])}" for code in sorted(others))
            lines.append(
                f"    ALERTA CONTRATO: other>0 (motivo(s) no catalogado(s): {detail}) "
                "— revisar alta de reason code"
            )
    lines.append("")
    lines.append("Funnel de operabilidad (por dia; n/d = no medido, nunca 0):")
    for row in rows:
        funnel_line = _funnel_line(row)
        if funnel_line:
            lines.append(funnel_line)
    lines.append("")
    lines.append("Permanencia de propuestas sin desenlace (unresolved_age):")
    for row in rows:
        age_line = _age_line(row)
        if age_line:
            lines.append(age_line)
    return "\n".join(lines)


def _funnel_line(row: Mapping[str, Any]) -> str:
    funnel = _as_mapping(row.get("funnel"))
    if not funnel:
        return ""
    parts = []
    for step in FUNNEL_STEPS:
        count = _as_mapping(funnel.get(step)).get("count")
        parts.append(f"{step}={'n/d' if count is None else _count(count)}")
    return f"  {row.get('day')}  " + " -> ".join(parts)


def _age_line(row: Mapping[str, Any]) -> str:
    age = _as_mapping(row.get("unresolvedAge"))
    if not age:
        return ""
    buckets = _as_mapping(age.get("buckets"))
    detail = " ".join(
        f"{name}={'n/d' if buckets.get(name) is None else _count(buckets.get(name))}"
        for name in UNRESOLVED_AGE_BUCKETS
    )
    return f"  {row.get('day')}  ({'medido' if age.get('measured') else 'NO MEDIDO'}): {detail}"


# ── Informe HTML autocontenido (artefacto operability-window.html) ──────────────────────────────

_HTML_STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #1b1b1b; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; margin-top: 1.6rem; }
table { border-collapse: collapse; margin: 0.5rem 0; width: 100%; }
th, td { border: 1px solid #ccc; padding: 0.25rem 0.5rem; text-align: left; font-size: 0.85rem; }
th { background: #f2f2f2; }
.meta, .note { color: #555; font-size: 0.85rem; }
.gate { padding: 0.5rem 0.75rem; border-radius: 4px; margin: 0.5rem 0; font-size: 0.95rem; }
.gate.ready { background: #e6f4ea; border: 1px solid #34a853; }
.gate.inconclusive { background: #fce8e6; border: 1px solid #c5221f; }
.alert { color: #c5221f; font-weight: bold; }
code { background: #f2f2f2; padding: 0 0.2rem; }
"""


def _e(value: Any) -> str:
    """Texto escapado para HTML (``None`` → cadena vacía; nada se inyecta)."""
    return html.escape("" if value is None else str(value))


def _pair_cell(row: Mapping[str, Any]) -> str:
    if row.get("pairActive") is True:
        return "ACTIVO"
    if row.get("pairCapable") is True:
        return "CAPAZ"
    if row.get("pairCapable") is None and row.get("pairActive") is None:
        return "n/d"
    return "NO"


def _price_cell(row: Mapping[str, Any]) -> str:
    sources = _as_mapping(row.get("priceSources"))
    if not sources:
        return "n/d"
    return f"live={_count(sources.get('live'))} close={_count(sources.get('close'))} " \
        f"missing={_count(sources.get('missing'))}"


def _gate_html(gate: Mapping[str, Any]) -> str:
    ready = bool(gate.get("ready"))
    css = "ready" if ready else "inconclusive"
    return (
        f'<div class="gate {css}"><strong>GATE: {_e(gate.get("verdict") or "INCONCLUSIVE")}'
        f'</strong> — dias {_count(gate.get("days"))}/{_count(gate.get("minDays"))}'
        f' · episodios {_count(gate.get("episodes"))}/{_count(gate.get("minEpisodes"))}'
        f' · ciclos {_count(gate.get("cycles"))}/{_count(gate.get("minCycles"))}</div>'
    )


def _series_table_html(rows: Sequence[Mapping[str, Any]]) -> str:
    head = (
        "<tr><th>Dia</th><th>Regimen</th><th>ENTRY</th><th>VETOS</th><th>FILLS</th>"
        "<th>CYCLES</th><th>R</th><th>Par</th><th>Precio</th><th>Estado</th></tr>"
    )
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{_e(row.get('day'))}</td>"
            f"<td>{_e(row.get('regime') or '-')}</td>"
            f"<td>{_count(row.get('decided'))}</td>"
            f"<td>{_count(row.get('vetoCounted'))}</td>"
            f"<td>{'n/d' if row.get('fills') is None else _count(row.get('fills'))}</td>"
            f"<td>{_count(row.get('measurableCycles'))}</td>"
            f"<td>{_e(_number(row.get('rMean')))}</td>"
            f"<td>{_e(_pair_cell(row))}</td>"
            f"<td>{_e(_price_cell(row))}</td>"
            f"<td>{_e(row.get('state') or '')}</td>"
            "</tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def _funnel_table_html(rows: Sequence[Mapping[str, Any]]) -> str:
    head = "<tr><th>Dia</th>" + "".join(f"<th>{_e(step)}</th>" for step in FUNNEL_STEPS) + "</tr>"
    body = []
    for row in rows:
        funnel = _as_mapping(row.get("funnel"))
        cells = []
        for step in FUNNEL_STEPS:
            count = _as_mapping(funnel.get(step)).get("count")
            cells.append(f"<td>{'n/d' if count is None else _count(count)}</td>")
        body.append(f"<tr><td>{_e(row.get('day'))}</td>{''.join(cells)}</tr>")
    return f"<table>{head}{''.join(body)}</table>"


def _reasons_html(rows: Sequence[Mapping[str, Any]]) -> str:
    blocks = []
    for row in rows:
        lines = [f"<p><strong>{_e(row.get('day'))}</strong> — {_e(_veto_summary(row))}</p>"]
        codes = _as_mapping(row.get("nonVetoByCode"))
        detail = " ".join(
            f"{_e(code)}={_count(codes[code])}" for code in sorted(codes) if _count(codes[code]) > 0
        )
        if detail:
            lines.append(f"<p class=\"note\">aprobaciones/salidas (NO son vetos): {detail}</p>")
        position = _as_mapping(row.get("positionEventByCode"))
        position_detail = " ".join(
            f"{_e(code)}={_count(position[code])}"
            for code in sorted(position)
            if _count(position[code]) > 0
        )
        if position_detail:
            lines.append(f"<p class=\"note\">eventos/posicion (NO son vetos): {position_detail}</p>")
        coverage = _as_mapping(row.get("reasonCatalogCoverage"))
        if coverage:
            lines.append(
                "<p class=\"note\">cobertura: "
                f"declared={_count(coverage.get('declared'))} "
                f"observed={_count(coverage.get('observed'))} "
                f"unknown={_count(coverage.get('unknown'))}</p>"
            )
        if bool(row.get("contractViolation")):
            others = _as_mapping(_as_mapping(row.get("vetoByBucket")).get(BUCKET_OTHER))
            detail_other = " ".join(f"{_e(code)}={_count(others[code])}" for code in sorted(others))
            lines.append(
                f"<p class=\"alert\">ALERTA CONTRATO: other&gt;0 "
                f"(motivo(s) no catalogado(s): {detail_other}) — revisar alta de reason code</p>"
            )
        blocks.append("".join(lines))
    return "".join(blocks)


def _age_table_html(rows: Sequence[Mapping[str, Any]]) -> str:
    head = (
        "<tr><th>Dia</th><th>Estado</th><th>Propuestas</th>"
        + "".join(f"<th>{_e(name)}</th>" for name in UNRESOLVED_AGE_BUCKETS)
        + "</tr>"
    )
    body = []
    for row in rows:
        age = _as_mapping(row.get("unresolvedAge"))
        buckets = _as_mapping(age.get("buckets"))
        cells = "".join(
            f"<td>{'n/d' if buckets.get(name) is None else _count(buckets.get(name))}</td>"
            for name in UNRESOLVED_AGE_BUCKETS
        )
        proposals = age.get("proposals")
        body.append(
            f"<tr><td>{_e(row.get('day'))}</td>"
            f"<td>{'medido' if age.get('measured') else 'NO MEDIDO'}</td>"
            f"<td>{'n/d' if proposals is None else _count(proposals)}</td>{cells}</tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def render_window_html(rows: Sequence[Mapping[str, Any]], meta: Mapping[str, Any]) -> str:
    """(PURA) Informe HTML autocontenido de la ventana (``operability-window.html``).

    Determinista y sin recursos externos: todo el contenido sale de ``rows``/``meta`` (nada se
    regenera con el reloj). Publica la serie diaria, el veredicto del gate, el funnel, la
    distribución de motivos con su cobertura, la alerta de contrato y el ``unresolved_age``. Todo
    texto se ESCAPA (``html.escape``): un código de motivo no puede inyectar marcado.
    """
    header = _as_mapping(_as_mapping(meta).get("header"))
    gate = _as_mapping(_as_mapping(meta).get("gate"))
    versions = ", ".join(str(value) for value in _as_sequence(header.get("versions"))) or "(ninguna)"
    parts = [
        "<!DOCTYPE html>",
        '<html lang="es">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>AUTO MARKET WINDOW (V2.81 · AUTO-MATERIAL-9)</title>",
        f"<style>{_HTML_STYLE}</style>",
        "</head>",
        "<body>",
        "<h1>AUTO MARKET WINDOW — informe de ventana</h1>",
        (
            f'<p class="meta">cuenta {_e(header.get("account"))} · versiones {_e(versions)}'
            f' · capturado {_e(header.get("capturedAt"))}</p>'
        ),
        _gate_html(gate),
        "<h2>Serie diaria</h2>",
        _series_table_html(rows),
        "<h2>Funnel de operabilidad (por dia)</h2>",
        _funnel_table_html(rows),
        "<h2>Distribucion de motivos</h2>",
        _reasons_html(rows),
        "<h2>Permanencia de propuestas sin desenlace (unresolved_age)</h2>",
        _age_table_html(rows),
        (
            '<p class="note">ENTRY = decisiones de entrada; VETOS = vetos PUROS; los eventos de '
            "POSICION NO son vetos. Un hueco se declara <code>n/d</code> (None), nunca 0. "
            "El veredicto honesto sin ventana es <code>INCONCLUSIVE</code>.</p>"
        ),
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)
