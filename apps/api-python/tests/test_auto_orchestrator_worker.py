"""V2.26 / A10 — worker del Auto Orchestrator (tests herméticos, SIM-only).

Verifica el gate de entorno (default OFF), el parseo de watch/intervalo, el flag de
shadow, y que el bucle refresca el ``DecisionProvider`` del runtime por el seam.
No requiere PG ni red.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_api.background import auto_orchestrator_worker as w


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        w.AUTO_ORCHESTRATOR_ENABLED,
        w.AUTO_ORCHESTRATOR_INSTRUMENTS,
        w.AUTO_ORCHESTRATOR_INTERVAL_SECONDS,
        w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED,
    ):
        monkeypatch.delenv(key, raising=False)


# ── Gate de entorno ─────────────────────────────────────────────────────────────


def test_enabled_defaults_off() -> None:
    assert w.orchestrator_enabled() is False


def test_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ENABLED, "1")
    assert w.orchestrator_enabled() is True


def test_start_returns_none_when_disabled() -> None:
    assert w.start_auto_orchestrator(orchestrator=object()) is None


def test_start_requires_store_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ENABLED, "1")
    # Habilitado pero sin session_factory ni orchestrator ⇒ no arranca (fail-closed).
    assert w.start_auto_orchestrator() is None


def test_watch_and_interval_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, " aaa , BBB ,, ")
    assert w.instrument_watch() == ("aaa", "BBB")
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INTERVAL_SECONDS, "-5")
    assert w._interval_seconds(default=42.0) == 42.0
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INTERVAL_SECONDS, "12.5")
    assert w._interval_seconds() == 12.5


def test_shadow_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    assert w.shadow_validated() is False
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED, "true")
    assert w.shadow_validated() is True


# ── Bucle ───────────────────────────────────────────────────────────────────────


@dataclass
class _Result:
    status: str = "active"
    promoted: bool = False


@dataclass
class _FakeOrchestrator:
    cycles: list[str] = field(default_factory=list)
    watches: list[str] = field(default_factory=list)
    fail_on: str | None = None

    async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
        self.cycles.append(instrument_id)
        if self.fail_on == instrument_id:
            raise RuntimeError("boom")
        return _Result()

    async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
        self.watches.append(instrument_id)
        return _Result()


@pytest.mark.asyncio
async def test_loop_without_watch_returns_immediately() -> None:
    orch = _FakeOrchestrator()
    await asyncio.wait_for(w.auto_orchestrator_loop(orch, interval_seconds=0.01), timeout=1)
    assert orch.cycles == []


@pytest.mark.asyncio
async def test_loop_runs_cycle_and_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    orch = _FakeOrchestrator()
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "AAA" in orch.cycles
    assert "AAA" in orch.watches


@pytest.mark.asyncio
async def test_loop_survives_per_instrument_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA,BBB")
    orch = _FakeOrchestrator(fail_on="AAA")
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # El fallo de AAA no impide que BBB se orqueste.
    assert "BBB" in orch.cycles
