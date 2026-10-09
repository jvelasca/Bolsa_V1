"""PAPER-2 — adaptador de evidencia durable PAPER (READ-ONLY, PURO en la composición).

Qué cierra, exactamente: el [contrato PAPER](../../../../docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md)
define **siete criterios** pero el read-model que los evalúa (``paper-confirmation-contract.ts``)
recibe hechos "ya masticados". Este módulo es el eslabón que faltaba: toma el material durable
**conciliado** (``paper_evidence_reconciliation``) y compone, criterio a criterio, lo que la
superficie web consume —con su **procedencia**, su **medición** y sus **huecos declarados**—.

Regla dura (idéntica a la del contrato): **``UNKNOWN ≠ 0`` y ningún dato parcial satisface un
criterio completo.** Un recuento ausente viaja ``None`` + ``UNKNOWN``; jamás un ``0`` que
afirmaría "no lo hay". Ningún criterio se marca ``met`` sin fuente cargada. Y el veredicto es
siempre ``NO_CONFIRMED``: definir la vara **no** es emitir la confirmación.

PAPER-2.1: un PnL o una cantidad de cierre sin medir **no** reconcilia, y un cierre duplicado por
ciclo o sin cuenta atribuible se declara como contradicción. El compositor no necesita código
nuevo: esas contradicciones ya degradan ``closure_reconciliation`` y ``non_contradiction``.

Puro y determinista: sin I/O, sin red, sin reloj (el ``asOf`` lo aporta el llamante). Los
umbrales están espejados desde el contrato TS y son parametrizables, nunca se bajan para forzar
un veredicto.

@see docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md
@see apps/web/src/features/auto-monitor/paper-confirmation-contract.ts (contrato espejo en TS)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)

from bolsa_application.paper_evidence_reconciliation import PaperEvidenceReconciliation

__all__ = [
    "MIN_CLOSED_OPERATIONS",
    "MIN_EPISODES",
    "MIN_REQUIRED_FILLS",
    "MIN_WINDOW_DAYS",
    "PAPER_EVIDENCE_CRITERIA_ORDER",
    "PAPER_EVIDENCE_SCHEMA",
    "PaperEvidenceInput",
    "build_paper_evidence",
]

#: Sello del adaptador. Si cambia un criterio o una fuente, el sello lo declara.
PAPER_EVIDENCE_SCHEMA = "paper_evidence_adapter_v1"

#: Veredicto reservado: el adaptador NUNCA emite la confirmación.
PAPER_EVIDENCE_VERDICT = "NO_CONFIRMED"

# ── Umbrales espejados del contrato TS (``paper-confirmation-contract.ts``) ─────────────────
#: Ventana mínima operativa: ``≥4 días`` (PROJECT_PREMISES §5.1).
MIN_WINDOW_DAYS = 4
#: Episodios mínimos en la ventana: ``≥2``.
MIN_EPISODES = 2
#: Operaciones cerradas mínimas (``DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY``).
MIN_CLOSED_OPERATIONS = 32
#: Fills durables mínimos (dos patas por operación cerrada).
MIN_REQUIRED_FILLS = MIN_CLOSED_OPERATIONS * 2

#: Orden fijo de los criterios, idéntico al del contrato TS.
PAPER_EVIDENCE_CRITERIA_ORDER: tuple[str, ...] = (
    "window",
    "operation_lineage",
    "execution_attribution",
    "closure_reconciliation",
    "cost_coverage",
    "durable_results",
    "non_contradiction",
)

#: Origen durable que demuestra cada criterio, en lenguaje de usuario y ``read-only``.
CRITERION_SOURCES: Mapping[str, str] = {
    "window": "sim_fill_finance_context.created_at · ventana durable de material",
    "operation_lineage": "cycles_from_fills (FIFO durable AUTO-17) · cycle_id (migración 044)",
    "execution_attribution": "sim_fill_finance_context · execution_id / cycle_id",
    "closure_reconciliation": "decision_journal_entries · auto_cycle_settlement",
    "cost_coverage": "applied_cost (AUTO-16) · reference_mid (migración 046)",
    "durable_results": "auto_cycle_settlement · pnl / pnlMeasurement",
    "non_contradiction": "paper_evidence_reconciliation · cruce de cierres",
}

#: Etiqueta del hueco (misma frase que el vocabulario de ``absent-data`` del frontend).
UNMEASURED_LABEL = "Sin dato todavía"


def _status(met: bool) -> str:
    return "met" if met else "unmet"


@dataclass(frozen=True, slots=True)
class PaperEvidenceInput:
    """Hechos normalizados que el adaptador compone (todos ya leídos, sin I/O aquí)."""

    account_id: str | None
    requested_versions: Sequence[str]
    reconciliation: PaperEvidenceReconciliation
    as_of: str | None = None


@dataclass(frozen=True, slots=True)
class _Criterion:
    id: str
    status: str
    measurement: MeasurementStatus
    counts: Mapping[str, Any]
    notes: tuple[str, ...] = field(default=())

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "measurement": self.measurement,
            "source": CRITERION_SOURCES[self.id],
            "counts": dict(self.counts),
            "notes": list(self.notes),
        }


def _num(value: int | None) -> int | None:
    return None if value is None else int(value)


def _window_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    days = rec.window_days
    episodes = rec.window_episodes
    counts = {"days": _num(days), "episodes": _num(episodes)}
    if not rec.fills_loaded or days is None or episodes is None:
        return _Criterion("window", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = days >= MIN_WINDOW_DAYS and episodes >= MIN_EPISODES
    return _Criterion("window", _status(met), MEASUREMENT_COMPLETE, counts)


def _operation_lineage_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    operations = rec.closed_cycles + rec.anonymous_closed_cycles
    with_lineage = rec.closed_cycles
    counts = {
        "operations": _num(operations),
        "withCycleLineage": _num(with_lineage),
        "anonymousOperations": _num(rec.anonymous_closed_cycles),
    }
    if not rec.fills_loaded:
        return _Criterion("operation_lineage", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = operations >= MIN_CLOSED_OPERATIONS and with_lineage == operations
    # Si hay operaciones sin identidad, la medición es PARTIAL (no toda la población declara
    # linaje), pero el número sigue siendo medido: se declara la base, no se oculta.
    measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE
        if rec.anonymous_closed_cycles == 0
        else MEASUREMENT_PARTIAL
    )
    return _Criterion("operation_lineage", _status(met), measurement, counts)


def _execution_attribution_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    fills = rec.fills_total
    attributed = rec.fills_with_cycle
    counts = {
        "fills": _num(fills),
        "attributed": _num(attributed),
        "duplicateExecutions": _num(rec.duplicate_executions),
    }
    if not rec.fills_loaded:
        return _Criterion("execution_attribution", "unknown", MEASUREMENT_UNKNOWN, counts)
    # La ATRIBUCIÓN es cobertura (todas las ejecuciones con su operación). Una ejecución
    # DUPLICADA no es un fallo de atribución: es una contradicción y la paga el criterio
    # ``non_contradiction`` (mismo reparto que el contrato TS, para que ambos evaluadores digan
    # lo mismo sobre el mismo hecho).
    met = fills >= MIN_REQUIRED_FILLS and attributed == fills
    measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE
        if rec.orphan_executions == 0 and rec.duplicate_executions == 0
        else MEASUREMENT_PARTIAL
    )
    return _Criterion("execution_attribution", _status(met), measurement, counts)


def _closure_reconciliation_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    settlements = rec.settlements_total
    reconciled = rec.settlements_reconciled
    counts = {
        "settlements": _num(settlements),
        "reconciled": _num(reconciled),
        "divergent": _num(rec.settlements_divergent),
        "unmatched": _num(rec.settlements_unmatched),
    }
    if not rec.settlements_loaded:
        return _Criterion("closure_reconciliation", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = settlements >= MIN_CLOSED_OPERATIONS and reconciled == settlements
    measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE
        if reconciled == settlements and rec.settlements_divergent == 0
        else MEASUREMENT_PARTIAL
    )
    return _Criterion("closure_reconciliation", _status(met), measurement, counts)


def _cost_coverage_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    expected = rec.closed_cycles
    complete = sum(1 for cycle in rec.cycles if cycle.closed and cycle.cost_complete)
    counts = {"expected": _num(expected), "complete": _num(complete)}
    if not rec.fills_loaded:
        return _Criterion("cost_coverage", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = expected >= MIN_CLOSED_OPERATIONS and complete == expected
    measurement: MeasurementStatus = (
        MEASUREMENT_COMPLETE if complete == expected else MEASUREMENT_PARTIAL
    )
    return _Criterion("cost_coverage", _status(met), measurement, counts)


def _durable_results_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    measured = sum(
        1
        for cycle in rec.cycles
        if cycle.settlement_present
        and cycle.settlement_pnl is not None
        and cycle.settlement_pnl_measurement == MEASUREMENT_COMPLETE
    )
    counts = {"withMeasuredResult": _num(measured)}
    if not rec.settlements_loaded:
        return _Criterion("durable_results", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = measured >= MIN_CLOSED_OPERATIONS
    return _Criterion("durable_results", _status(met), MEASUREMENT_COMPLETE, counts)


def _non_contradiction_criterion(rec: PaperEvidenceReconciliation) -> _Criterion:
    contradictions = len(rec.contradictions)
    counts = {"contradictions": contradictions}
    if not rec.fills_loaded or not rec.settlements_loaded:
        return _Criterion("non_contradiction", "unknown", MEASUREMENT_UNKNOWN, counts)
    met = contradictions == 0
    return _Criterion("non_contradiction", _status(met), MEASUREMENT_COMPLETE, counts)


def _per_version(rec: PaperEvidenceReconciliation, versions: Sequence[str]) -> list[dict[str, Any]]:
    """Desglose por ``strategyVersion``: ninguna versión con 0 queda oculta (se declara).

    Una operación se exige a **cada** versión solicitada (``≥32`` por estrategia). Las versiones
    sin ciclos aparecen con sus contadores en cero **medido**, no ausentes: así no se puede leer
    un total global como si cada estrategia lo cumpliera.
    """
    buckets: dict[str, dict[str, Any]] = {}

    def bucket(key: str) -> dict[str, Any]:
        return buckets.setdefault(
            key,
            {
                "strategyVersion": key,
                "closedOperations": 0,
                "reconciledClosures": 0,
                "measuredResults": 0,
                "completeCosts": 0,
            },
        )

    for cycle in rec.cycles:
        cell = bucket(cycle.strategy_version or "unattributed")
        if cycle.closed:
            cell["closedOperations"] += 1
        if cycle.reconciled:
            cell["reconciledClosures"] += 1
        if cycle.cost_complete:
            cell["completeCosts"] += 1
        if (
            cycle.settlement_present
            and cycle.settlement_pnl is not None
            and cycle.settlement_pnl_measurement == MEASUREMENT_COMPLETE
        ):
            cell["measuredResults"] += 1

    requested = [str(v) for v in versions if str(v).strip()]
    for version in requested:
        bucket(version)
    for cell in buckets.values():
        cell["meetsMinimum"] = cell["closedOperations"] >= MIN_CLOSED_OPERATIONS
    return [buckets[key] for key in sorted(buckets)]


def build_paper_evidence(input: PaperEvidenceInput) -> dict[str, Any]:
    """(PURA) compone los siete criterios del contrato PAPER desde el material conciliado.

    Devuelve el DTO que consume la superficie web: por criterio, su estado (``met``/``unmet``/
    ``unknown``), su medición, su origen durable y sus contadores nullable. El veredicto es
    siempre ``NO_CONFIRMED``: este adaptador **no** promociona.
    """
    rec = input.reconciliation
    criteria: tuple[_Criterion, ...] = (
        _window_criterion(rec),
        _operation_lineage_criterion(rec),
        _execution_attribution_criterion(rec),
        _closure_reconciliation_criterion(rec),
        _cost_coverage_criterion(rec),
        _durable_results_criterion(rec),
        _non_contradiction_criterion(rec),
    )

    met = [c.id for c in criteria if c.status == "met"]
    unmet = [c.id for c in criteria if c.status == "unmet"]
    unknown = [c.id for c in criteria if c.status == "unknown"]
    unmet_or_unmeasured = [c.id for c in criteria if c.status != "met"]

    return {
        "schemaVersion": PAPER_EVIDENCE_SCHEMA,
        "accountId": input.account_id,
        "asOf": input.as_of,
        "readOnly": True,
        # Tipo LITERAL en el contrato: no existe rama que emita la confirmación.
        "verdict": PAPER_EVIDENCE_VERDICT,
        "criteria": [c.as_dict() for c in criteria],
        "metCriterionIds": met,
        "unmetCriterionIds": unmet,
        "unknownCriterionIds": unknown,
        "unmetOrUnmeasuredCriterionIds": unmet_or_unmeasured,
        "contradictions": list(rec.contradictions),
        "perVersion": _per_version(rec, input.requested_versions),
        "blockers": list(rec.notes),
        "reconciliation": rec.as_dict(),
    }
