"""V2.83 · AUTO-MATERIAL-11 — AUDITORÍA de la ventana PAPER (pura, sin I/O).

Qué resuelve: ``v2.81``/``v2.82`` dejaron la ventana real ≥4 días como operación del propietario y
el instrumento que la publica (``operability_window``) ya entrega la **serie diaria**, el **funnel**,
el ``unresolved_age`` y el **informe HTML**. Faltaba la lectura **acumulada**: la fila ``TOTAL`` y las
**tasas de operabilidad** que convierten el funnel en un perfil operativo («dónde se atasca el AUTO»)
y que el auditor necesita para no leer un ``0 cycles`` como «el AUTO no funciona».

Esta pieza AGREGA lo que el instrumento ya declaró: no abre el motor, no toca PostgreSQL, no
recalcula el gate ni cambia un umbral. Es la lectura de los ``rows`` que ``v2_80_market_window.py``
escribió (``{"meta": …, "rows": …}``) o del journal acumulado (``window.jsonl``).

Reglas duras (las MISMAS del instrumento):

* **No se inventa medición.** Un hueco se declara ``None`` (o ``n/d``), **jamás** un ``0``. Un cociente
  sin denominador medido, o con denominador ``0``, queda ``rate=None`` — no un ``0.0`` de relleno.
* **No se decide.** No se toca el motor, el gobernador ni ``TOP_N``; sólo se AGREGA. El funnel y el gate
  se REUTILIZAN del instrumento (``build_operability_funnel`` / ``window_gate``) para no abrir un segundo
  camino que pudiera divergir.
* **El TOTAL no suma huecos como ceros**: cada campo publica su cobertura (``measuredDays/ofDays`` y
  ``partial``) para que un día incompleto se VEA como incompleto.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_application.market_operability import (
    STATE_UNRESOLVED,
    pair_active,
    pair_capable,
)
from bolsa_application.market_price_snapshot import PRICE_SOURCE_CLOSE, PRICE_SOURCE_LIVE
from bolsa_application.operability_window import (
    FUNNEL_STEPS,
    _as_mapping,
    _maybe_int,
    build_operability_funnel,
    window_gate,
)

__all__ = [
    "AUDIT_TOTAL_FIELDS",
    "enrich_rows_with_evidence",
    "render_window_audit",
    "window_audit",
    "window_rates",
    "window_totals",
]

#: Campos de conteo que la fila diaria publica y que el TOTAL acumula (sólo días MEDIDOS).
AUDIT_TOTAL_FIELDS: tuple[str, ...] = (
    "decided",
    "proposals",
    "vetoes",
    "vetoCounted",
    "otherCount",
    "nonVetoCounted",
    "positionEventCounted",
    "fills",
    "cycles",
    "measurableCycles",
)

#: Etiqueta legible + fuente declarada de cada tasa (el motor no las emite: son DERIVADAS del funnel).
_RATE_SOURCES: dict[str, str] = {
    "topNExclusionRate": "funnel (signals - topN) / signals",
    "riskRejectionRate": "funnel (topN - risk) / topN",
    "reservationFailureRate": "funnel (risk - reservation) / risk",
    "fillRate": "funnel fills / orders (requiere --forward)",
    "cycleRate": "funnel measurableCycles / fills",
    "unresolvedRate": "dias MEDIDOS con state 'unresolved' (indicador 1.0/None; NO es tasa de propuestas)",
}


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _measured(row: Mapping[str, Any]) -> bool:
    """¿Declara la fila que se midió? Mismo contrato que ``operability_state``: ausente ⇒ medido."""
    return row.get("measured") is not False


def _sum_int_field(rows: Sequence[Mapping[str, Any]], field: str) -> tuple[int, int]:
    """Suma de ``field`` sobre los días MEDIDOS y en cuántos días se pudo leer (nunca cuenta huecos)."""
    total = 0
    days = 0
    for row in rows:
        if not _measured(row):
            continue
        value = _maybe_int(row.get(field))
        if value is None:
            continue
        total += value
        days += 1
    return total, days


def _coverage(measured_days: int, of_days: int) -> dict[str, Any]:
    return {
        "days": measured_days,
        "ofDays": of_days,
        "measured": measured_days > 0,
        "partial": measured_days < of_days,
    }


def window_totals(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """(PURA) Fila TOTAL acumulada de la ventana, con la cobertura de CADA campo declarada.

    Suma **sólo** los días con el campo medido; un día no medido (o un campo ausente) **no** se suma
    como ``0``. ``coverage[field].partial`` delata un TOTAL construido sobre días incompletos, para que
    no se lea como una medida cerrada. El ``rSum`` es la suma de R de los ciclos medibles (su cobertura
    se publica igual) y el funnel agrega, escalón a escalón, **sólo** los días MEDIDOS que SÍ lo midieron.
    ``stateCounts`` TAMBIÉN respeta ``measured_rows``: el ``state`` de un día con ``measured=False`` NO
    infla ningún bucket, y hoy sólo el bucket ``unknown`` podría verse afectado porque ``operability_state``
    es fail-closed.
    """
    rows = list(rows)
    days_total = len(rows)
    measured_rows = [row for row in rows if _measured(row)]
    days_measured = len(measured_rows)

    counts: dict[str, int] = {}
    coverage: dict[str, Any] = {}
    for field in AUDIT_TOTAL_FIELDS:
        total, days = _sum_int_field(measured_rows, field)
        counts[field] = total
        coverage[field] = _coverage(days, days_measured)

    r_sum = 0.0
    r_days = 0
    for row in measured_rows:
        value = row.get("rSum")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        r_sum += float(value)
        r_days += 1
    coverage["rSum"] = _coverage(r_days, days_measured)

    state_counts: dict[str, int] = {}
    # OBS-10: ``stateCounts`` honra ``measured_rows`` igual que ``counts``/``coverage``/``rSum``/``funnel``;
    # el ``state`` de un día NO medido no debe inflar ningún bucket.
    for row in measured_rows:
        state = _text(row.get("state"))
        if state:
            state_counts[state] = state_counts.get(state, 0) + 1

    regimes: set[str] = set()
    instruments: set[str] = set()
    versions: set[str] = set()
    for row in rows:
        for regime in _as_list(row.get("regimes")):
            text = _text(regime)
            if text:
                regimes.add(text)
        single = _text(row.get("regime"))
        if single:
            regimes.add(single)
        for name in _as_list(row.get("instruments")):
            text = _text(name)
            if text:
                instruments.add(text)
        for version in _as_list(row.get("versions")):
            text = _text(version)
            if text:
                versions.add(text)

    funnel: dict[str, Any] = {}
    for step in FUNNEL_STEPS:
        total = 0
        days = 0
        for row in measured_rows:
            entry = _as_mapping(_as_mapping(row.get("funnel")).get(step))
            value = _maybe_int(entry.get("count"))
            if value is None:
                continue
            total += value
            days += 1
        funnel[step] = {
            "count": total,
            "days": days,
            "measured": days > 0,
            "partial": days < days_measured,
        }

    return {
        "daysTotal": days_total,
        "daysMeasured": days_measured,
        "counts": counts,
        "coverage": coverage,
        "rSum": r_sum if r_days else None,
        "stateCounts": {name: state_counts[name] for name in sorted(state_counts)},
        "regimes": sorted(regimes),
        "instruments": sorted(instruments),
        "versions": sorted(versions),
        "funnel": funnel,
    }


def _rate_from_pairs(pairs: Sequence[tuple[int, int]], source: str) -> dict[str, Any]:
    """Tasa = numerador/denominador sobre los días aportados; sin días (o denominador 0) → ``None``."""
    if not pairs:
        return {
            "numerator": None,
            "denominator": None,
            "rate": None,
            "coveredDays": 0,
            "source": source,
        }
    numerator = sum(max(0, num) for num, _ in pairs)
    denominator = sum(max(0, den) for _, den in pairs)
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": (numerator / denominator) if denominator > 0 else None,
        "coveredDays": len(pairs),
        "source": source,
    }


def _funnel_step(row: Mapping[str, Any], step: str) -> int | None:
    return _maybe_int(_as_mapping(_as_mapping(row.get("funnel")).get(step)).get("count"))


def _funnel_pair(
    rows: Sequence[Mapping[str, Any]], upper: str, lower: str
) -> list[tuple[int, int]]:
    """Pares ``(perdidos = upper - lower, upper)`` de los días en que AMBOS escalones se midieron."""
    pairs: list[tuple[int, int]] = []
    for row in rows:
        upper_count = _funnel_step(row, upper)
        lower_count = _funnel_step(row, lower)
        if upper_count is None or lower_count is None:
            continue
        pairs.append((upper_count - lower_count, upper_count))
    return pairs


def window_rates(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """(PURA) Tasas de operabilidad DERIVADAS del funnel, con su cobertura y su fuente declaradas.

    Responde a la pregunta del auditor («¿dónde se atasca el AUTO?») sin mirar el resultado final:
    cada cociente se calcula sobre los días en que sus DOS escalones se midieron, y sin días medidos
    (o con denominador ``0``) el ``rate`` queda ``None`` —nunca un ``0.0`` fabricado. La ``fillRate``
    sólo existe con la evidencia del runner (``--forward``), pero sin ella se declara ``n/d``.

    ``unresolvedRate`` cuenta DÍAS, no propuestas: se construye con pares ``(1, 1)``, así que
    ``numerator == denominator ==`` número de días MEDIDOS cuyo ``state`` es ``unresolved``; su ``rate``
    es ``1.0`` en cuanto hay uno de esos días y ``None`` cuando no hay ninguno. NO debe leerse como una
    proporción ni como una tasa de propuestas. La clave NO se renombra a propósito, por compatibilidad
    con informes anteriores.
    """
    rows = list(rows)

    fill_pairs: list[tuple[int, int]] = []
    cycle_pairs: list[tuple[int, int]] = []
    for row in rows:
        fills = _maybe_int(row.get("fills"))
        orders = _funnel_step(row, "orders")
        if fills is not None and orders is not None:
            fill_pairs.append((fills, orders))
        cycles = _maybe_int(row.get("measurableCycles"))
        if cycles is not None and fills is not None:
            cycle_pairs.append((cycles, fills))

    unresolved_pairs = [
        (1, 1)
        for row in rows
        if _measured(row) and _text(row.get("state")) == STATE_UNRESOLVED
    ]

    return {
        "topNExclusionRate": _rate_from_pairs(
            _funnel_pair(rows, "signals", "topN"), _RATE_SOURCES["topNExclusionRate"]
        ),
        "riskRejectionRate": _rate_from_pairs(
            _funnel_pair(rows, "topN", "risk"), _RATE_SOURCES["riskRejectionRate"]
        ),
        "reservationFailureRate": _rate_from_pairs(
            _funnel_pair(rows, "risk", "reservation"), _RATE_SOURCES["reservationFailureRate"]
        ),
        "fillRate": _rate_from_pairs(fill_pairs, _RATE_SOURCES["fillRate"]),
        "cycleRate": _rate_from_pairs(cycle_pairs, _RATE_SOURCES["cycleRate"]),
        "unresolvedRate": _rate_from_pairs(unresolved_pairs, _RATE_SOURCES["unresolvedRate"]),
    }


def _warnings(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """AVISOS deterministas (nunca ocultados): contrato de razones, par A/B y precio faltante."""
    warnings: list[dict[str, Any]] = []
    for row in rows:
        day = _text(row.get("day"))
        if bool(row.get("contractViolation")):
            buckets = _as_mapping(_as_mapping(row.get("vetoByBucket")).get("other"))
            detail = " ".join(f"{code}={buckets[code]}" for code in sorted(buckets))
            warnings.append(
                {
                    "level": "aviso",
                    "code": "reason_contract",
                    "day": day,
                    "message": (
                        f"ALERTA CONTRATO: other>0 (motivo(s) no catalogado(s): {detail}) "
                        "— H-4 visible; catalogar antes de cerrar la fase estadistica"
                    ),
                }
            )
        price = _as_mapping(row.get("priceSources"))
        missing = _maybe_int(price.get("missing"))
        if missing is not None and missing > 0:
            warnings.append(
                {
                    "level": "aviso",
                    "code": "price_missing",
                    "day": day,
                    "message": f"precio faltante en {missing} simbolo(s): marketData parcial",
                }
            )
        pair_active_value = row.get("pairActive")
        if pair_active_value is False:
            warnings.append(
                {
                    "level": "aviso",
                    "code": "pair_not_active",
                    "day": day,
                    "message": "par A/B NO ACTIVO (pairActive=false): brecha 1 del runbook §2",
                }
            )
    if rows and all(row.get("pairActive") is None for row in rows):
        warnings.append(
            {
                "level": "info",
                "code": "pair_unmeasured",
                "day": "",
                "message": "par A/B NO MEDIDO (sin --forward): pairActive=n/d, no se deduce de pairCapable",
            }
        )
    return warnings


def window_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """(PURA) Bloque de auditoría de la ventana: TOTAL + tasas + gate + funnel + avisos."""
    rows = list(rows)
    totals = window_totals(rows)
    return {
        "daysTotal": totals["daysTotal"],
        "daysMeasured": totals["daysMeasured"],
        "totals": totals,
        "rates": window_rates(rows),
        "funnel": totals["funnel"],
        "gate": window_gate(rows),
        "warnings": _warnings(rows),
    }


def _evidence_price_counts(value: Any) -> dict[str, int] | None:
    """Reparto de procedencia del precio desde la evidencia del runner, o ``None`` si no se aportó."""
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


def _fill_funnel_gaps(row: Mapping[str, Any], rebuilt: Mapping[str, Any]) -> dict[str, Any]:
    """(PURA) Conserva cada escalón YA medido de la fila y toma del reconstruido SÓLO los huecos.

    ``build_operability_funnel`` recalcula el funnel ENTERO (los cuatro escalones superiores salen de
    la evidencia), así que usarlo como **reemplazo** PISARÍA un escalón ya medido cuando esa evidencia
    discrepa de la que midió la fila. Aquí se respeta el contrato del módulo: **sólo** se rellena lo
    que la fila declaró ``None``; un escalón medido se conserva (y con él su ``source``).
    """
    current = _as_mapping(row.get("funnel"))
    merged: dict[str, Any] = {}
    for step in FUNNEL_STEPS:
        existing = _as_mapping(current.get(step))
        if _maybe_int(existing.get("count")) is not None:
            merged[step] = dict(existing)
        else:
            merged[step] = dict(_as_mapping(rebuilt.get(step)))
    return merged


def enrich_rows_with_evidence(
    rows: Sequence[Mapping[str, Any]], evidence_by_day: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """(PURA) Rellena los huecos DECLARADOS de cada fila con la evidencia del runner (``--forward``).

    Sólo actúa en los campos que la fila declaró ``None``. El funnel se RECONSTRUYE con la MISMA función
    del instrumento (``build_operability_funnel``) para no abrir una segunda aritmética, pero de ahí se
    toman **sólo** los escalones que la fila dejó en ``None`` (``_fill_funnel_gaps``): un escalón YA
    medido **jamás** se sobrescribe. Un día sin evidencia se devuelve intacto: el hueco sigue declarado.
    """
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        evidence = _as_mapping(evidence_by_day.get(_text(row.get("day"))))
        if not evidence:
            enriched_rows.append(enriched)
            continue
        rebuilt = build_operability_funnel(row, evidence=evidence)
        enriched["funnel"] = _fill_funnel_gaps(row, rebuilt)
        if enriched.get("symbolsObserved") is None:
            enriched["symbolsObserved"] = _maybe_int(evidence.get("watchSize"))
        if enriched.get("pairCapable") is None:
            enriched["pairCapable"] = pair_capable(evidence)
        if enriched.get("pairActive") is None:
            enriched["pairActive"] = pair_active(evidence)
        if enriched.get("priceSources") is None:
            price = _evidence_price_counts(evidence.get("priceSources"))
            if price is not None:
                enriched["priceSources"] = price
        enriched_rows.append(enriched)
    return enriched_rows


# ── Render determinista (texto) ────────────────────────────────────────────────────────────────


def _number(value: Any) -> str:
    return "n/d" if value is None else f"{float(value):.4f}"


def _cell_count(value: Any) -> str:
    number = _maybe_int(value)
    return "n/d" if number is None else str(number)


def _format_table(headers: Sequence[str], table: Sequence[Sequence[str]]) -> list[str]:
    widths: list[int] = []
    for index in range(len(headers)):
        widths.append(max([len(headers[index]), *[len(cells[index]) for cells in table]]))

    def _format(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    lines = [_format(headers), _format(tuple("-" * width for width in widths))]
    lines.extend(_format(cells) for cells in table)
    return lines


def _series_table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    headers = ("Dia", "D", "Regimen", "ENTRY", "VETOS", "FILLS", "CYCLES", "R", "Estado")
    table: list[tuple[str, ...]] = []
    for index, row in enumerate(rows, start=1):
        table.append(
            (
                str(row.get("day") or ""),
                f"D{index}",
                str(row.get("regime") or "-"),
                _cell_count(row.get("decided")),
                _cell_count(row.get("vetoCounted")),
                _cell_count(row.get("fills")),
                _cell_count(row.get("measurableCycles")),
                _number(row.get("rMean")),
                str(row.get("state") or ""),
            )
        )
    return _format_table(headers, table)


def _funnel_lines(totals: Mapping[str, Any]) -> list[str]:
    funnel = _as_mapping(totals.get("funnel"))
    lines: list[str] = []
    for step in FUNNEL_STEPS:
        entry = _as_mapping(funnel.get(step))
        count = _maybe_int(entry.get("count"))
        days = _maybe_int(entry.get("days")) or 0
        of_days = _maybe_int(totals.get("daysMeasured")) or 0
        rendered = "n/d" if count is None or days == 0 else str(count)
        lines.append(f"  {step:<14} {rendered:>6}  ({days}/{of_days} dias medidos)")
    return lines


def _rate_lines(rates: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for name in (
        "topNExclusionRate",
        "riskRejectionRate",
        "reservationFailureRate",
        "fillRate",
        "cycleRate",
        "unresolvedRate",
    ):
        rate = _as_mapping(rates.get(name))
        value = rate.get("rate")
        numerator = rate.get("numerator")
        denominator = rate.get("denominator")
        days = _maybe_int(rate.get("coveredDays")) or 0
        detail = "n/d" if numerator is None else f"{numerator}/{denominator}"
        lines.append(f"  {name:<26} {_number(value):>8}  ({detail}, {days} dia(s))")
    lines.append(
        "  # unresolvedRate: dias MEDIDOS en estado 'unresolved' (indicador, NO tasa de propuestas)"
    )
    return lines


def render_window_audit(
    rows: Sequence[Mapping[str, Any]], meta: Mapping[str, Any] | None = None
) -> str:
    """(PURA) Auditoría legible: serie ``D1..Dn`` + ``TOTAL`` + funnel agregado + tasas + avisos."""
    rows = list(rows)
    audit = window_audit(rows)
    totals = _as_mapping(audit.get("totals"))
    gate = _as_mapping(audit.get("gate"))
    header = _as_mapping(_as_mapping(meta).get("header"))

    versions = ", ".join(str(value) for value in (header.get("versions") or [])) or "(ninguna)"
    lines = [
        "AUTO MARKET WINDOW AUDIT (V2.83 · AUTO-MATERIAL-11) — read-only, sin motor",
        "=" * 92,
        (
            f"cuenta {header.get('account') or '(n/d)'}  ·  versiones {versions}"
            f"  ·  capturado {header.get('capturedAt') or '(n/d)'}"
            f"  ·  dias {audit.get('daysTotal')} ({audit.get('daysMeasured')} medidos)"
        ),
        "",
        "Serie diaria (D1..Dn; n/d = no medido, nunca 0):",
        *_series_table(rows),
        "",
        "TOTAL acumulado (solo dias medidos; 'partial' = TOTAL sobre dias incompletos):",
    ]

    counts = _as_mapping(totals.get("counts"))
    coverage = _as_mapping(totals.get("coverage"))
    for field in AUDIT_TOTAL_FIELDS:
        cover = _as_mapping(coverage.get(field))
        flag = "  [partial]" if bool(cover.get("partial")) else ""
        lines.append(
            f"  {field:<20} {_cell_count(counts.get(field)):>6}"
            f"  ({_maybe_int(cover.get('days')) or 0}/{_maybe_int(cover.get('ofDays')) or 0} dias){flag}"
        )
    r_cover = _as_mapping(coverage.get("rSum"))
    lines.append(
        f"  {'rSum':<20} {_number(totals.get('rSum')):>6}"
        f"  ({_maybe_int(r_cover.get('days')) or 0}/{_maybe_int(r_cover.get('ofDays')) or 0} dias)"
    )

    lines.extend(["", "Funnel agregado (n/d = no medido, nunca 0):", *_funnel_lines(totals)])
    lines.extend(["", "Tasas de operabilidad:", *_rate_lines(_as_mapping(audit.get("rates")))])

    lines.extend(
        [
            "",
            "GATE DE LA VENTANA (>= 4 dias, >= 2 episodios, >= 32 ciclos medibles):",
            (
                f"  dias={_maybe_int(gate.get('days')) or 0}/{_maybe_int(gate.get('minDays')) or 0}"
                f"  episodios={_maybe_int(gate.get('episodes')) or 0}/{_maybe_int(gate.get('minEpisodes')) or 0}"
                f"  ciclos={_maybe_int(gate.get('cycles')) or 0}/{_maybe_int(gate.get('minCycles')) or 0}"
                f"  =>  {gate.get('verdict') or 'INCONCLUSIVE'}"
            ),
        ]
    )
    if not bool(gate.get("ready")):
        lines.append("  (INCONCLUSIVE / NO MEDIDO: la ventana aun no acredita diversidad de mercado)")

    warnings = _as_list(audit.get("warnings"))
    lines.append("")
    lines.append("AVISOS:")
    if not warnings:
        lines.append("  (ninguno)")
    for warning in warnings:
        item = _as_mapping(warning)
        day = _text(item.get("day"))
        prefix = f"{day} " if day else ""
        lines.append(f"  [{item.get('level')}] {prefix}{item.get('message')}")

    lines.append("")
    lines.append(
        "Nota: ENTRY = decisiones de entrada; VETOS = vetos PUROS; los eventos de POSICION NO son vetos. "
        "Un hueco se declara n/d (None), nunca 0."
    )
    return "\n".join(lines)
