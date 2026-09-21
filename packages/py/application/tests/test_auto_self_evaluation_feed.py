"""AUTO-7 — tests del alimentador read-only del informe de autoevaluación.

Se prueba lo que el adaptador NO puede permitirse: contar como cerrado un ciclo que sigue
abierto, inventar PnL sin contrapartida, repartir entre dos estrategias un ciclo que declara
dos versiones, o rellenar con ceros los huecos (R, MAE/MFE, slippage, embudo) que los
productores actuales no aportan.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_CYCLE_WITHOUT_IDENTITY,
    SELF_EVAL_UNVERSIONED_CYCLE,
    evaluate_auto_self_evaluation,
)
from bolsa_application.auto_self_evaluation_feed import (
    build_auto_self_evaluation,
    cycles_from_fills,
    make_auto_self_evaluation_provider,
)
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    version: str = "orb-1",
    cycle_id: str | None = None,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        strategy_version_id=version,
        cycle_id=cycle_id,
    )


# ── Reconstrucción del ciclo ────────────────────────────────────────────────────────


def test_a_closed_cycle_is_reconstructed_from_its_two_fills() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert cycles == (
        {"cycleId": "cyc-1", "strategyVersion": "orb-1", "pnl": Decimal("50")},
    )


def test_an_open_cycle_is_not_counted_as_a_result() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "4", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )

    assert cycles == (), "una posición abierta todavía no tiene resultado que medir"


def test_a_sell_without_counterpart_does_not_fabricate_pnl() -> None:
    cycles = cycles_from_fills(
        [_fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1")]
    )

    assert cycles == (), "sin compra que casar no hay PnL (no se fabrica un corto)"


def test_partial_exits_of_a_closed_cycle_realize_fifo_once() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "4", "105", execution_id="e2", cycle_id="cyc-1"),
            _fill("sell", "6", "110", execution_id="e3", cycle_id="cyc-1"),
        ]
    )

    assert len(cycles) == 1
    assert cycles[0]["pnl"] == Decimal("80"), "4×5 + 6×10, una sola vez"


def test_legacy_fills_without_cycle_id_yield_one_anonymous_cycle_per_match() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1"),
            _fill("buy", "10", "102", execution_id="e2"),
            _fill("sell", "10", "105", execution_id="e3"),
            _fill("sell", "10", "110", execution_id="e4"),
        ]
    )

    assert [cycle["pnl"] for cycle in cycles] == [Decimal("50"), Decimal("80")]
    assert all("cycleId" not in cycle for cycle in cycles), "sin identidad: se declara"


def test_a_cycle_declaring_two_strategies_is_not_split_between_them() -> None:
    cycles = cycles_from_fills(
        [
            _fill("buy", "10", "100", execution_id="e1", version="orb-1", cycle_id="cyc-1"),
            _fill(
                "sell", "10", "105", execution_id="e2", version="meanrev-2", cycle_id="cyc-1"
            ),
        ]
    )

    assert cycles == ({"cycleId": "cyc-1", "strategyVersion": "", "pnl": Decimal("50")},)

    report = build_auto_self_evaluation(fills=[
        _fill("buy", "10", "100", execution_id="e1", version="orb-1", cycle_id="cyc-1"),
        _fill("sell", "10", "105", execution_id="e2", version="meanrev-2", cycle_id="cyc-1"),
    ])
    assert report.by_strategy == ()
    assert report.unattributed_cycles == 1
    assert SELF_EVAL_UNVERSIONED_CYCLE in report.notes


def test_anonymous_legacy_cycles_are_declared_by_the_report() -> None:
    report = build_auto_self_evaluation(
        fills=[
            _fill("buy", "10", "100", execution_id="e1"),
            _fill("sell", "10", "105", execution_id="e2"),
        ]
    )

    assert report.cycles == 1
    assert report.cycles_without_identity == 1
    assert SELF_EVAL_CYCLE_WITHOUT_IDENTITY in report.notes
    assert report.by_strategy[0].realized_pnl == 50


# ── Huecos declarados, nunca rellenados ─────────────────────────────────────────────


def test_the_report_declares_what_fills_alone_cannot_measure() -> None:
    report = build_auto_self_evaluation(
        fills=[
            _fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"),
            _fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"),
        ]
    )
    row = report.by_strategy[0]

    assert row.expectancy_currency == 50
    assert row.win_rate == 1.0
    assert row.profit_factor is None, "sin perdedoras el ratio es indefinido"
    assert row.expectancy_r is None and row.risk_measurement == "UNKNOWN"
    assert row.mfe_r is None and row.excursions_measurement == "UNKNOWN"
    assert row.slippage_currency is None
    assert report.funnel_closed is False and report.seen is None
    assert report.read_only is True
    assert report.decisive is False, "una sola operación no autoriza a concluir"


def test_no_fills_is_an_unknown_report_not_a_report_of_zeros() -> None:
    report = build_auto_self_evaluation(fills=[])

    assert report.cycles == 0
    assert report.realized_pnl == 0
    assert report.expectancy_currency is None
    assert report.measurement == "UNKNOWN"
    assert report.by_strategy == ()


# ── Provider (composición) ─────────────────────────────────────────────────────────


class _Session:
    """Sesión mínima: el provider la abre y la cierra, nada más."""

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_returns_the_report_of_the_version() -> None:
    store = InMemorySimFillFinanceContextStore()
    await store.save(_fill("buy", "10", "100", execution_id="e1", cycle_id="cyc-1"))
    await store.save(_fill("sell", "10", "105", execution_id="e2", cycle_id="cyc-1"))
    provider = make_auto_self_evaluation_provider(
        lambda: _Session(), store_factory=lambda _session: store
    )

    payload = await provider("orb-1")

    assert payload["readOnly"] is True
    assert payload["byStrategy"][0]["strategyVersion"] == "orb-1"
    assert payload["byStrategy"][0]["realizedPnl"] == "50.000000"


@pytest.mark.asyncio
async def test_provider_without_version_declares_the_reason() -> None:
    provider = make_auto_self_evaluation_provider(lambda: _Session())

    payload = await provider("   ")

    assert payload["errors"] == ["strategy_version_required"]
    assert payload["decisive"] is False


@pytest.mark.asyncio
async def test_provider_read_failure_is_declared_and_never_fabricates_metrics() -> None:
    class _Broken:
        async def list_for_strategy_version(self, *_a: object, **_k: object) -> None:
            raise RuntimeError("db down")

    provider = make_auto_self_evaluation_provider(
        lambda: _Session(), store_factory=lambda _session: _Broken()
    )

    payload = await provider("orb-1")

    assert payload["errors"] == ["read_failed"]
    assert payload["byStrategy"] == []
    assert payload["decisive"] is False


def test_the_pure_feeds_module_does_not_touch_the_analytics_input_contract() -> None:
    """El informe de los fills y el informe puro comparten contrato (mismo ``as_dict``)."""
    report = build_auto_self_evaluation()
    assert report.as_dict() == evaluate_auto_self_evaluation().as_dict()
