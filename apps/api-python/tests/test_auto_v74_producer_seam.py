"""V2.74 (AUTO-MATERIAL-2) — costura del PRODUCTOR PAPER y del gate de dos niveles.

Hermético (sin PostgreSQL): conduce el camino REAL del worker (``auto_turn`` →
``_v2_plan_tick`` / ``_v2_persist_tick_reservations`` / ``_v2_reserve_exit``) con stores
in-memory y comprueba que el pipeline AUTO 2.0 deja ESTRUCTURA —``cycle_id`` en los fills,
reservas de riesgo, intents de salida— que el gate declara ``PRODUCER_READY``. El mismo
material por el camino LEGACY (V2 OFF) no tiene estructura: no hay linaje ni reservas.

También fija el contrato del CLI: ``--level producer`` distingue "bien formado" de "suficiente
muestra".
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.account_drawdown import EquityMarkBook
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.paper_material_readiness import (
    BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES,
    MATERIAL_READINESS_METHOD,
    READINESS_PRODUCER_READY,
    PaperMaterialReadiness,
    build_paper_material_readiness,
)
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-v74"
_SYMBOL = "AAA"
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_material_readiness.py"


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _buy() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _hold() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _sell_when_held(worker: AutoSimulationWorker) -> Any:
    def _d(symbol: str) -> DecisionPackage:
        held = worker._open.get(symbol, Decimal("0"))
        if held > 0:
            return DecisionPackage(action="SELL", instrument_id=symbol, quantity=float(held))
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)

    return _d


def _trade_kwargs() -> dict[str, object]:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _edge(_ref: str, _account: str | None) -> float | None:
        return 0.9

    return {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": EdgeReportSource(reader=_edge),
    }


def _worker(
    *,
    account_id: str,
    contexts: InMemorySimFillFinanceContextStore,
    reservations: InMemoryReservationStore,
    positions: InMemorySimAutoPositionStore,
    exit_orders: InMemoryExitOrderStore,
    marks: EquityMarkBook,
    minute: int = 0,
) -> AutoSimulationWorker:
    _store, clock = step_minute_clock(datetime(2026, 9, 15, 9, minute, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        context_store=contexts,
        reservation_store=reservations,
        position_store=positions,
        exit_order_store=exit_orders,
        account_id=account_id,
        equity_marks=marks,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),  # type: ignore[arg-type]
    )


def _readiness_from_durable(
    contexts: InMemorySimFillFinanceContextStore,
    reservations: InMemoryReservationStore,
    exit_orders: InMemoryExitOrderStore,
    *,
    min_cycles: int = 32,
) -> PaperMaterialReadiness:
    fills = list(contexts._rows.values())
    reservation_rows = list(reservations._rows.values())
    exit_rows = list(exit_orders._rows.values())
    versions = sorted({str(f.strategy_version_id) for f in fills if f.strategy_version_id})
    return build_paper_material_readiness(
        account_id=_ACCOUNT,
        requested_versions=versions,
        fills=fills,
        reservations=reservation_rows,
        exit_orders=[{"cycle_id": order.cycle_id} for order in exit_rows],
        min_cycles_per_strategy=min_cycles,
    )


@pytest.mark.asyncio
async def test_v2_producer_leaves_structure_that_the_gate_declares_producer_ready(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2 ON: el fill hereda ``cycle_id``, la reserva es durable y la salida deja INTENT."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()
    exit_orders = InMemoryExitOrderStore()
    marks = EquityMarkBook()

    worker = _worker(
        account_id=_ACCOUNT,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        exit_orders=exit_orders,
        marks=marks,
    )
    worker._decider = _buy()
    await worker.auto_turn()
    assert worker._open.get(_SYMBOL, Decimal("0")) > 0, "AUTO 2.0 abre por el camino real"

    # El fill de ENTRADA libera la reserva, pero la FILA DURABLE conserva el riesgo
    # COMPROMETIDO (el denominador de R) aunque el libro vivo lo deje a 0. Es el arreglo de
    # V2.74: sin él, todo ciclo cerrado queda con `risk_amount = None` (R inmedible) justo
    # cuando ya tiene resultado.
    entry = next(
        row for row in reservations._rows.values() if row.side == "buy" and row.cycle_id
    )
    assert entry.is_released is True, "el fill de entrada libera la reserva"
    assert entry.reserved_risk is not None and entry.reserved_risk > 0, (
        "la reserva liberada CONSERVA el riesgo comprometido para el R del ciclo"
    )
    assert entry.entry is not None and entry.stop is not None, "geometría durable intacta"

    # DD 16 % ⇒ RISK_OFF ⇒ RISK_EXIT: cierra con el MISMO camino que un stop real.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "84000")
    worker._decider = _hold()
    await worker.auto_turn()
    assert worker._open.get(_SYMBOL, Decimal("0")) == 0, "la salida V2 cierra el ciclo"

    readiness = _readiness_from_durable(contexts, reservations, exit_orders)

    assert readiness.producer_ready is True
    assert readiness.verdict == READINESS_PRODUCER_READY, "estructura sí, muestra no"
    assert readiness.producer_blockers == ()
    assert readiness.facts["fillsWithCycle"] > 0, "el fill lleva cycle_id"
    assert readiness.facts["closedCycles"] >= 1, "el round-trip cierra"
    assert readiness.facts["measurableCycles"] >= 1, "hay denominador de R"
    assert readiness.facts["reservations"] > 0
    assert readiness.facts["reservationsLive"] == 0, "no queda compromiso vivo tras cerrar"
    assert readiness.lineage["cycle"]["exitOrdersWithCycle"] > 0
    assert BLOCKER_INSUFFICIENT_MEASURABLE_CYCLES in readiness.blockers


@pytest.mark.asyncio
async def test_legacy_path_leaves_no_structure_and_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2 OFF: el material legacy no tiene linaje ni reservas (el gate lo DECLARA)."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "0")
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()
    exit_orders = InMemoryExitOrderStore()
    marks = EquityMarkBook()

    worker = _worker(
        account_id=_ACCOUNT,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        exit_orders=exit_orders,
        marks=marks,
    )
    worker._decider = _sell_when_held(worker)
    await worker.auto_turn()  # abre por el camino legacy
    await worker.auto_turn()  # cierra con la venta del decider
    assert contexts._rows, "el camino legacy sí materializa fills"

    readiness = _readiness_from_durable(contexts, reservations, exit_orders)

    assert readiness.producer_ready is False
    assert readiness.facts["fillsWithCycle"] == 0
    assert readiness.facts["reservations"] == 0
    assert readiness.lineage["cycle"]["exitOrdersWithCycle"] == 0


@pytest.mark.asyncio
async def test_v2_producer_never_backfills_the_frozen_legacy_material(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El material legacy CONGELADO queda byte a byte igual: sin backfill de ``cycle_id``.

    El productor V2 solo ACUÑA material nuevo (append por ``execution_id``); jamás reescribe
    las filas históricas. La guarda siembra un fill legacy (``cycle_id=None``), corre el
    productor V2 sobre el mismo libro y comprueba que la fila histórica no se toca: ni se le
    infiere linaje ni se le cuelga una reserva.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_GOVERNOR", "1")
    contexts = InMemorySimFillFinanceContextStore()
    reservations = InMemoryReservationStore()
    positions = InMemorySimAutoPositionStore()
    exit_orders = InMemoryExitOrderStore()
    marks = EquityMarkBook()

    legacy = SimFillFinanceContext(
        execution_id="legacy-fill-0001",
        instrument_id="LEGACY",
        side="buy",
        quantity=Decimal("10"),
        price=Decimal("50"),
        account_id=_ACCOUNT,
        strategy_version_id="legacy-v1",
        cycle_id=None,
    )
    await contexts.save(legacy)

    worker = _worker(
        account_id=_ACCOUNT,
        contexts=contexts,
        reservations=reservations,
        positions=positions,
        exit_orders=exit_orders,
        marks=marks,
    )
    worker._decider = _buy()
    await worker.auto_turn()
    worker._decider = _hold()
    await worker.auto_turn()

    # La fila histórica sigue SIN ciclo y con sus campos intactos (no se backfillea).
    frozen = contexts._rows["legacy-fill-0001"]
    assert frozen.cycle_id is None, "el productor NO infiere cycle_id al material legacy"
    assert frozen.instrument_id == "LEGACY"
    assert frozen.strategy_version_id == "legacy-v1"
    # Ninguna reserva se cuelga del material histórico.
    assert all(row.cycle_id != "legacy-fill-0001" for row in reservations._rows.values())
    # Y el material NUEVO del productor sí nace con linaje.
    new_fills = [
        row for row in contexts._rows.values() if row.execution_id != "legacy-fill-0001"
    ]
    assert new_fills and all(row.cycle_id for row in new_fills)


# ── Contrato del CLI: nivel producer vs evidence ────────────────────────────────────


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("v74_paper_material_readiness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _producer_ready() -> PaperMaterialReadiness:
    from bolsa_analytics.cognitive.portfolio_reservation import (
        RESERVATION_OPEN,
        SIDE_BUY,
        PortfolioReservation,
    )
    from bolsa_application.sim_durable_store import SimFillFinanceContext

    fills = [
        SimFillFinanceContext(
            execution_id=f"cyc-{side}",
            instrument_id="AAA",
            side=side,
            quantity=Decimal("10"),
            price=Decimal("100"),
            account_id=_ACCOUNT,
            strategy_version_id="orb-a",
            cycle_id="cyc-1",
        )
        for side in ("buy", "sell")
    ]
    reservations = [
        PortfolioReservation(
            reservation_id="RES-cyc-1",
            account_id=_ACCOUNT,
            instrument_id="AAA",
            side=SIDE_BUY,
            quantity=10.0,
            entry=100.0,
            stop=95.0,
            reserved_cash=1000.0,
            reserved_risk=250.0,
            status=RESERVATION_OPEN,
            created_at="2026-09-26T08:00:00+00:00",
            remaining_qty=10.0,
            cycle_id="cyc-1",
        )
    ]
    return build_paper_material_readiness(
        account_id=_ACCOUNT,
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        exit_orders=[{"cycle_id": "cyc-1"}],
        min_cycles_per_strategy=32,
    )


def _patch_read(monkeypatch: pytest.MonkeyPatch, module: Any, readiness: PaperMaterialReadiness) -> None:
    async def _read(account_id: str, versions: list[str], *, limit: int, min_cycles: int) -> Any:
        return readiness

    monkeypatch.setattr(module, "_read", _read)


def test_producer_level_is_reached_without_the_evidence_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_cli()
    _patch_read(monkeypatch, module, _producer_ready())

    assert module.main(
        ["--account-id", _ACCOUNT, "--strategy-version", "orb-a", "--level", "producer"]
    ) == 0
    # El mismo material NO alcanza el nivel por defecto (evidence): falta muestra.
    assert module.main(["--account-id", _ACCOUNT, "--strategy-version", "orb-a"]) == 2


def test_the_json_payload_carries_the_two_levels_and_the_seal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    module = _load_cli()
    _patch_read(monkeypatch, module, _producer_ready())

    code = module.main(
        [
            "--account-id",
            _ACCOUNT,
            "--strategy-version",
            "orb-a",
            "--level",
            "producer",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == MATERIAL_READINESS_METHOD
    assert payload["verdict"] == READINESS_PRODUCER_READY
    assert payload["producerReady"] is True
    assert payload["evidenceReady"] is False
