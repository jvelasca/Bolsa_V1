"""PAPER-2 — adaptador de evidencia durable PAPER (contrato de siete criterios).

Test hermético del módulo puro ``paper_evidence_adapter``: no toca base de datos. Fija las
invariantes que el contrato PAPER no puede romper:

1. Sin fuente leída, TODO criterio es ``unknown`` (``UNKNOWN ≠ 0``), nunca un ``0`` medido.
2. Con material suficiente y conciliado, los siete criterios se cumplen — y el veredicto SIGUE
   siendo ``NO_CONFIRMED``: definir la vara no es emitir la confirmación.
3. Un dato adverso (ejecución duplicada, cierre contradictorio) degrada el criterio que toca y
   NO puede producir evidencia completa.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
from bolsa_application.paper_evidence_adapter import (
    PAPER_EVIDENCE_CRITERIA_ORDER,
    PaperEvidenceInput,
    build_paper_evidence,
)
from bolsa_application.paper_evidence_reconciliation import reconcile_paper_evidence

_VERSION = "orb-trend"


@dataclass(frozen=True, slots=True)
class _Fill:
    execution_id: str
    side: str
    price: Decimal
    quantity: Decimal
    reference_mid: Decimal | None = Decimal("100")
    cycle_id: str | None = None
    strategy_version_id: str | None = _VERSION
    created_at: datetime | None = None


def _cycles(count: int) -> tuple[list[_Fill], list[dict[str, object]]]:
    """``count`` operaciones cerradas, balanceadas y conciliadas, repartidas en varios días."""
    fills: list[_Fill] = []
    settlements: list[dict[str, object]] = []
    for index in range(count):
        cycle = f"cyc-{index:04d}"
        day = datetime(2026, 10, 1, 10, tzinfo=UTC) + timedelta(days=index % 5)
        fills.append(
            _Fill(f"{cycle}#buy", "buy", Decimal("100"), Decimal("10"), cycle_id=cycle, created_at=day)
        )
        fills.append(
            _Fill(
                f"{cycle}#sell",
                "sell",
                Decimal("110"),
                Decimal("10"),
                cycle_id=cycle,
                created_at=day,
            )
        )
        settlements.append(
            {
                "event": "auto_cycle_settlement",
                "cycleId": cycle,
                "pnl": "100",
                "pnlMeasurement": MEASUREMENT_COMPLETE,
                "closedQty": "10",
            }
        )
    return fills, settlements


def _build(fills: list[_Fill], settlements: list[dict[str, object]], **kwargs: object) -> dict:
    rec = reconcile_paper_evidence(fills=fills, settlements=settlements, **kwargs)  # type: ignore[arg-type]
    return build_paper_evidence(
        PaperEvidenceInput(
            account_id="acc-1",
            requested_versions=[_VERSION],
            reconciliation=rec,
            as_of="2026-10-09T00:00:00Z",
        )
    )


def _statuses(dto: dict) -> dict[str, str]:
    return {item["id"]: item["status"] for item in dto["criteria"]}


def test_without_any_loaded_source_every_criterion_is_unknown() -> None:
    """Sin fuente leída, ningún criterio se declara: ``UNKNOWN ≠ 0`` y el veredicto es reservado."""
    dto = _build([], [], fills_loaded=False, settlements_loaded=False)

    assert dto["verdict"] == "NO_CONFIRMED"
    assert _statuses(dto) == {criterion: "unknown" for criterion in PAPER_EVIDENCE_CRITERIA_ORDER}
    assert dto["metCriterionIds"] == []


def test_an_empty_loaded_source_is_measured_but_never_satisfied() -> None:
    """Fuente leída y vacía es un cero MEDIDO: no cumple mínimos, y no se confunde con un hueco."""
    dto = _build([], [])

    statuses = _statuses(dto)
    assert statuses["window"] == "unmet"
    assert statuses["operation_lineage"] == "unmet"
    assert statuses["execution_attribution"] == "unmet"
    assert statuses["non_contradiction"] == "met"  # cero contradicciones es un cero real
    assert dto["verdict"] == "NO_CONFIRMED"


def test_all_seven_met_still_never_emits_the_confirmation() -> None:
    """Con los siete criterios cumplidos el veredicto SIGUE ``NO_CONFIRMED`` (reserva de contrato)."""
    fills, settlements = _cycles(32)
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert set(statuses.values()) == {"met"}, statuses
    assert dto["metCriterionIds"] == list(PAPER_EVIDENCE_CRITERIA_ORDER)
    assert dto["unmetOrUnmeasuredCriterionIds"] == []
    assert dto["verdict"] == "NO_CONFIRMED"
    # El token reservado NO aparece suelto en el payload (frontera de palabra): ``NO_CONFIRMED``
    # es un veredicto reservado, no la confirmación.
    assert re.search(r"\bCONFIRMED\b", json.dumps(dto)) is None


def test_a_duplicate_execution_is_a_contradiction_that_blocks_non_contradiction() -> None:
    """Una ejecución duplicada se declara como contradicción: no puede haber evidencia limpia."""
    fills, settlements = _cycles(32)
    fills[0] = _Fill(
        fills[1].execution_id,  # misma clave que otra fila ⇒ duplicada
        fills[0].side,
        fills[0].price,
        fills[0].quantity,
        cycle_id=fills[0].cycle_id,
        created_at=fills[0].created_at,
    )
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert statuses["non_contradiction"] == "unmet"
    attribution = _criterion(dto, "execution_attribution")
    # La atribución mide COBERTURA; la contradicción la paga ``non_contradiction``.
    assert attribution["status"] == "met"
    assert attribution["measurement"] == "PARTIAL"
    assert any(c.startswith("duplicate_execution_id") for c in dto["contradictions"])
    assert dto["verdict"] == "NO_CONFIRMED"


def _criterion(dto: dict, criterion_id: str) -> dict:
    return next(item for item in dto["criteria"] if item["id"] == criterion_id)


def test_a_contradictory_closure_blocks_the_non_contradiction_criterion() -> None:
    """Un cierre que discrepa del material es una contradicción: no puede haber evidencia limpia."""
    fills, settlements = _cycles(32)
    settlements[0] = {**settlements[0], "pnl": "90"}  # FIFO mide 100, el cierre declara 90
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert statuses["closure_reconciliation"] == "unmet"
    assert statuses["non_contradiction"] == "unmet"
    assert any(c.startswith("settlement_pnl_mismatch") for c in dto["contradictions"])


def test_a_settlement_without_a_measured_pnl_degrades_closure() -> None:
    """Un PnL no medido NO se lee como cero: degrada cierre, resultados y no-contradicción."""
    fills, settlements = _cycles(32)
    settlements[0] = {**settlements[0], "pnl": None, "pnlMeasurement": "UNKNOWN"}
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert statuses["closure_reconciliation"] == "unmet"
    assert statuses["non_contradiction"] == "unmet"
    # El PnL no medido no cuenta como resultado medido: 31 < 32.
    assert statuses["durable_results"] == "unmet"
    assert any(c.startswith("settlement_pnl_unmeasured") for c in dto["contradictions"])


def test_a_settlement_without_a_declared_quantity_degrades_closure() -> None:
    """Una cantidad de cierre ausente NO se acepta: degrada cierre y no-contradicción."""
    fills, settlements = _cycles(32)
    settlements[0] = {**settlements[0], "closedQty": None}
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert statuses["closure_reconciliation"] == "unmet"
    assert statuses["non_contradiction"] == "unmet"
    assert any(c.startswith("settlement_quantity_unmeasured") for c in dto["contradictions"])


def test_duplicate_settlements_block_closure_and_non_contradiction() -> None:
    """Dos cierres para el mismo ciclo bloquean la conciliación limpia (duplicidad declarada)."""
    fills, settlements = _cycles(32)
    settlements.append(dict(settlements[0]))  # mismo ``cycleId`` duplicado
    dto = _build(fills, settlements)

    statuses = _statuses(dto)
    assert statuses["closure_reconciliation"] == "unmet"
    assert statuses["non_contradiction"] == "unmet"
    assert any(c.startswith("duplicate_settlement_cycle") for c in dto["contradictions"])


def test_unattributed_settlements_block_non_contradiction() -> None:
    """Un cierre excluido por no declarar cuenta se declara como contradicción."""
    fills, settlements = _cycles(32)
    dto = _build(fills, settlements, unattributed_settlements=1)

    assert _statuses(dto)["non_contradiction"] == "unmet"
    assert any(c.startswith("settlement_without_account") for c in dto["contradictions"])


def test_each_criterion_declares_its_durable_source() -> None:
    """Cada cifra puede rastrearse hasta su fuente: el criterio publica su origen durable."""
    fills, settlements = _cycles(32)
    dto = _build(fills, settlements)

    for criterion in dto["criteria"]:
        assert criterion["source"], criterion["id"]
    cell = next(item for item in dto["perVersion"] if item["strategyVersion"] == _VERSION)
    assert cell["closedOperations"] == 32
    assert cell["meetsMinimum"] is True
