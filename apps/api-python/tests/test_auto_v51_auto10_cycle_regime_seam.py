"""AUTO-10 — la costura del LECTOR de régimen por ciclo dentro del worker (paso 3).

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/application/tests/test_auto_cycle_regime_reader.py`` y ``test_cycle_risk.py``):
que con lector inyectado el denominador de R siga siendo el mismo pero el ciclo gane su
RÉGIMEN medido; que el ``CycleRisk`` pase a declarar ``regime_not_found`` (la fuente se leyó)
y no ``regime_not_durable``; que el régimen llegue al cruce ``strategy × regime`` y lo nombre
cuando la celda es DECISIVA (una celda no decisiva sigue declarando ``UNKNOWN``: la regla de
``AUTO-9`` no se toca); que sin lector el comportamiento anterior quede intacto; que un
lector que revienta degrade **declarando** —el R no se pierde por una traza—; y que el reintento
del tick (traza repetida) se declare como nota sin elevarse a hueco (paso 4).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import ADAPTIVE_REGIME_UNKNOWN
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_cycle_regime_reader import (
    REGIME_READ_ABSENT,
    CycleRegimeReading,
)
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-1"
_CYCLE = "cyc-aaa"
_REGIME = "TREND_UP"
#: Ciclos necesarios para que una celda `strategy × regime` sea DECISIVA (``min_trades`` = 10).
_DECISIVE_CYCLES = 10


def _fill(
    side: str, qty: str, price: str, *, execution_id: str, cycle_id: str
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        account_id=_ACCOUNT,
        strategy_version_id="orb-1",
        cycle_id=cycle_id,
    )


def _reservation(cycle_id: str) -> Any:
    from bolsa_analytics.cognitive.portfolio_reservation import PortfolioReservation

    return PortfolioReservation(
        reservation_id=f"res-{cycle_id}",
        account_id=_ACCOUNT,
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=250.0,
        strategy_version_id="orb-1",
        created_at="2026-09-22T08:00:00+00:00",
        cycle_id=cycle_id,
    )


def _closed_cycle(cycle_id: str) -> list[SimFillFinanceContext]:
    """Un ciclo cerrado con +250 de PnL (10 × (125 − 100)) sobre 250 de riesgo ⇒ R = 1."""
    return [
        _fill("buy", "10", "100", execution_id=f"e1-{cycle_id}", cycle_id=cycle_id),
        _fill("sell", "10", "125", execution_id=f"e2-{cycle_id}", cycle_id=cycle_id),
    ]


class _Reader:
    """Lector de mentira: devuelve la lectura fijada y registra los ciclos que se le piden."""

    def __init__(self, reading: CycleRegimeReading) -> None:
        self._reading = reading
        self.asked: list[list[str]] = []

    async def __call__(self, cycle_ids: Sequence[str]) -> CycleRegimeReading:
        self.asked.append(list(cycle_ids))
        return self._reading


class _BrokenReader:
    """Lector que revienta: el R medido NO puede perderse por una traza ilegible."""

    async def __call__(self, _cycle_ids: Sequence[str]) -> CycleRegimeReading:
        raise RuntimeError("journal ilegible")


def _worker(
    *, reader: Any | None = None, cycles: tuple[str, ...] = (_CYCLE,)
) -> AutoSimulationWorker:
    """Worker mínimo con lo que el camino Adaptive toca: fills durables + reservas + lector."""
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    context = InMemorySimFillFinanceContextStore()
    for cycle_id in cycles:
        for fill in _closed_cycle(cycle_id):
            context._rows[fill.execution_id] = fill
    worker._context_store = context
    worker._reservation_store = InMemoryReservationStore(
        seed=tuple(_reservation(cycle_id) for cycle_id in cycles)
    )
    worker._cycle_regime_reader = reader
    worker._v2_tunables = SimpleNamespace(adaptive_win_rate_floor=0.35)
    worker._v2_adaptive_paused_cycles = {}
    return worker


def _all_fills(cycles: tuple[str, ...] = (_CYCLE,)) -> list[SimFillFinanceContext]:
    return [fill for cycle_id in cycles for fill in _closed_cycle(cycle_id)]


async def _plan(worker: AutoSimulationWorker) -> Any:
    return await worker._v2_build_adaptive_plan({"orb-1"}, _REGIME)


def _reading_for(*cycles: str) -> CycleRegimeReading:
    return CycleRegimeReading(
        regime_by_cycle={cycle_id: _REGIME for cycle_id in cycles}, requested=len(cycles)
    )


# ── Con lector: el ciclo gana su régimen medido ─────────────────────────────────────


@pytest.mark.asyncio
async def test_the_worker_measures_the_regime_of_the_cycle_from_the_journal() -> None:
    reader = _Reader(_reading_for(_CYCLE))
    worker = _worker(reader=reader)

    evidence = await worker._v2_cycle_risk(_all_fills())

    assert evidence is not None
    row = evidence[_CYCLE]
    assert row.regime == _REGIME
    assert row.risk_amount == Decimal("250.0"), "el denominador no cambia por saber el régimen"
    assert row.regime_measurement == "COMPLETE"
    assert reader.asked == [[_CYCLE]], "se le pide el régimen de los ciclos del tick"


@pytest.mark.asyncio
async def test_a_non_decisive_cell_measures_the_regime_without_naming_it() -> None:
    """Regla de ``AUTO-9`` intacta: una celda no decisiva no asciende a régimen nombrado."""
    plan = await _plan(_worker(reader=_Reader(_reading_for(_CYCLE))))

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.regime == ADAPTIVE_REGIME_UNKNOWN
    assert health.expectancy_r == pytest.approx(1.0), "el R sí se mide: 250 / 250"


@pytest.mark.asyncio
async def test_a_decisive_cell_names_the_regime_end_to_end() -> None:
    """El premio del paso 3: con evidencia decisiva, el régimen del journal se NOMBRA."""
    cycles = tuple(f"cyc-{index:012x}" for index in range(_DECISIVE_CYCLES))
    reader = _Reader(_reading_for(*cycles))
    worker = _worker(reader=reader, cycles=cycles)

    plan = await _plan(worker)

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.decisive is True
    assert health.regime == _REGIME, "el régimen medido por ciclo llega al cruce"
    assert sorted(reader.asked[0]) == sorted(cycles)


@pytest.mark.asyncio
async def test_a_read_that_does_not_find_the_cycle_declares_not_found() -> None:
    """La fuente SÍ se consultó: el hueco no es "no hay fuente", es "no está"."""
    worker = _worker(reader=_Reader(CycleRegimeReading(absent=(_CYCLE,), requested=1)))

    evidence = await worker._v2_cycle_risk(_all_fills())

    assert evidence is not None
    row = evidence[_CYCLE]
    assert row.regime is None
    assert "regime_not_found" in row.notes
    assert "regime_not_durable" not in row.notes
    assert row.risk_amount == Decimal("250.0"), "el R se mide igual: el hueco es del régimen"


@pytest.mark.asyncio
async def test_the_gaps_are_declared_in_the_log(caplog: pytest.LogCaptureFixture) -> None:
    worker = _worker(reader=_Reader(CycleRegimeReading(absent=(_CYCLE,), requested=1)))
    with caplog.at_level(logging.WARNING):
        await worker._v2_cycle_risk(_all_fills())

    assert "cycle regime gaps" in caplog.text
    assert REGIME_READ_ABSENT == "regime_absent", "el motivo declarado viaja con su nombre"


@pytest.mark.asyncio
async def test_a_repeated_trace_is_declared_without_crying_wolf(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reintento del tick (paso 4): se declara en el log, NO se eleva a hueco."""
    reading = CycleRegimeReading(
        regime_by_cycle={_CYCLE: _REGIME},
        requested=1,
        duplicates={_CYCLE: 1},
    )
    worker = _worker(reader=_Reader(reading))
    with caplog.at_level(logging.INFO):
        evidence = await worker._v2_cycle_risk(_all_fills())

    assert evidence is not None
    assert "cycle regime duplicates" in caplog.text
    assert "cycle regime gaps" not in caplog.text, "un duplicado no es un hueco"
    assert evidence[_CYCLE].regime == _REGIME, "se publica el régimen de la traza más nueva"


@pytest.mark.asyncio
async def test_the_gap_warning_keeps_the_duplicate_note_when_both_exist(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Con huecos Y duplicados, el aviso de huecos no puede comerse la nota del reintento."""
    reading = CycleRegimeReading(
        regime_by_cycle={_CYCLE: _REGIME},
        absent=("cyc-missing",),
        requested=2,
        duplicates={_CYCLE: 1},
    )
    worker = _worker(reader=_Reader(reading))
    with caplog.at_level(logging.WARNING):
        await worker._v2_cycle_risk(_all_fills())

    assert "cycle regime gaps" in caplog.text
    assert "'collapsedRows': 1" in caplog.text, "la nota viaja dentro del aviso"


# ── Sin lector: comportamiento de AUTO-9, intacto ───────────────────────────────────


@pytest.mark.asyncio
async def test_without_a_reader_the_auto9_declaration_is_kept() -> None:
    evidence = await _worker(reader=None)._v2_cycle_risk(_all_fills())

    assert evidence is not None
    row = evidence[_CYCLE]
    assert row.regime is None
    assert "regime_not_durable" in row.notes
    assert row.regime_measurement == "UNKNOWN"
    assert row.risk_amount == Decimal("250.0")


@pytest.mark.asyncio
async def test_without_a_reader_the_plan_keeps_declaring_the_regime_unknown() -> None:
    plan = await _plan(_worker(reader=None))

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.regime == ADAPTIVE_REGIME_UNKNOWN, "sin lectura no se atribuye régimen"


# ── Lector roto: fail-open declarado, sin perder el R ───────────────────────────────


@pytest.mark.asyncio
async def test_a_broken_reader_degrades_declaring_and_keeps_the_r(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = _worker(reader=_BrokenReader())
    with caplog.at_level(logging.ERROR):
        evidence = await worker._v2_cycle_risk(_all_fills())

    assert evidence is not None
    assert "cycle regime read failed" in caplog.text, "el fallo se declara, no se silencia"
    row = evidence[_CYCLE]
    assert row.risk_amount == Decimal("250.0"), "el denominador viene de otra fuente y se conserva"
    assert row.regime is None
    assert "regime_not_durable" in row.notes, "sin lectura NO se afirma que la fuente se leyó"
