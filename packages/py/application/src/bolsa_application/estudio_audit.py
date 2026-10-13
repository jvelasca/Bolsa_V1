"""`P2` (sello 2) — Auditoría por VALOR de ESTUDIO: estrategia + porqué + señal + resultado.

Origen: hueco **`P2`** de la auditoría profundizada (DÍA-D enlazado al ciclo + auditoría por
valor). El sello 1 (`v2.88.112-beta`) enlazó la verificación DÍA-D con su ciclo; este módulo
**compone**, por valor, las cuatro capas que hoy viven dispersas:

* **estrategia elegida** — identidad EXACTA (``presetKey`` + ``version``), la clave de unión
  H1 que el ciclo sella (``strategyPresetKey``).
* **porqué** — ``definition.indicatorSpecs`` + ``coachFacts.recommendations[]``, si el llamante
  los aporta; ausente ⇒ hueco declarado (nunca se inventa una explicación).
* **señal** — los ciclos de la ventana para ese valor: su recuento (``signal``) y la **lista
  enlazable** (``cycles[]`` con ``cycleId``/entrada/salida/identidad/``realizedR``), la clave
  canónica que permite navegar del informe por valor a la **operación** (un ciclo sin ``cycleId``
  se declara hueco; nunca se inventa una clave para forzar el enlace).
* **resultado** — en **R** (feedback por valor) y en **dinero** (reporte financiero OOS).

Diseño (alineado con el proyecto):

* **Puro y determinista**: sin DB, red ni reloj. Entran piezas ya calculadas, sale el informe.
* **Clave de unión EXACTA (H1)**: el dinero se atribuye al valor por ``presetKey`` cuando se
  conoce; si dos ciclos del mismo valor declaran identidades distintas, la unión es **ambigua**
  ⇒ hueco declarado (nunca se elige una «ganadora»).
* **Honestidad** (doctrina «Sin dato todavía», ``UNKNOWN ≠ 0``): un valor solo se declara
  ``measured`` si **ambas** mitades (R y dinero) alcanzan su **suelo de muestra**; en otro caso
  los ratios son ``None`` y el motivo viaja en ``unmeasured`` — **jamás** un ``0`` que finja
  medición. ``pointCitable = False`` (banda ``K`` sin medir): un punto no es propiedad del motor.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DEFAULT_MIN_CYCLES",
    "DEFAULT_MIN_TRADES",
    "ESTUDIO_AUDIT_KIND",
    "EstudioAuditReport",
    "build_estudio_audit_report",
]

#: Suelo de muestra de la mitad **R** (mismo que el feedback por valor: ``MIN_VALUE_CYCLES``).
DEFAULT_MIN_CYCLES = 5
#: Suelo de muestra de la mitad **dinero** (mismo que el reporte financiero OOS).
DEFAULT_MIN_TRADES = 10
#: Marcador del read-model (contrato estable para consumidores).
ESTUDIO_AUDIT_KIND = "AUTO_ESTUDIO_AUDIT_V1"

_POINT_CITABLE_REASON = (
    "El replay OOS es un sorteo del venue: la banda de K=12 sorteos cruza el cero "
    "(v2.88.16.3) ⇒ el punto NO es una propiedad del motor. Cítese la banda, no el punto."
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite(value: Any) -> float | None:
    """Número finito o ``None`` (un valor ilegible es hueco, no ``0``)."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _count(value: Any) -> int:
    number = _finite(value)
    return int(number) if number is not None and number > 0 else 0


def _first_distinct(values: Sequence[str | None]) -> tuple[str | None, bool]:
    """Único valor no vacío de la secuencia; ``(valor, ambiguo)``.

    Cero valores ⇒ ``(None, False)`` (hueco). Más de uno distinto ⇒ ``(None, True)`` (ambiguo):
    NO se elige una identidad «ganadora».
    """
    distinct = sorted({value for value in values if value})
    if len(distinct) == 1:
        return distinct[0], False
    if not distinct:
        return None, False
    return None, True


@dataclass(frozen=True, slots=True)
class EstudioAuditReport:
    """Auditoría por valor de ESTUDIO: una entrada por valor, con huecos declarados."""

    values: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    notes: tuple[str, ...]
    point_citable: bool = False
    point_citable_reason: str = _POINT_CITABLE_REASON

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": ESTUDIO_AUDIT_KIND,
            "readOnly": True,
            "pointCitable": self.point_citable,
            "pointCitableReason": self.point_citable_reason,
            "summary": dict(self.summary),
            "values": [dict(value) for value in self.values],
            "notes": list(self.notes),
        }


def _signal_for_symbol(
    cycles: Sequence[Mapping[str, Any]],
    *,
    linked_cycles: int,
    unlinked_cycles: int,
    duplicate_cycles: int,
) -> dict[str, Any]:
    """Recuento de la señal de un valor, con el desglose **enlazables / sin enlazar / repetidos**.

    ``cycles`` es el total de ciclos; ``linkedCycles`` los que traen ``cycleId`` y por tanto
    ``len(cycles[])`` (el invariante que se sostiene por construcción); ``unlinkedCycles`` los
    que no declaran ``cycleId`` (no enlazables); ``duplicateCycles`` los que repetían una clave
    ya listada (deduplicados). ``linkedCycles + unlinkedCycles + duplicateCycles == cycles``.
    """
    return {
        "cycles": len(cycles),
        "linkedCycles": linked_cycles,
        "unlinkedCycles": unlinked_cycles,
        "duplicateCycles": duplicate_cycles,
        "measuredCycles": sum(1 for cycle in cycles if _finite(cycle.get("realizedR")) is not None),
        "daysCovered": len(
            {
                str(cycle.get("entryDay"))
                for cycle in cycles
                if _text(cycle.get("entryDay")) is not None
            }
        ),
    }


_DIGITS_RE = re.compile(r"(\d+)")


def _natural_sort_key(text: str) -> tuple[tuple[int, object], ...]:
    """Clave de orden NATURAL: los tramos numéricos se comparan como números.

    ``cyc-2`` < ``cyc-10`` (el orden lexicográfico los pondría al revés). Determinista y estable;
    un ``cycleId`` sin dígitos se ordena por texto. Evita que el listado quede fuera de orden.
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in _DIGITS_RE.split(text)
        if part != ""
    )


def _cycle_row_signature(row: Mapping[str, Any]) -> str:
    """Firma textual determinista de una fila de ciclo (desempate estable en el dedup)."""
    return "|".join(
        "" if row.get(key) is None else str(row.get(key))
        for key in ("entryDay", "exitDay", "strategyPresetKey", "strategyVersion", "realizedR")
    )


def _cycles_for_symbol(
    cycles: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Ciclos del valor con la clave canónica para **enlazar** con la operación (PURA).

    Lista ordenada de forma NATURAL por ``cycleId`` (``cyc-2`` antes que ``cyc-10``) y **deduplicada**
    por ``cycleId``, con los campos que el ciclo ya sella (día de entrada/salida, identidad de
    estrategia y ``realizedR``). Solo se listan ciclos con ``cycleId`` legible: sin esa clave no hay
    enlace canónico a la operación. Los que no la declaran se **cuentan** aparte (``unlinked``) y las
    claves repetidas también (``duplicates``) para declarar el hueco — nunca se descartan en silencio.
    Un campo ausente es ``None`` (hueco declarado, jamás ``""``/``0``).

    El orden de llegada NO decide: se ordena por ``(cycleId natural, firma de la fila)`` ANTES de
    deduplicar, así que dos ciclos con el MISMO ``cycleId`` no eligen «ganadora» por permutación.
    """
    candidates: list[tuple[str, dict[str, Any]]] = []
    unlinked = 0
    for cycle in cycles:
        cycle_id = _text(cycle.get("cycleId"))
        if not cycle_id:
            unlinked += 1
            continue
        candidates.append(
            (
                cycle_id,
                {
                    "cycleId": cycle_id,
                    "entryDay": _text(cycle.get("entryDay")),
                    "exitDay": _text(cycle.get("exitDay")),
                    "strategyPresetKey": _text(cycle.get("strategyPresetKey")),
                    "strategyVersion": _text(cycle.get("strategyVersion")),
                    "realizedR": _finite(cycle.get("realizedR")),
                },
            )
        )
    candidates.sort(key=lambda item: (_natural_sort_key(item[0]), _cycle_row_signature(item[1])))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0
    for cycle_id, row in candidates:
        if cycle_id in seen:
            duplicates += 1
            continue
        seen.add(cycle_id)
        rows.append(row)
    return rows, unlinked, duplicates


def _strategy_for_symbol(cycles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    preset, preset_ambiguous = _first_distinct(
        [_text(cycle.get("strategyPresetKey")) for cycle in cycles]
    )
    version, version_ambiguous = _first_distinct(
        [_text(cycle.get("strategyVersion")) for cycle in cycles]
    )
    return {
        "presetKey": preset,
        "version": version,
        "presetKeyAmbiguous": preset_ambiguous,
        "versionAmbiguous": version_ambiguous,
    }


def _pick_finance_group(
    groups: Sequence[Mapping[str, Any]], *, preset_key: str | None
) -> Mapping[str, Any] | None:
    """Elige el grupo financiero del valor por la clave EXACTA ``presetKey``.

    Precedencia: (1) grupo con ``strategyPresetKey`` == ``preset_key``; (2) si el valor no
    declara identidad **o** el único grupo tampoco la declara, ese grupo ÚNICO; (3) si hay
    varios candidatos sin clave, es **ambiguo** ⇒ ``None`` (hueco declarado, no se elige uno).
    Un grupo que declara OTRA identidad nunca se atribuye a este valor (sería dinero de otra
    estrategia, justo el hueco que H1 cierra).
    """
    if preset_key:
        for group in groups:
            if _text(group.get("strategyPresetKey")) == preset_key:
                return group
    without_key = [group for group in groups if _text(group.get("strategyPresetKey")) is None]
    # Fallback "grupo único" sólo si el valor NO declara identidad, o el único grupo tampoco
    # la declara. Con identidad declarada y sin coincidencia, un grupo con OTRA clave no se usa.
    if len(groups) == 1 and (preset_key is None or len(without_key) == 1):
        return groups[0]
    if len(without_key) == 1:
        return without_key[0]
    return None


def _money_bucket(
    group: Mapping[str, Any] | None, *, min_trades: int
) -> tuple[dict[str, Any], list[str]]:
    if group is None:
        return (
            {
                "trades": 0,
                "netReturnPct": None,
                "netReturnPctAtStress": None,
                "maxDrawdownPct": None,
                "hitRate": None,
                "committedCapital": None,
                "measured": False,
                "sampleFloor": min_trades,
            },
            ["dinero: sin grupo financiero para el valor (Sin dato todavía)"],
        )
    trades = _count(group.get("trades"))
    net = _finite(group.get("netReturnPct"))
    measured = trades >= max(1, min_trades) and net is not None
    bucket = {
        "trades": trades,
        "netReturnPct": net,
        "netReturnPctAtStress": _finite(group.get("netReturnPctAtStress")),
        "maxDrawdownPct": _finite(group.get("maxDrawdownPct")),
        "hitRate": _finite(group.get("hitRate")),
        "committedCapital": _finite(group.get("committedCapital")),
        "measured": measured,
        "sampleFloor": min_trades,
    }
    reasons: list[str] = []
    if trades < max(1, min_trades):
        reasons.append(
            f"dinero: {trades} round-trips < suelo {min_trades} ⇒ ratios sin dato"
        )
    elif net is None:
        reasons.append("dinero: retorno neto sin dato (grupo sin medir)")
    return bucket, reasons


def _r_bucket(value: Mapping[str, Any], *, min_cycles: int) -> tuple[dict[str, Any], list[str]]:
    measured_cycles = _count(value.get("measuredCycles"))
    expectancy = _finite(value.get("expectancyR"))
    measured = measured_cycles >= max(1, min_cycles) and expectancy is not None
    bucket = {
        "verdict": str(value.get("verdict") or "NOT_MEASURED"),
        "verdictReason": _text(value.get("verdictReason")),
        "evidenceQuality": str(value.get("evidenceQuality") or "NOT_MEASURED"),
        "expectancyR": expectancy,
        "hitRate": _finite(value.get("hitRate")),
        "realizedRTotal": _finite(value.get("realizedRTotal")),
        "measuredCycles": measured_cycles,
        "daysCovered": _count(value.get("daysCovered")),
        "measured": measured,
        "sampleFloor": min_cycles,
    }
    reasons: list[str] = []
    if measured_cycles < max(1, min_cycles):
        reasons.append(
            f"R: {measured_cycles} ciclos medidos < suelo {min_cycles} ⇒ ratios sin dato"
        )
    return bucket, reasons


def build_estudio_audit_report(
    *,
    values: Sequence[Mapping[str, Any]] = (),
    cycles: Sequence[Mapping[str, Any]] = (),
    finance_groups: Sequence[Mapping[str, Any]] = (),
    why_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    min_cycles: int = DEFAULT_MIN_CYCLES,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> EstudioAuditReport:
    """Compone la auditoría por valor de ESTUDIO (pura y determinista).

    ``values`` son las fichas por valor del feedback (``build_value_scorecard``). ``cycles`` el
    índice de ciclos (``build_cycle_index``). ``finance_groups`` los grupos del reporte
    financiero OOS (``oos_finance.to_dict()["groups"]``). ``why_by_symbol`` (opcional) aporta el
    «porqué» por valor: ``{"indicatorSpecs": [...], "recommendations": [...]}``; ausente ⇒ hueco.

    Salida ordenada por símbolo (mismo estado ⇒ mismo payload). Nunca fabrica: ``presetKey``
    ausente o **ambiguo** ⇒ ``None`` (hueco declarado); un valor sin **ambas** mitades medidas
    aparece en ``unmeasured`` con ratios ``None``.
    """
    why = why_by_symbol or {}

    cycles_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for cycle in cycles or ():
        symbol = _text(cycle.get("symbol"))
        if symbol:
            cycles_by_symbol.setdefault(symbol, []).append(cycle)

    groups_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for finance_row in finance_groups or ():
        finance_symbol = _text(finance_row.get("symbol"))
        if finance_symbol:
            groups_by_symbol.setdefault(finance_symbol, []).append(finance_row)

    symbol_set: set[str] = set()
    for value_row in values or ():
        name = _text(value_row.get("symbol"))
        if name:
            symbol_set.add(name)
    ordered_symbols = sorted(symbol_set)

    entries: list[dict[str, Any]] = []
    measured_count = 0
    with_preset = 0
    for symbol in ordered_symbols:
        value = next(
            (row for row in values or () if _text(row.get("symbol")) == symbol), {}
        )
        symbol_cycles = cycles_by_symbol.get(symbol, [])
        symbol_cycle_rows, unlinked_cycles, duplicate_cycles = _cycles_for_symbol(symbol_cycles)
        strategy = _strategy_for_symbol(symbol_cycles)
        signal = _signal_for_symbol(
            symbol_cycles,
            linked_cycles=len(symbol_cycle_rows),
            unlinked_cycles=unlinked_cycles,
            duplicate_cycles=duplicate_cycles,
        )
        r_bucket, r_reasons = _r_bucket(value, min_cycles=min_cycles)
        symbol_groups = groups_by_symbol.get(symbol, [])
        group = _pick_finance_group(symbol_groups, preset_key=strategy["presetKey"])
        money_bucket, money_reasons = _money_bucket(group, min_trades=min_trades)
        # Si existían grupos del símbolo pero ninguno declara la identidad del valor, el hueco
        # NO es "sin grupo" (mensaje genérico engañoso) sino "sin grupo con ESA identidad": se
        # declara tal cual para no sugerir que el dinero simplemente no viajó.
        if group is None and symbol_groups and strategy["presetKey"]:
            money_reasons = [
                f"dinero: los grupos del símbolo no declaran la identidad "
                f"'{strategy['presetKey']}' (Sin dato todavía)"
            ]

        why_row = why.get(symbol) or {}
        indicator_specs = why_row.get("indicatorSpecs")
        recommendations = why_row.get("recommendations")

        unmeasured = [*r_reasons, *money_reasons]
        if strategy["presetKey"] is None:
            unmeasured.append(
                "estrategia: identidad (presetKey) ambigua"
                if strategy["presetKeyAmbiguous"]
                else "estrategia: el ciclo no declara presetKey (Sin dato todavía)"
            )
        if indicator_specs is None and recommendations is None:
            unmeasured.append("porqué: la definición no viaja en el artefacto (Sin dato todavía)")
        if unlinked_cycles:
            unmeasured.append(
                f"señal: {unlinked_cycles} ciclo(s) sin cycleId "
                "(no enlazables a la operación)"
            )
        if duplicate_cycles:
            unmeasured.append(
                f"señal: {duplicate_cycles} ciclo(s) con cycleId repetido "
                "(deduplicados por su clave canónica)"
            )

        measured = bool(r_bucket["measured"] and money_bucket["measured"])
        if measured:
            measured_count += 1
        if strategy["presetKey"]:
            with_preset += 1

        entries.append(
            {
                "symbol": symbol,
                "strategy": {
                    "presetKey": strategy["presetKey"],
                    "version": strategy["version"],
                },
                "why": {
                    "indicatorSpecs": list(indicator_specs) if indicator_specs else None,
                    "recommendations": list(recommendations) if recommendations else None,
                },
                "signal": signal,
                "cycles": symbol_cycle_rows,
                "resultR": r_bucket,
                "money": money_bucket,
                "measured": measured,
                "unmeasured": unmeasured,
            }
        )

    summary = {
        "values": len(entries),
        "measured": measured_count,
        "unmeasured": len(entries) - measured_count,
        "withPresetKey": with_preset,
        "withoutPresetKey": len(entries) - with_preset,
    }
    notes: list[str] = [
        "Read-only: compone piezas YA calculadas (feedback R + reporte financiero OOS); no "
        "recalcula el motor.",
        "Un valor solo se declara «medido» si R y dinero alcanzan su suelo de muestra; en otro "
        "caso los ratios son None (nunca 0).",
        "La unión del dinero a la estrategia usa la clave EXACTA presetKey (H1); ambigua ⇒ hueco.",
        "Cada valor lista sus ciclos por cycleId (entrada/salida/identidad/realizedR) para enlazar "
        "con la operación; el recuento signal.linkedCycles == len(cycles[]) y los ciclos sin "
        "cycleId o con clave repetida se declaran, no se descartan en silencio.",
    ]
    return EstudioAuditReport(
        values=tuple(entries), summary=summary, notes=tuple(notes)
    )
