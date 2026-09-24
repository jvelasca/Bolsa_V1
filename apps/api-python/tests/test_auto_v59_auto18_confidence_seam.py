"""AUTO-18 — la costura de la CONFIANZA ESTADÍSTICA y el METRO del coste, de punta a punta.

Prueba la COSTURA, no la aritmética (esa vive en
``packages/py/analytics/tests/test_auto_adaptive_confidence.py``): que el plan que se publica
lleve la muestra **efectiva estadística** (``measuredN``/``episodes``/``effectiveN``), su
cobertura por independencia, la expectancy encogida y el factor que de verdad se aplicó, todo
dentro de la forma existente (``healthByStrategy``, sin migración); y que el sello del reparto
suba a ``auto18-v1`` porque el número que decide cambió de regla.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import AdaptivePolicy
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
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


def _profitable_cycles(version: str, count: int, *, day: int = 1) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados y ganadores (entrada 100 → salida 110)."""
    fills: list[SimFillFinanceContext] = []
    for index in range(count):
        for side, price in (("buy", "100"), ("sell", "110")):
            fills.append(_fill(version, index, side=side, price=price, day=day + index))
    return fills


class _FillStore:
    def __init__(self, by_version: dict[str, list[SimFillFinanceContext]]) -> None:
        self._by_version = by_version

    async def list_for_strategy_version(
        self, version: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        return list(self._by_version.get(version, ()))


class _Reservations:
    """Reservas de mentira con riesgo medido por ciclo (el denominador de R)."""

    def __init__(self, *, cost: Any | None = None) -> None:
        self._cost = cost

    async def list_by_cycle_ids(
        self, _account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
        return [
            SimpleNamespace(
                cycle_id=cycle_id,
                reservation_id=f"RES-{cycle_id}",
                is_buy=True,
                reserved_risk="5",
                cost=self._cost,
                created_at="2026-09-01T09:00:00+00:00",
            )
            for cycle_id in cycle_ids
        ]


def _worker(*, store: Any | None = None, reservations: Any | None = None) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = reservations
    worker._cycle_regime_reader = None
    worker._v2_adaptive_paused_cycles = {}
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
async def test_the_evidence_carries_the_statistical_sample_and_the_applied_shrink() -> None:
    """Los seis campos de ``AUTO-18`` viajan en ``healthByStrategy`` sin clave nueva.

    ``measuredN``/``episodes``/``effectiveN`` dicen con qué muestra se DECIDIÓ; ``coverage``
    declara la independencia; ``shrunkExpectancyR`` mide el encogimiento y ``shrinkFactor`` es el
    factor que de verdad se aplicó. Sin los seis juntos el operador no puede auditar el peso.
    """
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(store=store, reservations=_Reservations())
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    evidence = plan.evidence_for("orb-1")
    assert evidence is not None
    assert evidence["measuredN"] == 12
    assert evidence["episodes"] == 1, "12 ciclos sin lector de régimen = una sola racha (UNKNOWN)"
    assert evidence["effectiveN"] == 1, "la independencia ACOTA la muestra medida"
    assert evidence["coverage"] == "LOW"
    assert evidence["shrunkExpectancyR"] is not None
    assert 0.0 < evidence["shrinkFactor"] <= 1.0


@pytest.mark.asyncio
async def test_the_statistical_sample_narrows_more_than_the_measured_one() -> None:
    """La muestra efectiva (1 racha) encoge MÁS que la medida (12 ciclos): es el punto de AUTO-18.

    Con prior 20, ``12/(12+20) = 0.375`` pero ``1/(1+20) ≈ 0.0476``: el factor publicado tiene que
    ser el de la muestra ESTADÍSTICA, no el de la bruta.
    """
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(store=store, reservations=_Reservations())
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    factor = plan.evidence_for("orb-1")["shrinkFactor"]
    assert factor == pytest.approx(1.0 / (1.0 + AdaptivePolicy().confidence_prior), rel=1e-3)


def test_the_policy_used_by_the_worker_seals_the_auto18_rule() -> None:
    """La política del tick sella ``auto18-v1``: la ``n`` del encogimiento cambió de regla."""
    worker = _worker(store=None, reservations=None)

    assert worker._v2_adaptive_policy().policy_version == "auto18-v1"
