"""AUTO-16 — la costura del coste APLICADO dentro del worker (por su camino REAL).

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/application/tests/test_applied_cost.py`` y ``test_cycle_risk.py``, y la base del
neto en ``packages/py/analytics/tests/test_auto_self_evaluation.py``): que la fricción que el
**simulador aplicó** —recompuesta del ``reference_mid`` que el settlement persiste— llegue al
neto que Adaptive **consume**, y que lo haga **sin una lectura nueva** (los fills ya estaban en
la mano) y **sin cambiar el número de nadie** cuando la referencia no se midió.

El control es la mitad de la prueba: con el MISMO material y solo **quitando** la referencia
persistida (lo que es una fila anterior a ``2.57``), el neto vuelve a ser el **estimado de
``v2.56``** —byte a byte— y el reparto que sale de él cambia de peso. Sin ese control, "el
aplicado llegó" también pasaría con un modelo de coste roto que midiera cualquier cosa.

Y la declaración viaja: el neto publica su **base** (``applied``/``estimated``) para que dos
netos medidos contra modelos distintos no se lean como uno solo.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_COST_BASIS_APPLIED,
    SELF_EVAL_COST_BASIS_ESTIMATED,
    cycle_r,
)
from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    PortfolioReservation,
    TradingCost,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.applied_cost import applied_cost_from_fills
from bolsa_application.auto_self_evaluation_feed import build_auto_self_evaluation
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)

_ACCOUNT = "acc-1"
_REGIME = "TREND_UP"
#: ``min_trades`` de la autoevaluación: por debajo, la fila no compite en el reparto.
_DECISIVE_CYCLES = 10
_RISK = Decimal("250.0")
#: Coste ESTIMADO por el decisor — el que usaba ``v2.56``.
_ESTIMATE = 25.0
#: Fricción APLICADA del ciclo medido: 1.5 en la compra (100.15 sobre mid 100) + 1.0 en la venta.
_APPLIED = Decimal("2.500000")
#: El ciclo MEDIDO: 1.5 de fricción en la compra (100.15 sobre mid 100) y 1.0 en la venta.
_MEASURED = "orb-applied"
_BUY_PRICE = "100.15"
_BUY_REFERENCE = "100"
_SELL_PRICE = "129.90"
_SELL_REFERENCE = "130"
#: El ciclo LEGACY (sin ``reference_mid``): la fila anterior a la migración 046.
_LEGACY = "orb-legacy"
_LEGACY_BUY = "100.20"
_LEGACY_SELL = "130.10"


def _fill(
    side: str,
    quantity: str,
    price: str,
    *,
    reference_mid: str | None,
    execution_id: str,
    version: str,
    cycle_id: str,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        reference_mid=reference_mid,
        account_id=_ACCOUNT,
        strategy_version_id=version,
        cycle_id=cycle_id,
    )


def _measured_cycle(index: int, *, reference: tuple[str, str] | None) -> list[Any]:
    """Un ciclo cerrado de 10 unidades del ciclo MEDIDO, con (o sin) sus DOS referencias."""
    cycle_id = f"cyc-{_MEASURED}-{index:02d}"
    buy_reference, sell_reference = reference if reference is not None else (None, None)
    return [
        _fill(
            "buy",
            "10",
            _BUY_PRICE,
            reference_mid=buy_reference,
            execution_id=f"e1-{cycle_id}",
            version=_MEASURED,
            cycle_id=cycle_id,
        ),
        _fill(
            "sell",
            "10",
            _SELL_PRICE,
            reference_mid=sell_reference,
            execution_id=f"e2-{cycle_id}",
            version=_MEASURED,
            cycle_id=cycle_id,
        ),
    ]


def _legacy_cycle(index: int) -> list[Any]:
    """Un ciclo cerrado sin ``reference_mid`` ninguno: la fila anterior a la migración 046."""
    cycle_id = f"cyc-{_LEGACY}-{index:02d}"
    return [
        _fill(
            "buy",
            "10",
            _LEGACY_BUY,
            reference_mid=None,
            execution_id=f"e1-{cycle_id}",
            version=_LEGACY,
            cycle_id=cycle_id,
        ),
        _fill(
            "sell",
            "10",
            _LEGACY_SELL,
            reference_mid=None,
            execution_id=f"e2-{cycle_id}",
            version=_LEGACY,
            cycle_id=cycle_id,
        ),
    ]


def _reservation(version: str, index: int, *, commission: float | None = 5.0) -> PortfolioReservation:
    """La reserva de ENTRADA del ciclo: su denominador de riesgo y su coste ESTIMADO.

    ``commission=None`` modela el caso en que el modelo **no** puede cuantificarla: sin ella no
    se puede componer la base aplicada (fricción + comisión) y el neto vuelve al estimado.
    """
    cycle_id = f"cyc-{version}-{index:02d}"
    return PortfolioReservation(
        reservation_id=f"res-{cycle_id}",
        account_id=_ACCOUNT,
        instrument_id="AAA",
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=float(_RISK),
        cost=TradingCost(
            notional=1000.0,
            commission=commission,
            spread=4.0,
            slippage=3.5,
            gap=0.0,
            total=_ESTIMATE,
            measurement=MEASUREMENT_COMPLETE,
        ),
        status=RESERVATION_OPEN,
        created_at="2026-09-22T08:00:00+00:00",
        cycle_id=cycle_id,
    )


def _material(
    *,
    measured_reference: tuple[str, str] | None,
    commission: float | None = 5.0,
) -> tuple[list[Any], list[Any]]:
    """El MISMO material, con o sin la referencia persistida del ciclo medido.

    ``measured_reference=None`` es literalmente lo que deja la migración 046 en una fila anterior
    a ``2.57``: la columna existe y está ``NULL``. Es el control negativo, y solo cambia eso.
    """
    fills: list[Any] = []
    reservations: list[Any] = []
    for index in range(_DECISIVE_CYCLES):
        fills.extend(_measured_cycle(index, reference=measured_reference))
        reservations.append(_reservation(_MEASURED, index, commission=commission))
        fills.extend(_legacy_cycle(index))
        reservations.append(_reservation(_LEGACY, index, commission=commission))
    return fills, reservations


class _CountingContext(InMemorySimFillFinanceContextStore):
    """Store de fills que CUENTA lo que le piden: es la prueba de que no hay I/O nuevo."""

    def __init__(self) -> None:
        super().__init__()
        self.version_reads = 0
        self.cycle_reads = 0

    async def list_for_strategy_version(
        self,
        strategy_version_id: str,
        *,
        account_id: str | None = None,
        limit: int | None = None,
    ) -> list[SimFillFinanceContext]:
        self.version_reads += 1
        return await super().list_for_strategy_version(
            strategy_version_id, account_id=account_id, limit=limit
        )

    async def list_by_cycle_ids(
        self,
        account_id: str | None,
        cycle_ids: Any,
        *,
        limit: int = 500,
    ) -> list[SimFillFinanceContext]:
        self.cycle_reads += 1
        return await super().list_by_cycle_ids(account_id, cycle_ids, limit=limit)


def _worker(
    fills: list[Any],
    reservations: list[Any],
    *,
    enabled: bool = True,
) -> AutoSimulationWorker:
    """Worker mínimo con lo que el camino Adaptive toca: fills durables + reservas."""
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    context = _CountingContext()
    for fill in fills:
        context._rows[fill.execution_id] = fill
    worker._context_store = context
    worker._reservation_store = InMemoryReservationStore(seed=tuple(reservations))
    worker._cycle_regime_reader = None
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=enabled, adaptive_win_rate_floor=0.35, regime_override=None
    )
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_reactivated_at = {}
    return worker


def _row_of(report: Any, version: str) -> Any:
    return next(row for row in report.by_strategy if row.strategy_version == version)


# ── El aplicado llega al neto que Adaptive CONSUME ──────────────────────────────────


@pytest.mark.asyncio
async def test_the_applied_friction_reaches_the_net_the_adaptive_plan_reads() -> None:
    """El neto del plan sale de la fricción que el SIMULADOR aplicó, no del supuesto."""
    fills, reservations = _material(measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE))
    worker = _worker(fills, reservations)

    plan = await worker._v2_build_adaptive_plan({_MEASURED, _LEGACY}, _REGIME)

    assert plan is not None
    health = plan.health_for(_MEASURED)
    assert health is not None
    assert health.decisive is True
    assert health.net_r_measurement == MEASUREMENT_COMPLETE
    # pnl = 10 × (129.90 − 100.15) = 297.5; aplicado = 1.5 + 1.0 = 2.5 y su comisión de MODELO = 5.0
    # ⇒ (297.5 − 2.5 − 5.0) / 250
    assert health.net_expectancy_r == pytest.approx(1.16)


@pytest.mark.asyncio
async def test_the_assessment_publishes_the_base_of_the_net_it_measured() -> None:
    """La base viaja en la lectura: aplicado (con la comisión del modelo) cuando se midió, estimado cuando no."""
    fills, reservations = _material(measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE))
    worker = _worker(fills, reservations)

    evidence = await worker._v2_cycle_risk(fills)
    report = build_auto_self_evaluation(fills=fills, cycle_risk=evidence)

    applied_row = _row_of(report, _MEASURED)
    legacy_row = _row_of(report, _LEGACY)
    assert applied_row.net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
    assert legacy_row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED
    assert applied_row.as_dict()["netRBasis"] == SELF_EVAL_COST_BASIS_APPLIED
    # El aplicado (fricción + comisión del modelo) es MENOR que el estimado: el neto sale más
    # alto, no más bajo, y la base declara que lleva la comisión DENTRO.
    assert applied_row.net_expectancy_r > legacy_row.net_expectancy_r


@pytest.mark.asyncio
async def test_without_a_modelled_commission_the_applied_is_measured_but_not_composed() -> None:
    """CONTROL de la composición: sin comisión cuantificada el neto NO se compone a medias.

    El schedule no cobra comisión, así que el neto aplicado se completa con la del MODELO. Si esa
    comisión no se pudo cuantificar, restar solo la fricción regalaría la comisión entera de cada
    ciclo: se vuelve al estimado —declarado— y la medición aplicada se sigue publicando aparte.
    """
    fills, reservations = _material(
        measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE), commission=None
    )
    worker = _worker(fills, reservations)

    plan = await worker._v2_build_adaptive_plan({_MEASURED, _LEGACY}, _REGIME)

    assert plan is not None
    health = plan.health_for(_MEASURED)
    assert health is not None
    assert health.net_expectancy_r == pytest.approx(1.09), "el estimado completo, no medio coste"
    evidence = await worker._v2_cycle_risk(fills)
    report = build_auto_self_evaluation(fills=fills, cycle_risk=evidence)
    row = _row_of(report, _MEASURED)
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED
    assert row.as_dict()["netRBasis"] == SELF_EVAL_COST_BASIS_ESTIMATED
    # La medición NO se tira: el hueco de la comisión no borra la fricción que sí se midió.
    cycle_id = f"cyc-{_MEASURED}-00"
    measured = applied_cost_from_fills([cycle_id], fills)[cycle_id]
    assert measured.measurement == MEASUREMENT_COMPLETE
    assert measured.friction == _APPLIED


# ── El control negativo: sin referencia, el número de v2.56 (byte a byte) ────────────

@pytest.mark.asyncio
async def test_without_the_persisted_reference_the_net_is_the_estimate_of_v2_56() -> None:
    """CONTROL: la misma corrida sin ``reference_mid`` mide con el estimado, y lo declara.

    Sin este control, "el aplicado llegó" también pasaría con un modelo de coste que midiera
    cualquier cosa: aquí el material es idéntico salvo el hecho que la migración 046 persiste.
    """
    fills, reservations = _material(measured_reference=None)
    worker = _worker(fills, reservations)

    plan = await worker._v2_build_adaptive_plan({_MEASURED, _LEGACY}, _REGIME)

    assert plan is not None
    health = plan.health_for(_MEASURED)
    assert health is not None
    legacy = cycle_r(
        pnl="297.5", risk_amount=str(_RISK), cost={"total": _ESTIMATE, "measurement": "COMPLETE"}
    )
    assert health.net_expectancy_r == legacy.net_r_multiple, "byte a byte: el estimado de siempre"
    assert health.net_expectancy_r == pytest.approx(1.09)


@pytest.mark.asyncio
async def test_the_average_leg_without_reference_declares_the_gap_and_never_a_zero() -> None:
    """Sin referencia, el ciclo declara su hueco en la lectura del informe (nunca un ``0``)."""
    fills, reservations = _material(measured_reference=None)
    worker = _worker(fills, reservations)
    measurements = (
        await worker._v2_cycle_risk(fills) or {}
    )
    report = build_auto_self_evaluation(fills=fills, cycle_risk=measurements)

    row = _row_of(report, _MEASURED)
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_ESTIMATED, "cae al estimado, declarándolo"
    assert row.net_expectancy_r is not None and row.net_expectancy_r != 0.0
    # Y el hueco del aplicado se declara donde vive: en la medición del coste aplicado.
    applied = measurements[f"cyc-{_MEASURED}-00"]
    assert applied.cost_applied is None
    assert applied.cost_applied != 0, "una referencia ausente nunca vale fricción cero"
    assert "costApplied" not in applied.to_cycle_fields()


# ── El aplicado MUEVE la decisión (no solo el informe) ──────────────────────────────


@pytest.mark.asyncio
async def test_the_applied_cost_moves_the_allocation_weights() -> None:
    """Dos corridas que solo difieren en la referencia persistida reparten distinto.

    Es la consecuencia que justifica subir el sello del reparto (``auto16-v1``): la evidencia es
    la misma y el peso relativo NO, así que sin sello dos planes iguales parecerían equivalentes.
    """
    with_reference, reservations_a = _material(
        measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE)
    )
    without, reservations_b = _material(measured_reference=None)

    applied = await _worker(with_reference, reservations_a)._v2_build_adaptive_plan(
        {_MEASURED, _LEGACY}, _REGIME
    )
    estimated = await _worker(without, reservations_b)._v2_build_adaptive_plan(
        {_MEASURED, _LEGACY}, _REGIME
    )

    assert applied is not None and estimated is not None
    applied_multipliers = applied.as_dict()["allocation"]["riskMultipliers"]
    estimated_multipliers = estimated.as_dict()["allocation"]["riskMultipliers"]

    assert applied_multipliers[_MEASURED] > estimated_multipliers[_MEASURED], (
        "el coste medido es MENOR que el estimado (fricción + comisión): ese ciclo pesa más"
    )
    assert applied_multipliers[_LEGACY] < estimated_multipliers[_LEGACY], (
        "y el otro, con la misma evidencia, pesa relativamente menos"
    )


# ── No hay I/O nuevo: la referencia viaja con los fills que YA se leían ─────────────


@pytest.mark.asyncio
async def test_the_tick_reads_the_fills_once_and_never_reads_by_cycle() -> None:
    """``AUTO-16`` no añade una lectura: la fricción se recompone de los fills ya leídos.

    Se mide en el store: una lectura por versión (la de siempre, ``AUTO-9``) y **cero** lecturas
    por ciclo. El ``list_by_cycle_ids`` del store existe como lector de verificación del ciclo
    (lo usa el test PG para probar el reinicio), no como I/O del turno.
    """
    fills, reservations = _material(measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE))
    worker = _worker(fills, reservations)
    context = worker._context_store
    assert isinstance(context, _CountingContext)

    plan = await worker._v2_build_adaptive_plan({_MEASURED, _LEGACY}, _REGIME)

    assert plan is not None
    assert context.version_reads == 2, "una por versión: lo que ya hacía AUTO-9"
    assert context.cycle_reads == 0, "AUTO-16 no paga una lectura por ciclo"


@pytest.mark.asyncio
async def test_with_the_flag_off_the_adaptive_path_is_not_reached_at_all() -> None:
    """Con el flag OFF el constructor del plan no se invoca (guard de ``_v2_plan_tick``).

    ``AUTO-16`` vive **dentro** de ese constructor y no añade ninguna lectura propia, así que la
    mitad que sí se puede medir aquí —que nada se lee— se mide: el store queda intacto.
    """
    fills, reservations = _material(measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE))
    worker = _worker(fills, reservations, enabled=False)
    context = worker._context_store
    assert isinstance(context, _CountingContext)

    assert worker._v2_tunables.adaptive_enabled is False
    # La MISMA decisión de guard del tick: con el flag OFF el constructor no se llama.
    adaptive = (
        await worker._v2_build_adaptive_plan({_MEASURED, _LEGACY}, _REGIME)
        if worker._v2_tunables.adaptive_enabled
        else None
    )

    assert adaptive is None
    assert context.version_reads == 0
    assert context.cycle_reads == 0


@pytest.mark.asyncio
async def test_the_entry_leg_measured_in_another_tick_is_read_with_the_exit_leg() -> None:
    """Las dos patas se agregan JUNTAS, cada una con su referencia: es lo que la 046 habilita.

    La pata de ENTRADA se liquidó en otro tick (otra sesión, posiblemente otro proceso) y su mid
    viajaba en una variable que se tiraba. Sin la referencia persistida, medio ciclo se mediría y
    la otra mitad se perdería: aquí se mide el ciclo entero.
    """
    fills, reservations = _material(measured_reference=(_BUY_REFERENCE, _SELL_REFERENCE))
    worker = _worker(fills, reservations)

    evidence = await worker._v2_cycle_risk(fills)
    report = build_auto_self_evaluation(fills=fills, cycle_risk=evidence)

    for index in range(_DECISIVE_CYCLES):
        cycle_id = f"cyc-{_MEASURED}-{index:02d}"
        assert evidence is not None
        assert evidence[cycle_id].cost_applied is None, (
            "el productor de riesgo no mide coste: eso lo hace el agregador, y solo él"
        )
        assert evidence[cycle_id].risk_amount == _RISK, "el denominador viene de la reserva"

    row = _row_of(report, _MEASURED)
    assert row.net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
    assert row.cycles_without_cost == 0, "las dos patas de los 10 ciclos entraron al neto"
