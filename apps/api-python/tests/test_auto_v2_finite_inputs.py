"""P9 (auditoría .183) — ningún ``NaN``/``inf`` entra al camino de dinero ni al arranque.

Dos mitades, las dos de producción:

1. **Precios.** Una fuente de precio que devuelve ``NaN``/``inf`` (división por cero, overflow,
   parser roto) no puede abrir posición ni producir una equity no finita: el símbolo se trata
   como precio AUSENTE, se declara y se cuenta.
2. **Configuración.** Un ``LOT_QTY``/``INTERVAL`` no numérico o no finito cae a su default con
   warning en vez de reventar el arranque (``int('inf')`` lanzaba ``OverflowError``) o suspender
   el loop para siempre (``Infinity``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    _default_spine_decider,
    _protection_config_from_env,
    _sim_interval_seconds,
    step_minute_clock,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV, EdgeReportSource
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.reservation_store import InMemoryReservationStore

_SYMBOLS = ("AAA",)


def _buy_lot(lot: float = 250.0) -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=lot)

    return _d


def _edge_source(value: float = 0.9) -> EdgeReportSource:
    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


class _PoisonSource:
    """``PriceSource`` estructural cuyas dos fronteras devuelven un valor ENVENENADO."""

    def __init__(self, *, mid: float, exec_: float, low: float, high: float) -> None:
        self._mid = mid
        self._exec = exec_
        self._low = low
        self._high = high

    async def refresh(self) -> None:
        return None

    def mid(self, symbol: str) -> float | None:
        return self._mid

    def execution(self, symbol: str) -> float | None:
        return self._exec

    def low(self, symbol: str) -> float | None:
        return self._low

    def high(self, symbol: str) -> float | None:
        return self._high

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return ()


def _worker(price_source: Any) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))[1],
        exec_store=InMemoryExecutionEventStore(),
        reservation_store=InMemoryReservationStore(),
        exit_order_store=InMemoryExitOrderStore(),
        sector_source=lambda _symbol: "tech",
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=_edge_source(),
        price_source=price_source,
        engine_id="p9-finite",
    )


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


# ── 1. Precios no finitos ⇒ precio AUSENTE, declarado ───────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("poison", [float("nan"), float("inf"), float("-inf")])
async def test_a_non_finite_execution_price_does_not_open(
    v2_env: None, poison: float
) -> None:
    """``execution = inf`` NO puede abrir: antes pasaba el ``> 0`` y llegaba al libro."""
    worker = _worker(_PoisonSource(mid=50.0, exec_=poison, low=48.0, high=52.0))
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0
    assert worker.price_missing_counts.get("AAA", 0) >= 1, "la ausencia se DECLARA"


@pytest.mark.asyncio
@pytest.mark.parametrize("poison", [float("nan"), float("inf")])
async def test_a_non_finite_decision_price_does_not_open(v2_env: None, poison: float) -> None:
    """``mid = inf`` tampoco: la geometría (stop/T1) no puede construirse con ``inf``."""
    worker = _worker(_PoisonSource(mid=poison, exec_=55.0, low=48.0, high=52.0))
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0
    assert worker.price_missing_counts.get("AAA", 0) >= 1


def test_a_corrupt_bar_range_is_declared_absent(v2_env: None) -> None:
    """Un rango invertido o no finito es dato corrupto: ``(None, None)``, no una señal."""
    worker = _worker(_PoisonSource(mid=50.0, exec_=55.0, low=float("inf"), high=52.0))
    assert worker._v2_bar_extremes("AAA") == (None, None)

    worker = _worker(_PoisonSource(mid=50.0, exec_=55.0, low=60.0, high=52.0))
    assert worker._v2_bar_extremes("AAA") == (None, None)


def test_a_finite_bar_range_survives(v2_env: None) -> None:
    worker = _worker(_PoisonSource(mid=50.0, exec_=55.0, low=48.0, high=52.0))
    assert worker._v2_bar_extremes("AAA") == (48.0, 52.0)


@pytest.mark.asyncio
async def test_the_equity_stays_finite_when_a_mark_cannot_be_read(v2_env: None) -> None:
    """Con una marca imposible la curva de equity no se contamina: el símbolo se omite."""
    worker = _worker(_PoisonSource(mid=float("inf"), exec_=float("inf"), low=0.0, high=0.0))
    worker._decider = _buy_lot()
    await worker.auto_turn()

    # La comprobación que importa: nada de ``inf``/``NaN`` en las colecciones del libro.
    assert all(
        value == value and abs(value) != float("inf") for value in worker._entry_price.values()
    )
    assert all(qty == qty for qty in worker._open.values())
    assert worker._open.get("AAA", Decimal("0")) == 0


# ── 2. Configuración no finita ⇒ default seguro, nunca excepción ────────────────


@pytest.mark.parametrize("raw", ["abc", "NaN", "Infinity", "-inf", "", "0", "-5"])
def test_an_interval_that_cannot_be_used_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS", raw)
    assert _sim_interval_seconds(60.0) == 60.0


def test_a_finite_interval_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_INTERVAL_SECONDS", "2.5")
    assert _sim_interval_seconds(60.0) == 2.5


@pytest.mark.parametrize("raw", ["abc", "NaN", "Infinity"])
def test_a_broken_lot_quantity_does_not_break_the_startup(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """``AUTO_ENGINE_SIM_LOT_QTY=abc|NaN`` arranca con el lote por defecto."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_LOT_QTY", raw)
    decider = _default_spine_decider()  # antes: ``float('abc')`` rompía el arranque
    assert decider is not None


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-inf", "abc"])
def test_a_non_finite_protection_threshold_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Los umbrales de protección no pueden ser ``inf``: se usa el default declarado."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", raw)
    monkeypatch.setenv("AUTO_ENGINE_SIM_T1_PCT", raw)
    monkeypatch.setenv("AUTO_ENGINE_SIM_TRAILING_PCT", raw)
    monkeypatch.setenv("AUTO_ENGINE_SIM_SESSION_END_MINUTE", raw)
    policy = _protection_config_from_env()

    assert policy.stop_pct == pytest.approx(0.02)
    assert policy.t1_pct == pytest.approx(0.02)
    assert policy.trailing_pct == pytest.approx(0.015)
    assert policy.session_end_minute == 0


def test_a_finite_protection_threshold_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_STOP_PCT", "0.05")
    monkeypatch.setenv("AUTO_ENGINE_SIM_SESSION_END_MINUTE", "390")
    policy = _protection_config_from_env()

    assert policy.stop_pct == pytest.approx(0.05)
    assert policy.session_end_minute == 390
