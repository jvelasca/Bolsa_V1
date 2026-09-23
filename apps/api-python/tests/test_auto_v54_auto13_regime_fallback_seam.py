"""AUTO-13 — la costura del FALLBACK del hueco de régimen (§20) y de los tres ejes separados (§29).

Lo que se prueba es la COSTURA, no la aritmética (esa vive en
``packages/py/analytics/tests/test_auto_adaptive.py``): que un régimen que **no se pudo leer**
(``None``/``UNKNOWN``) degrade el gate declarando el hueco y **jamás** arme la rama adversa de la
rotación; que sin régimen del cruce ``strategy × regime`` la decisión caiga a la evidencia
**global** con la salida declarada; y que los tres ejes del audit —operativo, datos y calidad—
viajen en campos PROPIOS, de modo que ``ACTIVE`` + datos ``DEGRADED`` + calidad ``LOW`` se pueda
leer entero sin que un eje se disfrace de otro.

El control del test es el régimen adverso REAL (``BEAR_TREND`` del tick ⇒ ``TREND_DOWN``) con la
misma muestra fina: si la rama adversa no se armase, el control lo vería. Sin ese control, "no se
pausa" también pasaría con una rotación muerta que no juzgase nada.

El flag Adaptive OFF deja el método sin llamar (worker ``_v2_plan_tick``), así que esta costura no
añade I/O propio: el gate se compone de los hechos que el tick ya midió.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import ADAPTIVE_STRATEGY_REGIME_RISK
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_cycle_regime_reader import CycleRegimeReading
from bolsa_application.sim_durable_store import SimFillFinanceContext

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35
#: Ciclos de una muestra FINA: por debajo de ``min_trades`` (10) la salud no es decisoria, así que
#: la única rama que podría pausarla es la de régimen adverso.
_THIN_CYCLES = 3


def _fill(version: str, index: int, *, side: str, price: str) -> SimFillFinanceContext:
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
        created_at=datetime(2026, 9, 1, 9 if side == "buy" else 15, 0, tzinfo=UTC),
    )


def _losing_thin(version: str, count: int = _THIN_CYCLES) -> list[SimFillFinanceContext]:
    """``count`` ciclos perdedores: win rate 0 % (por debajo del suelo) y muestra NO decisoria."""
    return [
        _fill(version, index, side=side, price=price)
        for index in range(count)
        for side, price in (("buy", "110"), ("sell", "100"))
    ]


def _profitable(version: str, count: int) -> list[SimFillFinanceContext]:
    return [
        _fill(version, index, side=side, price=price)
        for index in range(count)
        for side, price in (("buy", "100"), ("sell", "110"))
    ]


class _FillStore:
    def __init__(self, by_version: dict[str, list[SimFillFinanceContext]]) -> None:
        self._by_version = by_version
        self.calls: list[str] = []

    async def list_for_strategy_version(
        self, version: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        self.calls.append(version)
        return list(self._by_version.get(version, ()))


class _Reservations:
    """Reservas de mentira: una entrada con riesgo medido por ciclo (el denominador de R)."""

    async def list_by_cycle_ids(
        self, _account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
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


class _Reader:
    """Lector de régimen por ciclo: nombra el régimen de los ciclos pedidos (o no encuentra)."""

    def __init__(self, regime: str | None = None) -> None:
        self._regime = regime
        self.asked: list[list[str]] = []

    async def __call__(self, cycle_ids: Any) -> CycleRegimeReading:
        cycles = list(cycle_ids)
        self.asked.append(cycles)
        if self._regime is None:
            return CycleRegimeReading(absent=tuple(cycles), requested=len(cycles))
        return CycleRegimeReading(
            regime_by_cycle={cycle_id: self._regime for cycle_id in cycles},
            requested=len(cycles),
        )


def _worker(
    *,
    store: Any | None = None,
    regime_reader: Any | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = _Reservations()
    worker._cycle_regime_reader = regime_reader
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_sink_failures = 0
    worker._v2_adaptive_journal_anchor_age = 0
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    return worker


# ── §20, mitad del gate: el régimen que no se pudo leer DEGRADA, nunca acusa ────────


@pytest.mark.asyncio
async def test_a_missing_tick_regime_degrades_the_gate_and_never_arms_the_adverse_branch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``None`` ⇒ datos ``DEGRADED`` (``regime_absent``) y la muestra fina NO se pausa."""
    store = _FillStore({"thin": _losing_thin("thin")})
    worker = _worker(store=store)

    with caplog.at_level(logging.WARNING):
        plan = await worker._v2_build_adaptive_plan({"thin"}, None)

    assert plan is not None, "el tick sigue construyendo plan: el hueco de régimen no lo borra"
    assert store.calls == ["thin"], "el gate no paga una lectura nueva"
    assert "data gate DEGRADED" in caplog.text
    assert "regime_absent" in caplog.text
    assert "regimeAvailable': False" in caplog.text
    assert not plan.rotation.is_paused("thin"), "un régimen ilegible no es un régimen adverso"
    assert plan.rotation.reason_for("thin") is None


@pytest.mark.asyncio
async def test_an_explicit_unknown_regime_is_the_same_declared_gap() -> None:
    """``UNKNOWN`` es el hueco declarado, no un régimen: mismo efecto, misma ausencia de pausa."""
    worker = _worker(store=_FillStore({"thin": _losing_thin("thin")}))

    plan = await worker._v2_build_adaptive_plan({"thin"}, "UNKNOWN")

    assert plan is not None
    assert not plan.rotation.is_paused("thin")
    assert plan.regime_undetermined == ("thin",)


@pytest.mark.asyncio
async def test_a_real_adverse_regime_does_arm_the_branch_the_test_controls() -> None:
    """Control del test anterior: con régimen adverso REAL la misma muestra fina SÍ se pausa.

    El régimen del tick llega en el eje **operativo** (``market_regime_gate``: ``BEAR_TREND``) y el
    plan lo traduce al eje de mercado (``TREND_DOWN``), que es el que la rotación juzga. Se prueba
    con la entrada REAL del tick, no con una traducción de conveniencia del test.
    """
    worker = _worker(store=_FillStore({"thin": _losing_thin("thin")}))

    plan = await worker._v2_build_adaptive_plan({"thin"}, "BEAR_TREND")

    assert plan is not None
    assert plan.regime == "TREND_DOWN", "el eje operativo del tick se traduce al de mercado"
    assert plan.rotation.is_paused("thin")
    assert plan.rotation.reason_for("thin") == ADAPTIVE_STRATEGY_REGIME_RISK


# ── §20, mitad de la rotación: sin cruce determinado manda la evidencia GLOBAL ──────


@pytest.mark.asyncio
async def test_without_a_cross_regime_the_tick_declares_the_fallback_to_global_evidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sin lector durable no hay celda de régimen: se declara el hueco y la salida declarada."""
    worker = _worker(store=_FillStore({"orb-1": _profitable("orb-1", 12)}))

    with caplog.at_level(logging.INFO):
        plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.regime_undetermined == ("orb-1",)
    assert "regime undetermined" in caplog.text
    assert "'regimeUndetermined': ['orb-1']" in caplog.text
    assert "'fallback': 'strategy_evidence'" in caplog.text


@pytest.mark.asyncio
async def test_a_determined_cross_regime_is_not_declared_as_a_gap() -> None:
    """Con la celda decisiva nombrada no hay hueco que declarar: el campo viaja vacío."""
    store = _FillStore({"orb-1": _profitable("orb-1", 10)})
    worker = _worker(store=store, regime_reader=_Reader("TREND_UP"))

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.health_for("orb-1").regime == "TREND_UP"
    assert plan.regime_undetermined == ()
    assert plan.health_for("orb-1").decisive is True


# ── §29: los tres ejes, en campos propios ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_three_axes_travel_side_by_side_without_sharing_a_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``ACTIVE`` (operativo) + ``DEGRADED`` (datos) + ``LOW`` (calidad) se leen enteros y separados."""
    store = _FillStore({"thin": _losing_thin("thin"), "broad": _profitable("broad", 6)})
    worker = _worker(store=store)

    with caplog.at_level(logging.WARNING):
        plan = await worker._v2_build_adaptive_plan({"thin", "broad"}, None)

    assert plan is not None
    payload = plan.as_dict()

    # Eje OPERATIVO: campo propio, con su vocabulario y sin el de los otros dos.
    operational = payload["operationalStates"]
    assert set(operational.values()) <= {"active", "paused", "recovering"}
    assert operational["thin"] == "active"

    # Eje de DATOS: el estado del gate, con SU vocabulario, en su propio registro del tick.
    assert "data gate DEGRADED" in caplog.text and "data gate OK" not in caplog.text
    assert "'effect': 'LIMITS'" in caplog.text
    for value in operational.values():
        assert value not in {"OK", "DEGRADED", "STALE", "BLOCKED"}

    # Eje de CALIDAD: la banda medida SOBREVIVE al gate que limita (lo que se apaga es el USO, no
    # el hecho medido) y vive en la evidencia de la fila, no en el estado operativo ni en el gate.
    band = plan.health_for("broad").confidence
    assert band in {"LOW", "MEDIUM", "HIGH"}
    assert plan.shrinkage is False, "el gate limitó: el reparto no encoge con esa banda"
    assert payload["shrinkage"] is False
    assert "OK" not in operational.values()


@pytest.mark.asyncio
async def test_the_axes_do_not_change_each_other_in_their_own_direction() -> None:
    """El mismo material con el gate ``OK`` no toca el eje operativo: solo cambia el de datos."""
    fills = {"thin": _losing_thin("thin"), "broad": _profitable("broad", 6)}

    degraded = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad"}, None
    )
    healthy = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad"}, "TREND_UP"
    )

    assert degraded is not None and healthy is not None
    assert degraded.as_dict()["operationalStates"] == healthy.as_dict()["operationalStates"]
    assert degraded.shrinkage is False and healthy.shrinkage is True
