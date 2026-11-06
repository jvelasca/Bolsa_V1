"""M8 — un turno OPERATIVO sin espejos durables se rechaza; no hay «modo estructural».

El fallo que se cierra: con stores opcionales el motor podía conducir la operativa real
con la parada dura, la posición, el compromiso de capital y el libro financiero viviendo
sólo en RAM, y el «modo estructural» marcaba fills como ``applied`` sin que nadie moviera
dinero. El runtime real declara ahora ``require_durable_stores=True``: si falta un espejo,
el turno no decide nada y lo declara. El camino hermético (tests/replay) conserva su
comportamiento byte a byte.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_api.background import auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import (
    DURABLE_STORES_MISSING,
    OPERATIVE_DURABLE_SEAMS,
    AutoSimulationWorker,
    TurnReport,
)
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

_ACCOUNT = "acc-m8"


def _worker(*, operative: bool) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=lambda: datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
        account_id=_ACCOUNT,
        require_durable_stores=operative,
    )


class _AutoStore:
    """``AutoEngineStore`` mínimo: el turno sólo lee y escribe un tick."""

    def __init__(self) -> None:
        self.ticks: list[Any] = []

    async def read(self, _engine_id: str) -> None:
        return None

    async def record_tick(self, tick: Any) -> None:
        self.ticks.append(tick)


async def _applier(_event: Any) -> bool:
    return True


def _all_seams() -> dict[str, Any]:
    return {
        "exec_store": InMemoryExecutionEventStore(),
        "auto_store": _AutoStore(),
        "finance_applier": _applier,
        "position_store": InMemorySimAutoPositionStore(),
        "reservation_store": InMemoryReservationStore(),
        "kill_switch_store": InMemoryKillSwitchStore(),
    }


@pytest.mark.asyncio
async def test_operative_turn_is_refused_when_durable_stores_are_missing() -> None:
    worker = _worker(operative=True)

    report = await worker.real_turn(
        exec_store=InMemoryExecutionEventStore(),
        auto_store=None,
        finance_applier=None,
        account_id=_ACCOUNT,
    )

    assert report.decided == 0 and report.orders == 0
    reason = (worker._last_gate_reason or ("",))[0]
    assert reason.startswith(f"{DURABLE_STORES_MISSING}:")
    assert "kill_switch_store" in reason
    assert "finance_applier" in reason


@pytest.mark.asyncio
async def test_operative_turn_proceeds_when_every_seam_is_present() -> None:
    worker = _worker(operative=True)
    worker._readopted = True  # el gate no llega a readoptar en este doble
    worker._v2_reservations_reconciled = True
    called: list[bool] = []

    async def fake_turn() -> TurnReport:
        called.append(True)
        return TurnReport(venue="paper")

    worker.auto_turn = fake_turn  # type: ignore[method-assign]

    await worker.real_turn(account_id=_ACCOUNT, **_all_seams())

    assert called == [True], "con todos los espejos el turno se conduce"
    assert not (worker._last_gate_reason or ("",))[0].startswith(DURABLE_STORES_MISSING)


def test_missing_seams_lists_exactly_the_absent_ones() -> None:
    worker = _worker(operative=True)

    assert worker._v2_missing_durable_seams() == OPERATIVE_DURABLE_SEAMS

    for name, value in _all_seams().items():
        setattr(worker, f"_{name}", value)

    assert worker._v2_missing_durable_seams() == ()


@pytest.mark.asyncio
async def test_operative_structural_settlement_is_a_declared_failure() -> None:
    """Sin ``finance_applier`` no se marca un fill como aplicado en modo operativo."""
    worker = _worker(operative=True)
    worker._exec_store = InMemoryExecutionEventStore()

    settlement = await worker._settle("buy", "AAA", __import__("decimal").Decimal("10"))

    assert settlement.failed is True
    assert settlement.applied == (), "confirmar el schedule no es haber movido dinero"
    assert worker.settlement_failures == 1


@pytest.mark.asyncio
async def test_hermetic_worker_keeps_the_structural_path() -> None:
    """Contraprueba: sin la exigencia (tests/replay) el modo estructural sigue vivo."""
    worker = _worker(operative=False)
    worker._exec_store = InMemoryExecutionEventStore()
    worker._price_script = lambda _symbol, _tick: 100.0

    settlement = await worker._settle("buy", "AAA", __import__("decimal").Decimal("10"))

    assert settlement.failed is False
    assert worker.settlement_failures == 0


def test_runtime_declares_the_requirement() -> None:
    """El runtime de producción no puede volver a componer un worker sin la exigencia."""
    import inspect

    source = inspect.getsource(worker_module.AutoSimRuntime.__init__)
    assert "require_durable_stores=True" in source
