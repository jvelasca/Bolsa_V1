"""AUTO-9 — la costura del productor de riesgo por ciclo dentro del worker (READ-ONLY).

Lo que aquí se prueba es la COSTURA, no la aritmética (esa vive en `test_cycle_risk.py`):
que el worker lea las reservas del CICLO que aparece en los fills y las entregue al
informe; que sin reservas el informe recupere exactamente la forma `AUTO-7`; que un fill
sin ciclo no herede el denominador de otro; y que una lectura rota o saturada degrade
**declarando** en vez de estrechar con un R que no se pudo medir.

El régimen por ciclo no se prueba aquí porque no existe productor: el journal del worker es
en memoria y el productor lo declara hueco (`regime_not_durable`). Ese hueco —y su cierre el
día que exista fuente durable— se verifica en el módulo puro.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import PortfolioReservation
from bolsa_api.background import auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-1"


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    cycle_id: str | None,
    version: str = "orb-1",
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        account_id=_ACCOUNT,
        strategy_version_id=version,
        cycle_id=cycle_id,
    )


def _reservation(
    *,
    reservation_id: str,
    cycle_id: str,
    risk: float = 250.0,
    side: str = "buy",
    created_at: str = "2026-09-22T08:00:00+00:00",
) -> PortfolioReservation:
    return PortfolioReservation(
        reservation_id=reservation_id,
        account_id=_ACCOUNT,
        instrument_id="AAA",
        side=side,
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=risk,
        created_at=created_at,
        cycle_id=cycle_id,
    )


def _worker(
    *,
    fills: list[SimFillFinanceContext] | None = None,
    reservations: list[PortfolioReservation] | None = None,
    reservation_store: Any | None = None,
) -> AutoSimulationWorker:
    """Worker mínimo con los cuatro atributos que el camino Adaptive toca.

    No se construye el driver entero (necesita media docena de stores y una sesión de BD)
    porque la costura bajo prueba no depende de nada más: `_v2_build_adaptive_plan` lee
    fills, lee reservas por ciclo y arma el plan con la política del tick.
    """
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    context = InMemorySimFillFinanceContextStore()
    for fill in fills or []:
        context._rows[fill.execution_id] = fill
    worker._context_store = context
    if reservation_store is None:
        reservation_store = InMemoryReservationStore(seed=tuple(reservations or ()))
    worker._reservation_store = reservation_store
    worker._v2_tunables = SimpleNamespace(adaptive_win_rate_floor=0.35)
    worker._v2_adaptive_paused_cycles = {}
    # AUTO-13 paso 4: la memoria de la rampa arranca vacia (el lector durable la siembra).
    worker._v2_adaptive_reactivated_at = {}
    # AUTO-10: sin lector de régimen inyectado, la fuente durable NO se consulta y el hueco se
    # declara como en AUTO-9 (`regime_not_durable`). Ese es justo el comportamiento que esta
    # costura certifica: medir el R no depende de que exista la vía del régimen.
    worker._cycle_regime_reader = None
    return worker


def _closed_cycle(cycle_id: str) -> list[SimFillFinanceContext]:
    """Un ciclo cerrado con +250 de PnL (10 × (125 − 100))."""
    return [
        _fill("buy", "10", "100", execution_id=f"e1-{cycle_id}", cycle_id=cycle_id),
        _fill("sell", "10", "125", execution_id=f"e2-{cycle_id}", cycle_id=cycle_id),
    ]


class _BrokenReservationStore:
    """Store que no puede leer: el camino debe degradar declarando, no inventar."""

    async def list_by_cycle_ids(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("reservas ilegibles")


# ── El worker entrega el denominador del ciclo ──────────────────────────────────────


@pytest.mark.asyncio
async def test_the_worker_measures_the_r_from_the_cycle_reservation() -> None:
    plan = await _worker(
        fills=_closed_cycle("cyc-1"),
        reservations=[_reservation(reservation_id="res-1", cycle_id="cyc-1", risk=250.0)],
    )._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.expectancy_r == pytest.approx(1.0), "250 de PnL sobre 250 de riesgo"
    assert health.net_expectancy_r is None, "sin coste medido el neto NO se afirma"
    assert plan.evidence_for("orb-1")["expectancyR"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_without_reservations_the_plan_keeps_the_auto7_shape() -> None:
    """Un store vacío NO es evidencia: el informe queda como estaba (sin R inventado)."""
    measured_plan = await _worker(
        fills=_closed_cycle("cyc-1"),
        reservations=[_reservation(reservation_id="res-1", cycle_id="cyc-1")],
    )._v2_build_adaptive_plan({"orb-1"}, "trend_up")
    bare_plan = await _worker(fills=_closed_cycle("cyc-1"))._v2_build_adaptive_plan(
        {"orb-1"}, "trend_up"
    )

    assert bare_plan is not None and measured_plan is not None
    bare = bare_plan.health_for("orb-1")
    measured = measured_plan.health_for("orb-1")
    assert bare is not None and measured is not None
    assert bare.expectancy_r is None, "sin reserva no hay denominador: se declara"
    assert measured.expectancy_r == pytest.approx(1.0)
    # El hueco no cambia el eje del reparto: el R solo se adopta si TODO el pool lo mide.
    assert bare_plan.allocation.evidence_axis == "expectancy_currency"


@pytest.mark.asyncio
async def test_a_reservation_of_another_cycle_is_not_borrowed() -> None:
    """El denominador de otro ciclo no se presta: el ciclo huérfano queda declarado."""
    plan = await _worker(
        fills=_closed_cycle("cyc-1"),
        reservations=[_reservation(reservation_id="res-x", cycle_id="cyc-9", risk=999.0)],
    )._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.expectancy_r is None


@pytest.mark.asyncio
async def test_a_fill_without_a_cycle_is_not_measured_by_a_borrowed_denominator() -> None:
    """Un fill anterior a 2.47 (sin ciclo) no tiene reserva: "sin ciclo" ≠ "ciclo vacío"."""
    fills = [
        _fill("buy", "10", "100", execution_id="e1", cycle_id=None),
        _fill("sell", "10", "125", execution_id="e2", cycle_id=None),
    ]
    plan = await _worker(
        fills=fills, reservations=[_reservation(reservation_id="res-1", cycle_id="cyc-1")]
    )._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.expectancy_r is None


# ── Degradación declarada ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_broken_read_degrades_declaring_instead_of_inventing() -> None:
    plan = await _worker(
        fills=_closed_cycle("cyc-1"), reservation_store=_BrokenReservationStore()
    )._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None, "la salud (fills) sigue mandando: no se aborta el plan"
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.expectancy_r is None, "sin lectura no hay R: se declara, no se asume"
    assert plan.allocation.evidence_axis == "expectancy_currency"


@pytest.mark.asyncio
async def test_without_a_reservation_store_the_adaptive_path_still_works() -> None:
    """Sin libro de reservas no hay R, pero la salud de los fills sigue decidiendo."""
    worker = _worker(fills=_closed_cycle("cyc-1"))
    worker._reservation_store = None

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None
    assert health.expectancy_currency is not None
    assert health.expectancy_r is None


@pytest.mark.asyncio
async def test_a_saturated_read_declares_the_cycles_that_did_not_fit(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Agotar el tope NO inventa: los ciclos que no cupieron quedan sin denominador."""
    monkeypatch.setattr(worker_module, "_V2_CYCLE_RISK_READ_LIMIT", 1)
    worker = _worker(
        fills=_closed_cycle("cyc-1") + _closed_cycle("cyc-2"),
        reservations=[
            _reservation(reservation_id="res-1", cycle_id="cyc-1", risk=250.0),
            _reservation(reservation_id="res-2", cycle_id="cyc-2", risk=100.0),
        ],
    )
    with caplog.at_level(logging.WARNING):
        plan = await worker._v2_build_adaptive_plan({"orb-1"}, "trend_up")

    assert plan is not None
    health = plan.health_for("orb-1")
    assert health is not None, "un ciclo sin denominador sigue siendo medible en moneda"
    assert health.expectancy_currency is not None
    assert any("saturated" in record.getMessage() for record in caplog.records), (
        "una lectura saturada no puede pasar en silencio"
    )
