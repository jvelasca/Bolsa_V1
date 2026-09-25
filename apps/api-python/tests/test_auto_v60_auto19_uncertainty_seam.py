"""AUTO-19A — la costura de la INCERTIDUMBRE del edge (intervalo + ``edgeConfidence``), de punta a punta.

Prueba la COSTURA, no la aritmética (esa vive en
``packages/py/analytics/tests/test_auto_adaptive_uncertainty.py`` y
``.../test_auto_adaptive_replay.py``): que el plan que se publica lleve el frame ``uncertainty`` con
el intervalo por EPISODIOS y la confianza de EDGE por estrategia, que la evidencia
(``healthByStrategy``) gane las dos claves nuevas, y que **el sello del reparto NO suba** —
``auto18-v1``— porque la lectura nueva es evidencia publicada, no una regla nueva.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading
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


def _regime_reader(regimes: dict[str, str]) -> Any:
    """Lector durable de mentira: régimen confirmado por ciclo (AUTO-10)."""

    async def _read(cycle_ids: Any) -> CycleRegimeReading:
        found = {cid: regimes[cid] for cid in cycle_ids if cid in regimes}
        return CycleRegimeReading(regime_by_cycle=found, requested=len(list(cycle_ids)))

    return _read


def _worker(
    *,
    store: Any | None = None,
    reservations: Any | None = None,
    regimes: dict[str, str] | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = reservations
    worker._cycle_regime_reader = _regime_reader(regimes) if regimes else None
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


def _alternating_regimes(version: str, count: int) -> dict[str, str]:
    return {
        f"cyc-{version}-{index}": "TREND_UP" if index % 2 else "RANGE"
        for index in range(count)
    }


@pytest.mark.asyncio
async def test_the_plan_carries_the_interval_and_the_edge_confidence() -> None:
    """El frame ``uncertainty`` viaja con el intervalo por EPISODIOS y la banda de EDGE."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(
        store=store,
        reservations=_Reservations(),
        regimes=_alternating_regimes("orb-1", 12),
    )
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.uncertainty is not None, "la lectura se publica con el plan"
    payload = plan.as_dict()["uncertainty"]
    row = payload["byStrategy"]["orb-1"]

    assert payload["method"] == "bootstrap_episodes_v2"
    assert row["expectancyInterval"]["episodes"] == 12, "12 ciclos alternando = 12 rachas"
    assert row["expectancyInterval"]["lower"] is not None
    assert row["expectancyInterval"]["lower"] <= row["expectancyInterval"]["point"]
    assert row["expectancyInterval"]["point"] <= row["expectancyInterval"]["upper"]
    assert row["edgeConfidence"] in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


@pytest.mark.asyncio
async def test_the_evidence_gains_the_two_new_keys_without_touching_the_old_ones() -> None:
    """``expectancyInterval``/``edgeConfidence`` entran en la evidencia; las históricas no cambian."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(
        store=store,
        reservations=_Reservations(),
        regimes=_alternating_regimes("orb-1", 12),
    )
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    evidence = plan.evidence_for("orb-1")
    assert evidence is not None
    assert "expectancyInterval" in evidence
    assert "edgeConfidence" in evidence
    row = plan.uncertainty.uncertainty_for("orb-1")
    assert row is not None
    assert evidence["expectancyInterval"] == row.interval.as_dict()
    assert evidence["edgeConfidence"] == row.edge_confidence
    # Las claves de AUTO-18 siguen ahí y con su forma (aditividad, no reemplazo).
    for key in (
        "measuredN",
        "episodes",
        "effectiveN",
        "coverage",
        "shrunkExpectancyR",
        "shrinkFactor",
    ):
        assert key in evidence


@pytest.mark.asyncio
async def test_an_insufficient_interval_is_declared_not_fabricated() -> None:
    """Sin rachas de régimen (un solo tramo) hay punto pero NO intervalo: se declara."""
    store = _FillStore({"orb-1": _profitable_cycles("orb-1", 12)})
    worker = _worker(store=store, reservations=_Reservations(), regimes=None)
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    row = plan.as_dict()["uncertainty"]["byStrategy"]["orb-1"]
    assert row["expectancyInterval"]["lower"] is None
    assert "insufficient_episodes" in row["expectancyInterval"]["notes"]
    assert row["edgeConfidence"] == "UNKNOWN", "sin medición no se afirma edge"


def test_the_policy_used_by_the_worker_still_seals_the_auto18_rule() -> None:
    """AUTO-19A mide, no reparte: el sello del reparto NO se mueve."""
    worker = _worker(store=None, reservations=None)

    assert worker._v2_adaptive_policy().policy_version == "auto18-v1"
