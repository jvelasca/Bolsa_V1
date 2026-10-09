"""PAPER-2 — conciliación de la evidencia durable PAPER (cruces falsables).

Test hermético del módulo puro ``paper_evidence_reconciliation``: no toca base de datos. Fija
las reglas que impiden que un agregado optimista se lea como evidencia completa:

1. Una ejecución duplicada o un fill huérfano se DECLARAN, no se cuentan dos veces ni se
   descartan.
2. Un cierre durable que no cuadra con el round-trip (cantidad o PnL) es una CONTRADICCIÓN.
3. Una fuente no leída deja sus cruces **sin dato**, no limpios (``UNKNOWN ≠ 0``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
from bolsa_application.paper_evidence_reconciliation import (
    RECON_DUPLICATE_EXECUTION,
    RECON_DUPLICATE_SETTLEMENT,
    RECON_ORPHAN_FILL,
    RECON_PNL_MISMATCH,
    RECON_PNL_UNMEASURED,
    RECON_QTY_MISMATCH,
    RECON_QTY_UNMEASURED,
    RECON_SETTLEMENT_WITHOUT_ACCOUNT,
    RECON_SETTLEMENT_WITHOUT_CLOSURE,
    reconcile_paper_evidence,
)

_CYCLE = "cyc-abc"


@dataclass(frozen=True, slots=True)
class _Fill:
    execution_id: str
    side: str
    price: Decimal
    quantity: Decimal
    reference_mid: Decimal | None = Decimal("100")
    cycle_id: str | None = _CYCLE
    strategy_version_id: str | None = "orb-trend"
    created_at: datetime | None = None


def _fill(
    side: str,
    *,
    price: str = "100",
    qty: str = "10",
    cycle: str | None = _CYCLE,
    execution: str | None = None,
    version: str | None = "orb-trend",
    created_at: datetime | None = None,
) -> _Fill:
    return _Fill(
        execution_id=execution or f"venue#{side}",
        side=side,
        price=Decimal(price),
        quantity=Decimal(qty),
        cycle_id=cycle,
        strategy_version_id=version,
        created_at=created_at,
    )


def _settlement(
    cycle: str = _CYCLE,
    *,
    pnl: str | None = "100",
    closed_qty: str | None = "10",
    measurement: str = MEASUREMENT_COMPLETE,
) -> dict[str, object]:
    return {
        "event": "auto_cycle_settlement",
        "cycleId": cycle,
        "pnl": pnl,
        "pnlMeasurement": measurement,
        "closedQty": closed_qty,
    }


def _round_trip(cycle: str = _CYCLE) -> list[_Fill]:
    """Ida y vuelta balanceada con PnL medible: ``(110 − 100) × 10 = 100``."""
    return [
        _fill("buy", price="100", cycle=cycle, execution=f"{cycle}#buy"),
        _fill("sell", price="110", cycle=cycle, execution=f"{cycle}#sell"),
    ]


def test_a_clean_round_trip_reconciles_without_contradictions() -> None:
    """Un cierre durable que cuadra con el material no declara ninguna contradicción."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl="100", closed_qty="10")],
    )

    assert result.closed_cycles == 1
    assert result.settlements_total == 1
    assert result.settlements_reconciled == 1
    assert result.contradictions == ()
    cycle = result.cycles[0]
    assert cycle.closed is True
    assert cycle.balanced is True
    assert cycle.reconciled is True
    assert cycle.cost_complete is True


def test_a_duplicate_execution_is_declared_not_counted_twice() -> None:
    """El MISMO ``execution_id`` repetido es una ejecución duplicada, no dos operaciones."""
    fills = [
        _fill("buy", price="100", execution="dup#1"),
        _fill("sell", price="110", execution="dup#1"),
    ]
    result = reconcile_paper_evidence(fills=fills, settlements=[])

    assert result.duplicate_executions == 1
    assert any(c.startswith(RECON_DUPLICATE_EXECUTION) for c in result.contradictions)


def test_a_fill_without_a_cycle_is_an_orphan_declared() -> None:
    """Un fill sin ``cycle_id`` no se puede atribuir: se declara huérfano."""
    fills = [_fill("buy", cycle=None, execution="legacy#1")]
    result = reconcile_paper_evidence(fills=fills, settlements=[])

    assert result.orphan_executions == 1
    assert result.fills_with_cycle == 0
    assert any(c.startswith(RECON_ORPHAN_FILL) for c in result.contradictions)


def test_an_unbalanced_round_trip_is_not_a_closed_operation() -> None:
    """``BUY 100 / SELL 10`` tiene los dos lados y aun así deja 90 unidades abiertas."""
    fills = [
        _fill("buy", price="100", qty="100", execution="c#buy"),
        _fill("sell", price="110", qty="10", execution="c#sell"),
    ]
    result = reconcile_paper_evidence(fills=fills, settlements=[])

    cycle = result.cycles[0]
    assert cycle.both_sides is True
    assert cycle.balanced is False
    assert cycle.closed is False
    assert result.closed_cycles == 0


def test_a_settlement_without_a_closed_cycle_is_unmatched() -> None:
    """Un cierre durable de un ciclo que el material no declaró cerrado es una contradicción."""
    fills = [
        _fill("buy", price="100", qty="100", execution="c#buy"),
        _fill("sell", price="110", qty="10", execution="c#sell"),
    ]
    result = reconcile_paper_evidence(
        fills=fills,
        settlements=[_settlement(pnl="100", closed_qty="100")],
    )

    assert result.settlements_unmatched == 1
    assert any(c.startswith(RECON_SETTLEMENT_WITHOUT_CLOSURE) for c in result.contradictions)


def test_a_pnl_mismatch_is_declared_as_divergent() -> None:
    """El PnL del cierre que discrepa del FIFO más allá de la tolerancia no se da por bueno."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl="90", closed_qty="10")],
    )

    assert result.settlements_divergent == 1
    assert result.settlements_reconciled == 0
    assert any(c.startswith(RECON_PNL_MISMATCH) for c in result.contradictions)
    assert RECON_PNL_MISMATCH in result.cycles[0].notes


def test_a_quantity_mismatch_is_declared() -> None:
    """La cantidad cerrada debe cuadrar con el round-trip balanceado, no solo con el recuento."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl="100", closed_qty="5")],
    )

    assert result.settlements_divergent == 1
    assert any(c.startswith(RECON_QTY_MISMATCH) for c in result.contradictions)


def test_an_unloaded_source_leaves_cross_checks_without_data() -> None:
    """Una fuente no leída no puede producir contradicciones ni contadores inventados."""
    result = reconcile_paper_evidence(
        fills=[],
        settlements=[],
        fills_loaded=False,
        settlements_loaded=False,
    )

    assert result.fills_loaded is False
    assert result.settlements_loaded is False
    assert result.contradictions == ()
    assert "fills_not_loaded" in result.notes
    assert "settlements_not_loaded" in result.notes


def test_anonymous_legacy_cycles_are_counted_without_lineage() -> None:
    """Un round-trip FIFO sin ``cycle_id`` es una operación que NO declara linaje: se cuenta."""
    fills = [
        _fill("buy", cycle=None, execution="legacy#buy"),
        _fill("sell", price="110", cycle=None, execution="legacy#sell"),
    ]
    result = reconcile_paper_evidence(fills=fills, settlements=[])

    assert result.anonymous_closed_cycles == 1
    assert result.closed_cycles == 0
    assert result.orphan_executions == 2


def test_window_days_and_episodes_come_from_the_durable_fills() -> None:
    """La ventana durable son los días con fill y los ciclos observados, no una cifra supuesta."""
    day1 = datetime(2026, 10, 1, 10, tzinfo=UTC)
    day2 = datetime(2026, 10, 2, 10, tzinfo=UTC)
    fills = [
        _fill("buy", cycle="cyc-a", execution="a#buy", created_at=day1),
        _fill("sell", price="110", cycle="cyc-a", execution="a#sell", created_at=day1),
        _fill("buy", cycle="cyc-b", execution="b#buy", created_at=day2),
        _fill("sell", price="110", cycle="cyc-b", execution="b#sell", created_at=day2),
    ]
    result = reconcile_paper_evidence(fills=fills, settlements=[])

    assert result.window_days == 2
    assert result.window_episodes == 2


def test_an_unmeasured_fifo_pnl_does_not_reconcile_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un PnL FIFO ilegible NO se colapsa a ``0``: el ciclo queda sin reconciliar.

    ``cycles_from_fills`` siempre emite hoy un ``Decimal`` finito; el test INYECTA un ciclo
    cerrado sin PnL para fijar la regla: la ausencia de medición no puede compararse como cero.
    """

    def _closed_without_pnl(_fills: object) -> tuple[dict[str, object], ...]:
        return ({"cycleId": _CYCLE, "strategyVersion": "orb-trend", "pnl": None},)

    monkeypatch.setattr(
        "bolsa_application.paper_evidence_reconciliation.cycles_from_fills",
        _closed_without_pnl,
    )
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl="100", closed_qty="10")],
    )

    assert result.settlements_reconciled == 0
    assert result.settlements_divergent == 1
    assert RECON_PNL_UNMEASURED in result.cycles[0].notes
    assert any(c.startswith(RECON_PNL_UNMEASURED) for c in result.contradictions)


def test_a_settlement_without_a_measured_pnl_does_not_reconcile() -> None:
    """Un cierre con PnL no medido tampoco reconcilia (el hueco simétrico del FIFO)."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl=None, closed_qty="10", measurement="UNKNOWN")],
    )

    assert result.settlements_reconciled == 0
    assert result.settlements_divergent == 1
    assert RECON_PNL_UNMEASURED in result.cycles[0].notes
    assert any(c.startswith(RECON_PNL_UNMEASURED) for c in result.contradictions)


def test_a_settlement_without_a_declared_quantity_does_not_reconcile() -> None:
    """Una cantidad de cierre ausente NO se acepta como válida: la conciliación queda incompleta."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[_settlement(pnl="100", closed_qty=None)],
    )

    assert result.settlements_reconciled == 0
    assert result.settlements_divergent == 1
    assert RECON_QTY_UNMEASURED in result.cycles[0].notes
    assert any(c.startswith(RECON_QTY_UNMEASURED) for c in result.contradictions)


def test_duplicate_settlements_for_a_cycle_are_declared_not_overwritten() -> None:
    """Dos cierres para el mismo ciclo son una duplicidad DECLARADA, no una sobreescritura."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[
            _settlement(pnl="100", closed_qty="10"),
            _settlement(pnl="100", closed_qty="10"),
        ],
    )

    assert result.settlements_total == 2
    assert result.settlements_reconciled == 0
    assert result.settlements_divergent == 1
    assert RECON_DUPLICATE_SETTLEMENT in result.cycles[0].notes
    assert any(c.startswith(RECON_DUPLICATE_SETTLEMENT) for c in result.contradictions)


def test_duplicate_settlements_on_a_not_closed_cycle_are_still_declared() -> None:
    """La duplicidad se declara también cuando el material NO probó el cierre del ciclo."""
    result = reconcile_paper_evidence(
        fills=[
            _fill("buy", price="100", qty="100", execution="d#buy"),
            _fill("sell", price="110", qty="10", execution="d#sell"),
        ],
        settlements=[
            _settlement(pnl="100", closed_qty="100"),
            _settlement(pnl="100", closed_qty="100"),
        ],
    )

    assert result.settlements_reconciled == 0
    assert RECON_DUPLICATE_SETTLEMENT in result.cycles[0].notes
    assert any(c.startswith(RECON_DUPLICATE_SETTLEMENT) for c in result.contradictions)
    assert RECON_SETTLEMENT_WITHOUT_CLOSURE in result.cycles[0].notes


def test_unattributed_settlements_are_declared_as_contradiction() -> None:
    """Un cierre excluido por no declarar cuenta se declara: no puede leerse como material limpio."""
    result = reconcile_paper_evidence(
        fills=_round_trip(),
        settlements=[],
        unattributed_settlements=1,
    )

    assert any(c.startswith(RECON_SETTLEMENT_WITHOUT_ACCOUNT) for c in result.contradictions)
