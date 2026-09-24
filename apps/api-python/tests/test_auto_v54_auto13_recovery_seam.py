"""AUTO-13 — la costura de la RAMPA de reincorporación ``RECOVERING`` (paso 4, §23/§24).

Lo que se prueba es la costura del worker, no las piezas puras (esas viven en
``packages/py/analytics/tests/test_auto_adaptive.py``, ``test_auto_adaptive_recovery.py`` y
``test_auto_self_evaluation_feed.py``): que el corte durable (``reactivated_at``) que declara el
lector de ``AUTO-11`` se traduzca en evidencia medida con los MISMOS fills del tick —sin una
lectura más—, que el escalón se aplique como **techo** del reparto (``m_final = min(m_reparto,
escalón)``), que una versión que nunca estuvo pausada conserve el peso pleno, que el estado
operativo se **derive** sin tocar la rotación y que el journal siga escribiendo su forma declarada
(aditivo, sin migración).

   10|Sin corte no hay rampa: la ausencia se declara y el plan es el histórico — la misma disciplina
que ``AUTO-12`` con ``confidence=None``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_STATE_ACTIVE,
    ADAPTIVE_STATE_RECOVERING,
)
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_adaptive_recovery import AdaptiveStateReading, adaptive_state_unread
from bolsa_application.sim_durable_store import SimFillFinanceContext

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35
#: Corte ANTERIOR al ``closedAt`` de los fills de juguete (``2026-09-01T15:00``): la evidencia cae
#: después de la reincorporación, que es lo que la rampa cuenta.
_CUT = "2026-08-31T00:00:00+00:00"


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


def _profitable(version: str, count: int) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados ganadores y medidos (un R positivo cada uno)."""
    return [
        _fill(version, index, side=side, price=price)
        for index in range(count)
        for side, price in (("buy", "100"), ("sell", "110"))
    ]


def _losing(version: str, count: int) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados perdedores y medidos: la fila pasa a ser probadamente negativa."""
    return [
        _fill(version, index, side=side, price=price)
        for index in range(count)
        for side, price in (("buy", "110"), ("sell", "100"))
    ]


class _FillStore:
    """Store de fills que CUENTA las lecturas: la rampa no puede pagar una lectura nueva."""

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


def _worker(
    *,
    store: Any | None = None,
    reactivated: dict[str, str] | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = _Reservations()
    worker._cycle_regime_reader = None
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_sink_failures = 0
    worker._v2_adaptive_journal_anchor_age = 0
    # AUTO-13 paso 4: la memoria derivada de la rampa (el lector durable la siembra al arrancar).
    worker._v2_adaptive_reactivated_at = dict(reactivated or {})
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    return worker


def _reactivated(*versions: str) -> dict[str, str]:
    """Cortes de reincorporación por versión, en el instante del corte de juguete."""
    return {version: _CUT for version in versions}


# ── Sin corte durable no hay rampa ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_without_a_reactivation_cut_the_plan_carries_no_ramp() -> None:
    """La rampa es OPCIONAL: sin corte no hay evidencia, no hay estado ``recovering``."""
    worker = _worker(store=_FillStore({"orb-1": _profitable("orb-1", 12)}))

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.recovery == {}
    assert plan.state_for("orb-1") == ADAPTIVE_STATE_ACTIVE
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_a_version_that_never_paused_keeps_the_full_weight() -> None:
    """El corte es de OTRA versión: la que no volvió de una pausa no lleva rampa ni techo."""
    fills = {"orb-1": _profitable("orb-1", 12), "orb-2": _profitable("orb-2", 1)}
    worker = _worker(store=_FillStore(fills), reactivated=_reactivated("orb-2"))

    plan = await worker._v2_build_adaptive_plan({"orb-1", "orb-2"}, "TREND_UP")

    assert plan is not None
    assert plan.recovery_for("orb-1") is None
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(1.0)
    assert plan.state_for("orb-2") == ADAPTIVE_STATE_RECOVERING


# ── El corte se traduce en evidencia medida con los fills del tick ──────────────────


@pytest.mark.asyncio
async def test_a_reactivated_version_is_declared_recovering_at_the_first_step() -> None:
    """Vuelve por la rampa, no de golpe: el primer escalón (0.25) es TECHO del reparto."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 1)}), reactivated=_reactivated("orb-1")
    )

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.state_for("orb-1") == ADAPTIVE_STATE_RECOVERING
    reading = plan.recovery_for("orb-1")
    assert reading is not None
    assert reading.step == pytest.approx(0.25)
    assert reading.evidence_cycles == 1, "un ciclo positivo medido tras el corte ya se declara"
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_a_completed_ramp_returns_the_version_to_active_at_full_weight() -> None:
    """El techo (1.00) es recuperación CUMPLIDA: la versión vuelve a ``active`` sin recorte."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 12)}), reactivated=_reactivated("orb-1")
    )

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    reading = plan.recovery_for("orb-1")
    assert reading is not None and reading.step == pytest.approx(1.0)
    assert plan.state_for("orb-1") == ADAPTIVE_STATE_ACTIVE
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_the_ramp_climbs_with_the_ticks_own_measured_evidence() -> None:
    """Tres ciclos positivos por escalón: con el material del tick, 0.25 → 0.50."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 3)}), reactivated=_reactivated("orb-1")
    )

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    reading = plan.recovery_for("orb-1")
    assert reading is not None
    assert reading.evidence_cycles == 3
    assert reading.step == pytest.approx(0.50)
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(0.50)


@pytest.mark.asyncio
async def test_the_ramp_adds_no_read_and_does_not_touch_the_rotation() -> None:
    """La rampa reusa los fills y la confianza del tick: una lectura por versión, ni una más."""
    store = _FillStore({"orb-1": _profitable("orb-1", 2)})
    worker = _worker(store=store, reactivated=_reactivated("orb-1"))

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert store.calls == ["orb-1"]
    assert not plan.rotation.is_paused("orb-1"), "la rampa no pausa: eso es de la rotación"
    assert plan.as_dict()["readOnly"] is True


@pytest.mark.asyncio
async def test_the_ramp_is_a_ceiling_and_never_widens_the_allocation() -> None:
    """Dos versiones: la que vuelve queda topada y la otra conserva su reparto exacto."""
    fills = {"thin": _profitable("thin", 2), "broad": _profitable("broad", 180)}
    without = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad"}, "TREND_UP"
    )
    with_ramp = await _worker(
        store=_FillStore(fills), reactivated=_reactivated("thin")
    )._v2_build_adaptive_plan({"thin", "broad"}, "TREND_UP")

    assert without is not None and with_ramp is not None
    assert with_ramp.risk_multiplier_for("broad") == without.risk_multiplier_for("broad"), (
        "el techo solo topa a la que vuelve: no redistribuye a las demás"
    )
    assert with_ramp.risk_multiplier_for("thin") == pytest.approx(0.25)
    assert with_ramp.risk_multiplier_for("thin") < without.risk_multiplier_for("thin")
    for version in ("thin", "broad"):
        assert 0.0 < with_ramp.risk_multiplier_for(version) <= 1.0


# ── La evidencia durable conserva su forma (aditivo, sin migración) ─────────────────


@pytest.mark.asyncio
async def test_the_published_evidence_keeps_its_declared_frame() -> None:
    """El estado operativo y la rampa van en campos PROPIOS: la forma de rotación no se toca."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 2)}), reactivated=_reactivated("orb-1")
    )

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    payload = plan.as_dict()
    assert set(payload["rotation"]) == {"paused", "byStrategy"}
    assert set(payload["allocation"]) == {"riskMultipliers", "evidenceAxis"}
    assert payload["operationalStates"] == {"orb-1": ADAPTIVE_STATE_RECOVERING}
    assert payload["recovery"]["orb-1"]["step"] == pytest.approx(0.25)
    assert payload["policyVersion"] == "auto17-v1"


@pytest.mark.asyncio
async def test_the_journal_entry_still_builds_with_a_ramp_present() -> None:
    """La rampa no cambia el contrato del journal: la fila sigue construyéndose y escribiéndose."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 2)}), reactivated=_reactivated("orb-1")
    )
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")
    assert plan is not None

    class _Journal:
        def __init__(self) -> None:
            self.entries: list[Any] = []

        async def sink(self, entry: Any) -> None:
            self.entries.append(entry)

    journal = _Journal()
    worker._adaptive_sink = journal.sink
    await worker._v2_journal_adaptive_recommendation(plan)

    assert len(journal.entries) == 1
    entry = journal.entries[0]
    assert entry.payload["rotation"]["paused"] == []
    assert worker._v2_adaptive_sink_failures == 0


# ── La memoria derivada: sembrada del journal y completada por el proceso ───────────


def _reader(reading: AdaptiveStateReading) -> Any:
    async def _read(_account_id: str) -> AdaptiveStateReading:
        return reading

    return _read


@pytest.mark.asyncio
async def test_the_durable_reading_seeds_the_ramp_memory_at_startup() -> None:
    """El corte sobrevive al reinicio: el lector durable siembra la memoria de la rampa."""
    worker = _worker(store=None)
    worker._v2_adaptive_state_recovered = False
    worker._adaptive_reader = _reader(AdaptiveStateReading(reactivated_at={"orb-1": _CUT}))

    await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_reactivated_at == {"orb-1": _CUT}


@pytest.mark.asyncio
async def test_a_journal_that_cannot_be_read_seeds_no_ramp() -> None:
    """``read_ok=False`` no puede fingir una reincorporación fechada: la memoria queda vacía."""
    worker = _worker(store=None)
    worker._v2_adaptive_state_recovered = False
    worker._adaptive_reader = _reader(adaptive_state_unread("reader_failed"))

    await worker._v2_recover_adaptive_state()

    assert worker._v2_adaptive_reactivated_at == {}


@pytest.mark.asyncio
async def test_a_version_that_leaves_its_pause_is_dated_in_the_same_tick() -> None:
    """No hay tick a peso pleno: la transición observada entra en la rampa YA, con el suelo."""
    worker = _worker(store=_FillStore({"orb-1": _profitable("orb-1", 1)}))
    worker._v2_adaptive_paused_cycles = {"orb-1": 5}

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert not plan.rotation.is_paused("orb-1"), "el cooldown cumplido reactiva la versión"
    assert worker._v2_adaptive_reactivated_at == {"orb-1": _AS_OF}
    assert plan.state_for("orb-1") == ADAPTIVE_STATE_RECOVERING
    assert plan.risk_multiplier_for("orb-1") == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_a_version_that_never_paused_is_never_dated() -> None:
    """Sin pausa previa no hay transición que fechar: el proceso no inventa una reincorporación."""
    worker = _worker(store=_FillStore({"orb-1": _profitable("orb-1", 1)}))

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert worker._v2_adaptive_reactivated_at == {}
    assert plan.state_for("orb-1") == ADAPTIVE_STATE_ACTIVE


@pytest.mark.asyncio
async def test_returning_to_a_pause_forgets_the_date_until_the_next_reactivation() -> None:
    """§24: si la evidencia devuelve a pausa, el escalón se DESCARTA y el corte se olvida."""
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 12)}), reactivated=_reactivated("orb-1")
    )
    await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")
    assert worker._v2_adaptive_reactivated_at == {"orb-1": _CUT}

    # La evidencia se deteriora probadamente: la rotación la pausa y el corte se olvida.
    worker._context_store = _FillStore({"orb-1": _losing("orb-1", 12)})
    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert plan.rotation.is_paused("orb-1")
    assert worker._v2_adaptive_reactivated_at == {}
    assert plan.recovery == {}
