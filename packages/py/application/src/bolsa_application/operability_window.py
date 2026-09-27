"""V2.80 · AUTO-MATERIAL-8 — MARKET WINDOW (serie diaria de la ventana de operación).

Qué resuelve: la auditoría de ``v2.79`` dejó claro que el siguiente avance ya no es añadir
arquitectura, sino **observar** al AUTO funcionando durante una ventana real (≥4 días de
calendario). El censo de operabilidad de ``v2.77``/``v2.79`` se lee del JSON del runner; esta
pieza construye la **serie temporal diaria** a partir del **journal durable** (y del material de
riesgo por ciclo), para poder reconstruir cada día con su linaje.

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

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import measured_r
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.market_operability import (
    BUCKET_OTHER,
    ENTRY_DECISION_EVENT,
    POSITION_JOURNAL_EVENTS,
    classify_veto_reasons,
    collect_journal_reasons,
    operability_state,
    other_veto_count,
    reason_catalog_coverage,
    split_journal_reasons,
    veto_counted,
)
from bolsa_application.market_price_snapshot import PRICE_SOURCE_CLOSE, PRICE_SOURCE_LIVE

__all__ = [
    "MARKET_WINDOW_INCONCLUSIVE",
    "MARKET_WINDOW_MIN_CYCLES",
    "MARKET_WINDOW_MIN_DAYS",
    "MARKET_WINDOW_MIN_EPISODES",
    "MARKET_WINDOW_READY",
    "build_window_row",
    "render_window_series",
    "window_gate",
]

#: Umbrales de la ventana (los del repo: NO se bajan para forzar una corrida).
MARKET_WINDOW_MIN_DAYS = 4
MARKET_WINDOW_MIN_EPISODES = 2
MARKET_WINDOW_MIN_CYCLES = 32

#: Veredicto del gate: la ventana aún no acredita diversidad de mercado.
MARKET_WINDOW_INCONCLUSIVE = "INCONCLUSIVE"
MARKET_WINDOW_READY = "READY"


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
) -> dict[str, Any]:
    """(PURA) UNA fila diaria de la ventana, con su linaje y sus huecos declarados.

    ``entries`` son las entradas del journal del día (se filtran por el evento de ENTRADA); si no
    se pasan ``position_entries`` aparte, la MISMA secuencia se usa también para el canal de
    POSICIÓN (un solo stream sirve). ``cycles`` son los ciclos con evidencia de riesgo de ese día
    (su R sale del MISMO lector que el informe: ``measured_r``).
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
        "priceSources": _price_source_counts(price_sources),
        # No medibles desde el journal durable: se declaran ausentes, no se aproximan.
        "pairCapable": None,
        "pairActive": None,
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
    return "\n".join(lines)
