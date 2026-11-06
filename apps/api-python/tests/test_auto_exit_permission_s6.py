"""S-6 — el worker AUTO consulta F5 antes de emitir una salida (y la declara).

Hallazgo de la auditoría 2026-10-26 (§5.8): ``check_exit_permission`` se invocaba en el
desk paper y en las pruebas, pero **no** en el worker AUTO, así que ``data_stale``/
``market_closed``/``portfolio_drift`` no tenían efecto **ni rastro** sobre una salida.

Contrato implementado (``bolsa_application.auto_exit_gate``): la salida consulta F5 sobre
el MISMO ``ExitPlan`` de la decisión; el veredicto **no** la bloquea (la salida protectora
reduce riesgo y el venue es el simulador paper), pero un ``DENY`` queda en el journal con
sus motivos y con la exención declarada. El caso que la auditoría pedía fijar es el del
objetivo (``TARGET_1``) con dato rancio: **se vende igual** y el journal lo dice.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_exit_gate import (
    AUTO_EXIT_EXEMPTION,
    AUTO_EXIT_PERMISSION_EVENT,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.reservation_store import InMemoryReservationStore

_SYMBOLS = ["AAA"]
_TEMPLATE = "moderate"
_START = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", raising=False)


def _buy_lot(lot: float = 250.0) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=lot)

    return _d


def _hold() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _edge_source(value: float = 0.9):
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _worker(**kwargs: object) -> AutoSimulationWorker:
    defaults: dict[str, object] = {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
        "exec_store": InMemoryExecutionEventStore(),
        "reservation_store": InMemoryReservationStore(),
        "exit_order_store": InMemoryExitOrderStore(),
    }
    defaults.update(kwargs)
    _start, clock = step_minute_clock(_START)
    return AutoSimulationWorker(clock=clock, **defaults)  # type: ignore[arg-type]


def _make_data_stale(worker: AutoSimulationWorker) -> None:
    """Fija ``market_data`` UNA hora por detrás del reloj (umbral: 300 s)."""
    worker._v2_data_timestamps = {"market_data": _START.timestamp() - 3600}


def _permission_payloads(worker: AutoSimulationWorker) -> list[dict[str, object]]:
    """Details de las filas ``exit_permission`` del journal (una por salida emitida)."""
    return [
        dict(entry.payload)
        for entry in worker._v2_journal
        if entry.payload is not None
        and entry.payload.get("reasonCodes") == [AUTO_EXIT_PERMISSION_EVENT]
    ]


# ── el caso que la auditoría pedía fijar: TARGET_1 con dato rancio ───────────────────


@pytest.mark.asyncio
async def test_target_exit_sells_under_stale_data_and_declares_the_f5_deny(
    v2_env: None,
) -> None:
    prices = {"v": 100.0}
    worker = _worker(price_script=lambda _s, _m: prices["v"])
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0, "la entrada se ejecuta"

    # Objetivo alcanzable de forma determinista: T1 justo por encima del mark actual.
    born = worker._v2_positions["AAA"]
    worker._v2_positions["AAA"] = replace(
        born, target1=101.0, target1_achieved_at=None, target2=None
    )
    _make_data_stale(worker)

    prices["v"] = 105.0
    worker._decider = _hold()
    report = await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) < 250, "el objetivo se ejecuta igual"
    assert report.exit_permission_denied >= 1, "el DENY de F5 se cuenta en el turno"

    payloads = _permission_payloads(worker)
    assert payloads, "la salida deja su consulta F5 en el journal"
    row = payloads[-1]
    permission = row["permission"]
    assert isinstance(permission, dict)
    assert permission["verdict"] == "DENY"
    assert permission["reasons"] == ["data_stale"], "el veto es por el DATO, no por otra cosa"
    assert row["protective"] is False, "TARGET_1 no es protectora"
    assert row["exemption"] == AUTO_EXIT_EXEMPTION, "la exención se declara, no se calla"
    assert row["blocksExit"] is False
    assert row["exitPlanId"], "el plan juzgado es el de la decisión"
    assert row["primaryReason"] == "TARGET_1"
    jit = row["jit"]
    assert isinstance(jit, dict)
    assert jit["dataStale"] is True
    assert jit["marketClosed"] is None, "lo que no se mide se declara «no medido»"


# ── control negativo: la consulta NO es una constante ────────────────────────────────


@pytest.mark.asyncio
async def test_protective_exit_is_allowed_and_declares_no_exemption(v2_env: None) -> None:
    prices = {"v": 100.0}
    worker = _worker(price_script=lambda _s, _m: prices["v"])
    worker._decider = _buy_lot()
    await worker.auto_turn()

    _make_data_stale(worker)
    prices["v"] = 90.0  # rompe el stop estructural: salida protectora
    worker._decider = _hold()
    report = await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0, "el stop cierra la posición"
    assert report.exit_permission_denied == 0, "F5 no niega una salida protectora"

    payloads = _permission_payloads(worker)
    assert payloads
    row = payloads[-1]
    permission = row["permission"]
    assert isinstance(permission, dict)
    assert permission["verdict"] == "ALLOW"
    assert row["protective"] is True
    assert row["exemption"] is None
    assert row["primaryReason"] == "STRUCTURAL_STOP"
