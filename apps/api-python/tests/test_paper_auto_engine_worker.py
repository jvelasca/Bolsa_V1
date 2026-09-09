"""V2.21 / A8 (M4) — PaperAutoEngineWorker SAFE/dry: telemetría + gates.

No ejecuta dinero por sí (diseño SAFE). Cubrimos: transición de estado,
telemetría solo-lectura, kill switch → BLOCKED, venue no-AUTO →
REQUIRES_ATTENTION, guard de enable (off → sin task), y determinismo del gate.
"""

from __future__ import annotations

import asyncio

import pytest
from bolsa_application.risk_runtime import (
    clear_idempotency_memory_for_tests,
    set_runtime_kill_switch_memory,
)

from bolsa_api.background import paper_auto_engine_worker as w


@pytest.fixture(autouse=True)
def _reset_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_DRY_VENUE", raising=False)
    monkeypatch.delenv("AUTO_ENGINE_DRY_WATCH", raising=False)
    monkeypatch.delenv(w._ENV_ENABLED, raising=False)
    monkeypatch.delenv(w._ENV_INTERVAL, raising=False)
    set_runtime_kill_switch_memory(False)
    clear_idempotency_memory_for_tests()


def test_engine_starts_paused_then_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_DRY_VENUE", "paper")
    monkeypatch.setenv("AUTO_ENGINE_DRY_WATCH", "AAA")
    eng = w.PaperAutoEngine()
    assert eng.telemetry()["state"] == "PAUSED"
    eng.run_tick()
    tel = eng.telemetry()
    assert tel["state"] == "RUNNING"
    assert tel["lastTick"] is not None
    # SAFE/dry: las propuestas HOLD pasan el gate, nada ejecuta dinero.
    assert isinstance(tel["dryProposals"], int)


def test_kill_switch_blocks_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_DRY_WATCH", "AAA")
    set_runtime_kill_switch_memory(True)
    eng = w.PaperAutoEngine()
    eng.run_tick()
    tel = eng.telemetry()
    assert tel["state"] == "BLOCKED"
    assert "kill_switch_active" in str(tel["lastReason"])


def test_non_auto_venue_requires_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_DRY_VENUE", "live")
    eng = w.PaperAutoEngine()
    eng.run_tick()
    assert eng.telemetry()["state"] == "REQUIRES_ATTENTION"


def test_dry_tick_deterministic_gate() -> None:
    rep = w.dry_tick(watch=["AAA", "IBEX"], kill_switch=False, venue="paper")
    assert rep.proposals == 2
    assert rep.vetoes == 0
    rep2 = w.dry_tick(watch=["AAA", "IBEX"], kill_switch=True, venue="paper")
    assert rep2.proposals == 0
    assert rep2.vetoes == 2


def test_m3_buy_decider_yields_pending_sim_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """A9/M3: un proveedor (ia) que sugiere BUY produce candidato a ExecutionPlan
    SIM-ONLY a través del RiskGate; el motor no HOLD-único. HOLD default intacto."""
    from bolsa_application.decision_contract import DecisionPackage

    def buy_decider(sym: str) -> DecisionPackage:
        return DecisionPackage(
            action="BUY",
            instrument_id=sym,
            quantity=1.0,
            source="test_m3_ia",
        )

    monkeypatch.setenv("AUTO_ENGINE_DRY_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_DRY_WATCH", "AAA")
    # dry_tick directo: decider BUY en sim → propuesta + plan pendiente.
    rep = w.dry_tick(
        watch=["AAA"],
        kill_switch=False,
        venue="simulated",
        decider=buy_decider,
    )
    assert rep.proposals == 1
    assert rep.pending_plans == 1
    assert rep.vetoes == 0

    # En run_tick (telemetría del motor) pendiente suma.
    eng = w.PaperAutoEngine(decider=buy_decider)
    eng.run_tick()
    tel = eng.telemetry()
    assert tel["state"] == "RUNNING"
    assert tel["pendingPlans"] >= 1

    # Venue LIVE jamás emite plan (gate tercero / venue AUto-Restringido).
    rep_live = w.dry_tick(
        watch=["AAA"],
        kill_switch=False,
        venue="live",
        decider=buy_decider,
    )
    assert rep_live.pending_plans == 0
    assert rep_live.proposals == 0


def test_m3_default_engine_still_hold_pending_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """A9/M3: sin decider sigue HOLD-safe (0 planes)."""
    monkeypatch.setenv("AUTO_ENGINE_DRY_VENUE", "paper")
    monkeypatch.setenv("AUTO_ENGINE_DRY_WATCH", "AAA")
    eng = w.PaperAutoEngine()
    eng.run_tick()
    assert eng.telemetry()["pendingPlans"] == 0


def test_start_gated_off_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w._ENV_ENABLED, "0")
    assert w.start_paper_auto_engine_worker() is None


def test_start_returns_task_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w._ENV_ENABLED, "1")
    monkeypatch.setenv(w._ENV_INTERVAL, "3600")

    async def _scenario() -> bool:
        eng = w.PaperAutoEngine()
        task = w.start_paper_auto_engine_worker(engine=eng)
        assert task is not None and isinstance(task, asyncio.Task)
        task.cancel()
        return True

    assert asyncio.run(_scenario()) is True
