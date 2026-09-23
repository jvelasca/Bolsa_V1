"""AUTO-12 — la costura de la CONFIANZA estadística dentro del worker del tick.

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/analytics/tests/test_auto_adaptive_confidence.py``): que la confianza se
construya de los MISMOS fills que el informe —sin un segundo productor ni I/O nuevo—, que el
reparto publicado en el journal encoja el edge fino frente al de historia amplia, que el
payload conserve su forma (la confianza viaja dentro de ``healthByStrategy``), que sin fuente
durable o con lectura rota se degrade al comportamiento histórico declarándolo, y que sin
contexto de fills el tick no pague ninguna lectura.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import AdaptivePolicy
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_adaptive_journal import (
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
    build_adaptive_recommendation_entry,
)
from bolsa_application.sim_durable_store import SimFillFinanceContext

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35


def _fill(
    version: str,
    index: int,
    *,
    side: str,
    price: str,
    day: int,
    month: int = 9,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=f"{version}-{index}-{side}",
        instrument_id="AAA",
        side=side,
        quantity=Decimal("10"),
        price=Decimal(price),
        account_id=_ACCOUNT,
        venue="SIM",
        strategy_version_id=version,
        cycle_id=f"cyc-{version}-{index}",
        created_at=datetime(2026, month, day, 9 if side == "buy" else 15, 0, tzinfo=UTC),
    )


def _profitable_cycles(
    version: str,
    count: int,
    *,
    day: int = 1,
    month: int = 9,
    with_instants: bool = True,
) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados y ganadores (entrada 100 → salida 110).

    ``with_instants=False`` los deja SIN ``created_at``: es el material real de un origen que
    no declara fechas, y la ruta que debe declarar el hueco en vez de ordenar por posición.
    """
    fills: list[SimFillFinanceContext] = []
    for index in range(count):
        for side, price in (("buy", "100"), ("sell", "110")):
            fill = _fill(version, index, side=side, price=price, day=day, month=month)
            if not with_instants:
                fill = SimFillFinanceContext(
                    execution_id=fill.execution_id,
                    instrument_id=fill.instrument_id,
                    side=fill.side,
                    quantity=fill.quantity,
                    price=fill.price,
                    account_id=fill.account_id,
                    venue=fill.venue,
                    strategy_version_id=fill.strategy_version_id,
                    cycle_id=fill.cycle_id,
                )
            fills.append(fill)
    return fills


class _FillStore:
    """Store de fills de mentira que CUENTA las lecturas: la confianza no puede añadir I/O."""

    def __init__(self, by_version: dict[str, list[SimFillFinanceContext]], *, broken: bool = False):
        self._by_version = by_version
        self._broken = broken
        self.calls: list[str] = []

    async def list_for_strategy_version(
        self, version: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        self.calls.append(version)
        if self._broken:
            raise RuntimeError("PG caído")
        return list(self._by_version.get(version, ()))


class _Reservations:
    """Reservas de mentira: una entrada con riesgo medido por ciclo (el denominador de R)."""

    def __init__(self) -> None:
        self.calls = 0

    async def list_by_cycle_ids(
        self, _account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
        self.calls += 1
        return [
            SimpleNamespace(
                cycle_id=cycle_id,
                reservation_id=f"RES-{cycle_id}",
                is_buy=True,
                reserved_risk="5",
                cost=None,
                created_at="2026-09-01T09:00:00+00:00",
            )
            for cycle_id in cycle_ids
        ]


class _Journal:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def sink(self, entry: Any) -> None:
        self.entries.append(entry)


def _worker(
    *,
    store: Any | None = None,
    reservations: Any | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = reservations
    worker._cycle_regime_reader = None
    worker._v2_adaptive_paused_cycles = {}
    # AUTO-13 paso 4: la memoria de la rampa arranca vacia (el lector durable la siembra).
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    return worker


@pytest.mark.asyncio
async def test_the_confidence_is_built_without_a_second_reader_on_the_same_fills() -> None:
    """Una lectura por versión: la confianza reutiliza el material, no lo vuelve a pedir."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(store=store, reservations=_Reservations())

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert store.calls == ["orb-1"], "la confianza no puede pagar I/O nuevo"


@pytest.mark.asyncio
async def test_the_published_evidence_carries_the_confidence_without_a_new_payload_key() -> None:
    """La confianza viaja DENTRO de ``healthByStrategy``: misma forma, sin migración."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(store=store, reservations=_Reservations())
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")
    assert plan is not None

    journal = _Journal()
    worker._adaptive_sink = journal.sink
    await worker._v2_journal_adaptive_recommendation(plan)

    assert len(journal.entries) == 1
    entry = journal.entries[0]
    assert entry.event_type == AUTO_ADAPTIVE_RECOMMENDATION_EVENT
    payload = entry.payload
    assert payload is not None
    health = payload["healthByStrategy"]["orb-1"]
    assert health["confidence"] is not None, "sin confianza el operador no distingue 12 de 180"
    assert health["decay"] is not None
    assert "recentExpectancyR" in health and "longExpectancyR" in health
    assert entry.payload["readOnly"] is True


@pytest.mark.asyncio
async def test_a_thin_edge_loses_weight_against_a_broad_one_in_the_published_plan() -> None:
    """El caso §25 del audit, de punta a punta: A ``N=12`` no puede pesar como B ``N=180``."""
    fills = {
        "thin": _profitable_cycles("thin", 12),
        "broad": _profitable_cycles("broad", 180),
    }
    worker = _worker(store=_FillStore(fills), reservations=_Reservations())

    plan = await worker._v2_build_adaptive_plan({"thin", "broad"}, "TREND_UP")

    assert plan is not None
    thin = plan.risk_multiplier_for("thin")
    broad = plan.risk_multiplier_for("broad")
    assert broad >= thin, "la muestra amplia no puede quedar por detrás de la fina"
    assert 0.0 < thin <= 1.0 and 0.0 < broad <= 1.0


@pytest.mark.asyncio
async def test_without_a_fill_store_the_tick_pays_no_read_and_stays_historical() -> None:
    """Sin fuente de fills el plan es ``None`` (fail-closed): no se rota ni se estrecha a ciegas."""
    worker = _worker(store=None, reservations=_Reservations())

    assert await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP") is None


@pytest.mark.asyncio
async def test_a_broken_fill_read_degrades_to_the_historical_behaviour(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un fallo de lectura se DECLARA y no se inventa confianza sobre datos que no se leyeron."""
    import logging

    worker = _worker(store=_FillStore({}, broken=True), reservations=_Reservations())

    with caplog.at_level(logging.ERROR):
        plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is None
    assert "adaptive fill read failed" in caplog.text


@pytest.mark.asyncio
async def test_without_instants_the_gap_is_declared_at_tick_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sin ``created_at`` no hay ventana reciente honesta: se declara el hueco (no se inventa)."""
    import logging

    fills = _profitable_cycles("orb-1", 12, with_instants=False)
    worker = _worker(store=_FillStore({"orb-1": fills}), reservations=_Reservations())

    with caplog.at_level(logging.WARNING):
        plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None, "el plan sigue construyéndose: el hueco es de la ventana reciente"
    assert "confidence gaps" in caplog.text


def test_the_policy_used_by_the_worker_seals_the_auto13_rule() -> None:
    """La política del tick es la MISMA que sella el plan: no hay una copia paralela.

    ``auto12-v1`` selló el encogimiento por muestra; ``AUTO-13`` la sube a ``auto13-v1`` al añadir
    el techo de la rampa de reincorporación al reparto, así que el sello se actualiza con nombre
    (es el único rojo admisible del delta simétrico).
    """
    worker = _worker(store=None, reservations=None)
    policy = worker._v2_adaptive_policy()

    assert policy.policy_version == "auto13-v1"
    assert policy.confidence_prior > 0
    assert policy.recovery_steps[0] > 0


@pytest.mark.asyncio
async def test_the_recommendation_entry_is_reproducible_with_the_confidence_evidence() -> None:
    """Mismo material ⇒ misma evidencia y misma identidad, con la confianza incluida."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 20)})
    worker = _worker(store=store, reservations=_Reservations())
    first = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")
    assert first is not None

    other = _worker(store=_FillStore({"orb-1": _profitable_cycles("orb-1", 20)}), reservations=_Reservations())
    second = await other._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")
    assert second is not None

    entry = build_adaptive_recommendation_entry(
        plan=first, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT
    )
    again = build_adaptive_recommendation_entry(
        plan=second, actor="auto-sim", as_of=_AS_OF, account_id=_ACCOUNT
    )
    assert entry is not None and again is not None
    assert first.as_dict() == second.as_dict()
    assert entry.payload == again.payload
    assert entry.decision_id == again.decision_id


def test_the_shrinkage_knobs_are_the_declared_policy_defaults() -> None:
    policy = AdaptivePolicy()
    assert policy.confidence_prior == pytest.approx(20.0)
    assert policy.severe_decay_factor == pytest.approx(0.5)
