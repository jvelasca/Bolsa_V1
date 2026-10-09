"""PAPER-2 — conciliación de la evidencia durable PAPER (READ-ONLY, PURA).

Qué cierra, exactamente: el [contrato de evidencia PAPER](../../../../docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md)
define **siete criterios** de suficiencia, pero un contrato que solo cuenta filas no distingue
"hay N cierres" de "esos N cierres **cuadran** con las ejecuciones que los produjeron". Este
módulo aporta la mitad que faltaba: los **cruces falsables** entre operaciones, ejecuciones,
cierres y resultados, con la procedencia de cada cifra y la contradicción **declarada**.

Reglas duras, declaradas en vez de asumidas:

* **Sin dato no es cero.** Un recuento que no se pudo medir viaja ``None``/``UNKNOWN``; jamás se
  colapsa a un ``0`` que afirmaría "no lo hay" cuando la verdad es "no lo miré" (``UNKNOWN ≠ 0``).
* **Un cruce que no cuadra se declara, no se descarta.** Una ejecución duplicada, un fill huérfano
  (sin ciclo), un settlement sin cierre probado, una cantidad desequilibrada o un PnL discrepante
  se publican como **contradicción**; la capa que decide puede entonces no dar el criterio por
  cumplido. Un agregado "optimista" que suma solo lo que cuadra es un **suelo**, no el total.
* **Una sola noción de cierre.** Los ciclos cerrados y su PnL FIFO salen de ``cycles_from_fills``
  (``AUTO-7``), la MISMA autoridad que alimenta el informe, la confianza y el readiness. Este
  módulo no reimplementa un segundo FIFO: si divergiera, la calibración y la conciliación
  medirían ciclos distintos y nadie lo vería.
* **Un cruce sin AMBAS mediciones no reconcilia (PAPER-2.1).** Si falta el PnL FIFO del material,
  el PnL del cierre o la cantidad cerrada declarada, el ciclo **no** se da por conciliado
  (``settlement_pnl_unmeasured`` / ``settlement_quantity_unmeasured``): la ausencia no se confunde
  con un cero. Un ciclo con **dos** cierres durables se declara (``duplicate_settlement_cycle``) y
  bloquea su conciliación limpia en vez de sobrescribir el primero.

Puro y determinista: sin I/O, sin red, sin reloj. La lectura de las filas es del llamante.

@see packages/py/application/src/bolsa_application/applied_cost.py (AUTO-16/17: coste y balance)
@see packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py (cycles_from_fills)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)

from bolsa_application.applied_cost import (
    APPLIED_COST_UNBALANCED_ROUND_TRIP,
    APPLIED_COST_WITHOUT_ROUND_TRIP,
    applied_cost_from_fills,
)
from bolsa_application.auto_self_evaluation_feed import cycles_from_fills

__all__ = [
    "RECON_DUPLICATE_EXECUTION",
    "RECON_DUPLICATE_SETTLEMENT",
    "RECON_MULTIPLE_VERSIONS",
    "RECON_ORPHAN_FILL",
    "RECON_PNL_MISMATCH",
    "RECON_PNL_UNMEASURED",
    "RECON_QTY_MISMATCH",
    "RECON_QTY_UNMEASURED",
    "RECON_SETTLEMENT_WITHOUT_ACCOUNT",
    "RECON_SETTLEMENT_WITHOUT_CLOSURE",
    "CycleEvidence",
    "PaperEvidenceReconciliation",
    "reconcile_paper_evidence",
]

#: El mismo ``execution_id`` aparece más de una vez: una ejecución no se cuenta dos veces.
RECON_DUPLICATE_EXECUTION = "duplicate_execution_id"
#: Hay fills sin ``cycle_id`` (legacy anterior a la 044): no se puede atribuir su operación.
RECON_ORPHAN_FILL = "fill_without_cycle"
#: Un cierre durable (``auto_cycle_settlement``) que NO casa con ningún ciclo cerrado del material.
RECON_SETTLEMENT_WITHOUT_CLOSURE = "settlement_without_closed_cycle"
#: El PnL del cierre discrepa del PnL FIFO del material más allá de la tolerancia declarada.
RECON_PNL_MISMATCH = "settlement_pnl_mismatch"
#: El PnL del cierre (o el FIFO del material) NO se pudo MEDIR: no reconcilia (``UNKNOWN ≠ 0``).
#: Un PnL ausente NUNCA se colapsa a ``0`` para poder cerrar el cruce.
RECON_PNL_UNMEASURED = "settlement_pnl_unmeasured"
#: La cantidad cerrada del settlement no cuadra con el round-trip balanceado del material.
RECON_QTY_MISMATCH = "settlement_quantity_mismatch"
#: La cantidad cerrada del settlement NO se declaró: no se puede probar el cierre ⇒ no reconcilia.
RECON_QTY_UNMEASURED = "settlement_quantity_unmeasured"
#: El MISMO ciclo declara DOS cierres durables: la duplicidad se declara, no se sobrescribe.
RECON_DUPLICATE_SETTLEMENT = "duplicate_settlement_cycle"
#: Un cierre durable sin cuenta atribuible al ámbito consultado: no se incorpora como evidencia.
RECON_SETTLEMENT_WITHOUT_ACCOUNT = "settlement_without_account"
#: El ciclo declara DOS versiones de estrategia: la atribución no se reparte, se declara.
RECON_MULTIPLE_VERSIONS = "cycle_with_multiple_versions"

#: Tolerancia de la cantidad (misma cuantización que ``applied_cost``: ``1e-6``).
_QTY = Decimal("0.000001")
#: Tolerancia declarada del cruce de PnL. Parametrizable por el llamante; no se baja para forzar
#: un veredicto. Ambos números salen de la MISMA aritmética Decimal, así que solo absorbe ruido
#: de serialización, no una discrepancia real.
_PNL = Decimal("0.01")


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _dec(value: Any) -> Decimal | None:
    """Decimal finito del valor, o ``None`` (nunca un cero de relleno)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def _field_of(raw: Any, *names: str) -> Any:
    """Primer campo presente de un ``Mapping`` o de un objeto (contrato del lector)."""
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return None
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return None


def _version_of(row: Any) -> str:
    return _text(_field_of(row, "strategy_version_id", "strategyVersion"))


def _cycle_of(row: Any) -> str:
    return _text(_field_of(row, "cycle_id", "cycleId"))


def _measurement(value: Any) -> MeasurementStatus:
    """Estado de medición válido, o ``UNKNOWN`` (nunca se asciende a ``COMPLETE``)."""
    text = _text(value).upper()
    if text == MEASUREMENT_COMPLETE:
        return MEASUREMENT_COMPLETE
    if text == MEASUREMENT_PARTIAL:
        return MEASUREMENT_PARTIAL
    return MEASUREMENT_UNKNOWN


def _instant(value: Any) -> datetime | None:
    """Instante legible de un ``created_at`` (``datetime`` o ISO-8601), o ``None``."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


@dataclass(frozen=True, slots=True)
class CycleEvidence:
    """La evidencia conciliada de UN ciclo: material bruto, cierre durable y cruces.

    Los ejes son independientes a propósito (mismo contrato que ``CycleRisk``): un ciclo puede
    tener material balanceado y a la vez un settlement que discrepa, y eso hay que poder
    declararlo sin perder ninguno de los dos hechos.
    """

    cycle_id: str
    strategy_version: str | None
    fills: int
    buy_qty: Decimal | None
    sell_qty: Decimal | None
    both_sides: bool
    balanced: bool
    closed: bool
    fifo_pnl: Decimal | None
    settlement_present: bool
    settlement_pnl: Decimal | None
    settlement_pnl_measurement: MeasurementStatus
    settlement_closed_qty: Decimal | None
    reconciled: bool
    cost_measurement: MeasurementStatus
    cost_complete: bool
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycleId": self.cycle_id,
            "strategyVersion": self.strategy_version,
            "fills": self.fills,
            "buyQty": None if self.buy_qty is None else str(self.buy_qty),
            "sellQty": None if self.sell_qty is None else str(self.sell_qty),
            "bothSides": self.both_sides,
            "balanced": self.balanced,
            "closed": self.closed,
            "fifoPnl": None if self.fifo_pnl is None else str(self.fifo_pnl),
            "settlementPresent": self.settlement_present,
            "settlementPnl": None if self.settlement_pnl is None else str(self.settlement_pnl),
            "settlementPnlMeasurement": self.settlement_pnl_measurement,
            "settlementClosedQty": (
                None if self.settlement_closed_qty is None else str(self.settlement_closed_qty)
            ),
            "reconciled": self.reconciled,
            "costMeasurement": self.cost_measurement,
            "costComplete": self.cost_complete,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class PaperEvidenceReconciliation:
    """El material conciliado: contadores por ciclo, cruces globales y contradicciones.

    ``*_loaded`` distingue "la fuente se leyó y está vacía" de "la fuente no se pudo leer": sin
    esa distinción, un fallo de lectura se leería como material limpio. Los recuentos nullable
    viajan ``int`` cuando se midieron y no se inventan cuando no.
    """

    fills_loaded: bool
    settlements_loaded: bool
    fills_total: int
    fills_with_cycle: int
    duplicate_executions: int
    orphan_executions: int
    closed_cycles: int
    anonymous_closed_cycles: int
    window_days: int | None
    window_episodes: int | None
    settlements_total: int
    settlements_reconciled: int
    settlements_divergent: int
    settlements_unmatched: int
    cycles: tuple[CycleEvidence, ...]
    contradictions: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fillsLoaded": self.fills_loaded,
            "settlementsLoaded": self.settlements_loaded,
            "fillsTotal": self.fills_total,
            "fillsWithCycle": self.fills_with_cycle,
            "duplicateExecutions": self.duplicate_executions,
            "orphanExecutions": self.orphan_executions,
            "closedCycles": self.closed_cycles,
            "anonymousClosedCycles": self.anonymous_closed_cycles,
            "windowDays": self.window_days,
            "windowEpisodes": self.window_episodes,
            "settlementsTotal": self.settlements_total,
            "settlementsReconciled": self.settlements_reconciled,
            "settlementsDivergent": self.settlements_divergent,
            "settlementsUnmatched": self.settlements_unmatched,
            "cycles": [cycle.as_dict() for cycle in self.cycles],
            "contradictions": list(self.contradictions),
            "notes": list(self.notes),
        }


def _duplicate_executions(fills: Sequence[Any]) -> int:
    """Ejecuciones repetidas: ``total - distintas`` (un ``execution_id`` vacío no cuenta)."""
    seen: dict[str, int] = {}
    for fill in fills:
        execution_id = _text(_field_of(fill, "execution_id", "executionId"))
        if execution_id:
            seen[execution_id] = seen.get(execution_id, 0) + 1
    return sum(count - 1 for count in seen.values() if count > 1)


def _balance(fills: Sequence[Any]) -> tuple[Decimal | None, Decimal | None, bool, bool]:
    """``(Σ buy qty, Σ sell qty, ambos lados, balanceado)`` del material bruto de un ciclo.

    La cantidad de una pata sin ``reference_mid`` SÍ cuenta: el cierre es un eje independiente
    de la medición de la fricción (``AUTO-17``). Sin TODAS las cantidades legibles el balance
    **no se puede probar** (``balanced = False``), nunca se supone.
    """
    buys = sells = Decimal("0")
    has_buy = has_sell = False
    readable = True
    for fill in fills:
        side = _text(_field_of(fill, "side")).lower()
        qty = _dec(_field_of(fill, "quantity"))
        if qty is None or qty <= 0:
            readable = False
            continue
        if side == "buy":
            buys += qty
            has_buy = True
        elif side == "sell":
            sells += qty
            has_sell = True
    both_sides = has_buy and has_sell
    balanced = readable and both_sides and abs(buys - sells) <= _QTY
    return buys, sells, both_sides, balanced


def reconcile_paper_evidence(
    *,
    fills: Iterable[Any],
    settlements: Iterable[Any],
    fills_loaded: bool = True,
    settlements_loaded: bool = True,
    unattributed_settlements: int = 0,
    pnl_tolerance: Decimal = _PNL,
) -> PaperEvidenceReconciliation:
    """(PURA) concilia operaciones, ejecuciones, cierres y resultados del material PAPER.

    ``fills`` son las filas durables (``sim_fill_finance_context``) y ``settlements`` los
    payloads de los eventos ``auto_cycle_settlement``. ``fills_loaded``/``settlements_loaded``
    declaran si la lectura se pudo hacer: una fuente no leída deja sus cruces **sin dato**, no
    limpios. ``unattributed_settlements`` cuenta los cierres durables EXCLUIDOS por no declarar
    una cuenta atribuible al ámbito (los aporta el lector): se declaran como contradicción para
    que no puedan leerse como material limpio.

    Para cada ciclo se publica su material bruto (lados, cantidades, balance), si ``cycles_from_fills``
    lo declaró **cerrado** (autoridad de cierre ``AUTO-17``), si hay un settlement durable y si
    ambos **concuerdan**. Un settlement sin cierre, o con cantidad/PnL discrepantes o ausentes, se
    declara como contradicción; jamás se promedia ni se descarta en silencio. Un PnL o una cantidad
    sin medir **no** reconcilia (``UNKNOWN ≠ 0``): la ausencia no se confunde con un cero.
    """
    fill_rows = list(fills)
    settlement_rows = list(settlements)

    # ── Material bruto por ciclo (agrupación estable, sin segundo FIFO) ────────────────────
    grouped: dict[str, list[Any]] = {}
    orphan_executions = 0
    for fill in fill_rows:
        cycle_id = _cycle_of(fill)
        if not cycle_id:
            orphan_executions += 1
            continue
        grouped.setdefault(cycle_id, []).append(fill)

    # ── Autoridad de cierre: el MISMO FIFO que alimenta el informe (AUTO-7) ────────────────
    fifo_cycles = cycles_from_fills(fill_rows)
    #: Pertenecer al mapa = el ciclo está CERRADO; el valor ``None`` = cerrado pero con el PnL
    #: FIFO NO medido. Se conserva ``None`` (jamás un ``0`` de relleno): un PnL ausente no puede
    #: compararse como si fuera cero (``UNKNOWN ≠ 0``).
    closed_pnl: dict[str, Decimal | None] = {}
    closed_version: dict[str, str] = {}
    anonymous_closed_cycles = 0
    for row in fifo_cycles:
        key = _cycle_of(row)
        if not key:
            # Ciclo legacy sin identidad (emparejamiento FIFO de fills previos a la 044): es una
            # operación que el material reconoce pero que NO declara su ciclo. Se CUENTA para
            # que ``operation_lineage`` no pueda darse por cumplido ocultándola.
            anonymous_closed_cycles += 1
            continue
        closed_pnl[key] = _dec(_field_of(row, "pnl"))
        version = _version_of(row)
        if version:
            closed_version[key] = version

    # ── Coste aplicado (AUTO-16) sobre las patas de cada ciclo ─────────────────────────────
    applied_costs = applied_cost_from_fills(
        grouped.keys(), fill_rows, closed_cycle_ids=closed_pnl.keys()
    )

    # ── Cierres durables indexados por ciclo, ignorando los que no declaran ciclo ──────────
    # Un ciclo con DOS cierres durables es una duplicidad DECLARADA, no una sobreescritura: se
    # conserva el PRIMERO (determinista) y se bloquea su conciliación limpia.
    settlements_by_cycle: dict[str, Mapping[str, Any]] = {}
    duplicate_settlement_cycles: set[str] = set()
    duplicate_settlements = 0
    for settlement in settlement_rows:
        key = _cycle_of(settlement)
        if not key:
            continue
        if key in settlements_by_cycle:
            duplicate_settlements += 1
            duplicate_settlement_cycles.add(key)
            continue
        settlements_by_cycle[key] = settlement

    all_keys = sorted(set(grouped) | set(closed_pnl) | set(settlements_by_cycle))
    cycles: list[CycleEvidence] = []
    contradictions: list[str] = []
    reconciled_count = divergent_count = unmatched_count = 0

    for key in all_keys:
        rows = grouped.get(key, [])
        buy_qty, sell_qty, both_sides, balanced = _balance(rows)
        closed = key in closed_pnl
        fifo_pnl = closed_pnl.get(key)
        settlement = settlements_by_cycle.get(key)
        settlement_present = settlement is not None
        settlement_pnl = (
            _dec(_field_of(settlement, "pnl")) if settlement_present else None
        )
        settlement_pnl_measurement = (
            _measurement(_field_of(settlement, "pnlMeasurement"))
            if settlement_present
            else MEASUREMENT_UNKNOWN
        )
        settlement_closed_qty = (
            _dec(_field_of(settlement, "closedQty")) if settlement_present else None
        )

        notes: list[str] = []
        versions = {_version_of(fill) for fill in rows} - {""}
        if len(versions) > 1:
            notes.append(RECON_MULTIPLE_VERSIONS)
        if both_sides and not balanced:
            notes.append(APPLIED_COST_UNBALANCED_ROUND_TRIP)
        elif not both_sides and rows:
            notes.append(APPLIED_COST_WITHOUT_ROUND_TRIP)

        # Duplicidad del cierre: se declara en el propio ciclo (esté cerrado o no). Bloquea su
        # conciliación limpia en vez de sobrescribir el primer cierre en silencio.
        duplicate_here = settlement_present and key in duplicate_settlement_cycles
        if duplicate_here:
            notes.append(RECON_DUPLICATE_SETTLEMENT)
            contradictions.append(f"{RECON_DUPLICATE_SETTLEMENT}:{key}")

        # Cruce cierre↔settlement: la cantidad balanceada del material debe cuadrar con la
        # cantidad cerrada declarada; y el PnL solo reconcilia si AMBOS lados están medidos.
        # La ausencia de cantidad o de PnL NO es un cero: deja el ciclo sin reconciliar.
        reconciled = False
        if settlement_present and closed:
            if settlement_closed_qty is None:
                # Sin cantidad declarada no se puede probar el cierre: no se asume que cuadre.
                qty_ok = False
                notes.append(RECON_QTY_UNMEASURED)
                contradictions.append(f"{RECON_QTY_UNMEASURED}:{key}")
            else:
                qty_ok = (
                    balanced
                    and buy_qty is not None
                    and abs(buy_qty - settlement_closed_qty) <= _QTY
                )
                if not qty_ok:
                    notes.append(RECON_QTY_MISMATCH)
                    contradictions.append(f"{RECON_QTY_MISMATCH}:{key}")

            if fifo_pnl is None:
                # El FIFO del material no declara su PnL: no hay referencia con la que cruzar.
                pnl_ok = False
                notes.append(RECON_PNL_UNMEASURED)
                contradictions.append(f"{RECON_PNL_UNMEASURED}:{key}")
            elif settlement_pnl is None or settlement_pnl_measurement != MEASUREMENT_COMPLETE:
                # El cierre declara un PnL no medido: tampoco reconcilia.
                pnl_ok = False
                notes.append(RECON_PNL_UNMEASURED)
                contradictions.append(f"{RECON_PNL_UNMEASURED}:{key}")
            else:
                pnl_ok = abs(fifo_pnl - settlement_pnl) <= pnl_tolerance
                if not pnl_ok:
                    notes.append(RECON_PNL_MISMATCH)
                    contradictions.append(f"{RECON_PNL_MISMATCH}:{key}")

            reconciled = qty_ok and pnl_ok and not duplicate_here
        elif settlement_present and not closed:
            # Un settlement de un ciclo que el material NO declaró cerrado: o falta material, o
            # el cierre durable es de otra operación. Se declara; no se da por bueno.
            notes.append(RECON_SETTLEMENT_WITHOUT_CLOSURE)
            contradictions.append(f"{RECON_SETTLEMENT_WITHOUT_CLOSURE}:{key}")

        if settlement_present:
            if reconciled:
                reconciled_count += 1
            elif not closed:
                unmatched_count += 1
            else:
                divergent_count += 1

        cost = applied_costs.get(key)
        cost_measurement = (
            _measurement(_field_of(cost, "measurement")) if cost is not None else MEASUREMENT_UNKNOWN
        )
        cost_complete = cost_measurement == MEASUREMENT_COMPLETE

        # Versión: la del cierre FIFO si la hay; si no, la del material (solo si es única).
        resolved_version = closed_version.get(key) or (
            versions.pop() if len(versions) == 1 else None
        )

        cycles.append(
            CycleEvidence(
                cycle_id=key,
                strategy_version=resolved_version,
                fills=len(rows),
                buy_qty=buy_qty,
                sell_qty=sell_qty,
                both_sides=both_sides,
                balanced=balanced,
                closed=closed,
                fifo_pnl=fifo_pnl,
                settlement_present=settlement_present,
                settlement_pnl=settlement_pnl,
                settlement_pnl_measurement=settlement_pnl_measurement,
                settlement_closed_qty=settlement_closed_qty,
                reconciled=reconciled,
                cost_measurement=cost_measurement,
                cost_complete=cost_complete,
                notes=tuple(dict.fromkeys(notes)),
            )
        )

    # Contradicciones globales de atribución (no de un ciclo concreto).
    if orphan_executions:
        contradictions.append(f"{RECON_ORPHAN_FILL}:{orphan_executions}")
    duplicate_executions = _duplicate_executions(fill_rows)
    if duplicate_executions:
        contradictions.append(f"{RECON_DUPLICATE_EXECUTION}:{duplicate_executions}")
    # Cierres duplicados por ciclo: la duplicidad se declara (y bloquea la limpieza del ciclo).
    if duplicate_settlements:
        contradictions.append(f"{RECON_DUPLICATE_SETTLEMENT}:{duplicate_settlements}")
    # Cierres excluidos por NO declarar cuenta atribuible: no son evidencia de esta cuenta.
    if unattributed_settlements:
        contradictions.append(f"{RECON_SETTLEMENT_WITHOUT_ACCOUNT}:{unattributed_settlements}")
    # Un settlement sin ciclo legible no se puede conciliar con nada: se declara.
    unkeyed_settlements = (
        len(settlement_rows) - len(settlements_by_cycle) - duplicate_settlements
    )
    if unkeyed_settlements:
        contradictions.append(f"{RECON_SETTLEMENT_WITHOUT_CLOSURE}:unkeyed:{unkeyed_settlements}")

    result_notes: list[str] = []
    if not fills_loaded:
        result_notes.append("fills_not_loaded")
    if not settlements_loaded:
        result_notes.append("settlements_not_loaded")

    # ── Ventana durable: días con ejecución y episodios (ciclos) observados ────────────────
    # Sin fuente leída la ventana queda SIN DATO (``None``); con fuente leída y vacía es un
    # cero MEDIDO (no un hueco). Una ventana con fills sin instante legible no se puede fechar:
    # se declara ``None`` en los días en vez de inventar una cronología.
    if not fills_loaded:
        window_days: int | None = None
    elif not fill_rows:
        window_days = 0
    else:
        instants = [
            _instant(_field_of(fill, "created_at", "createdAt")) for fill in fill_rows
        ]
        dated = [value for value in instants if value is not None]
        window_days = len({value.date() for value in dated}) if dated else None
    if not fills_loaded:
        window_episodes: int | None = None
    else:
        window_episodes = len(grouped) if fill_rows else 0

    return PaperEvidenceReconciliation(
        fills_loaded=fills_loaded,
        settlements_loaded=settlements_loaded,
        fills_total=len(fill_rows),
        fills_with_cycle=len(fill_rows) - orphan_executions,
        duplicate_executions=duplicate_executions,
        orphan_executions=orphan_executions,
        closed_cycles=len(closed_pnl),
        anonymous_closed_cycles=anonymous_closed_cycles,
        window_days=window_days,
        window_episodes=window_episodes,
        settlements_total=len(settlement_rows),
        settlements_reconciled=reconciled_count,
        settlements_divergent=divergent_count,
        settlements_unmatched=unmatched_count,
        cycles=tuple(cycles),
        contradictions=tuple(contradictions),
        notes=tuple(result_notes),
    )
