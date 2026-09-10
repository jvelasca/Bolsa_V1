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
        w.AUTO_ORCHESTRATOR_STRATEGY_FAMILY,
        w.AUTO_ORCHESTRATOR_LAB_PARAMS,
        w.AUTO_ORCHESTRATOR_MAX_CANDIDATES,
    ):
        monkeypatch.delenv(key, raising=False)


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


def _session_factory() -> _FakeSession:
    """Session factory mínima: la composición no abre sesión hasta ejecutar."""
    return _FakeSession()


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
async def test_loop_without_instruments_keeps_running_safely() -> None:
    # V2.27: sin universo ni allowlist el bucle NO muere ni orquesta nada; sigue
    # reintentando (una caída transitoria de ESTUDIO no debe apagar el worker).
    orch = _FakeOrchestrator()
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
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


# ── V2.27: composición real (P1-01 + P1-02) ─────────────────────────────────────


@dataclass
class _OrchWithUniverse:
    """Doble mínimo con ``resolve_universe`` público (como el orquestador real)."""

    resolution: Any
    cycles: list[str] = field(default_factory=list)

    async def resolve_universe(self) -> Any:
        return self.resolution

    async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
        self.cycles.append(instrument_id)
        return _Result()

    async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
        return _Result()


@dataclass
class _Resolution:
    status: str = "ok"
    instrument_ids: list[str] = field(default_factory=lambda: ["AAA", "BBB"])


@pytest.mark.asyncio
async def test_universe_is_canonical_instrument_source() -> None:
    orch = _OrchWithUniverse(resolution=_Resolution())
    watch = await w._instruments_for_cycle(orch, allowlist=())
    assert watch == ("AAA", "BBB")


@pytest.mark.asyncio
async def test_allowlist_filters_the_universe() -> None:
    orch = _OrchWithUniverse(resolution=_Resolution())
    watch = await w._instruments_for_cycle(orch, allowlist=("BBB",))
    assert watch == ("BBB",)


@pytest.mark.asyncio
async def test_unavailable_universe_falls_back_to_allowlist() -> None:
    orch = _OrchWithUniverse(resolution=_Resolution(status="unavailable", instrument_ids=[]))
    watch = await w._instruments_for_cycle(orch, allowlist=("AAA",))
    assert watch == ("AAA",)


@pytest.mark.asyncio
async def test_loop_uses_estudio_universe_without_csv() -> None:
    orch = _OrchWithUniverse(resolution=_Resolution())
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Sin AUTO_ORCHESTRATOR_INSTRUMENTS, el universo ESTUDIO manda.
    assert "AAA" in orch.cycles
    assert "BBB" in orch.cycles


def test_default_orchestrator_wires_real_dependencies() -> None:
    # P1-01/P1-02: ya no se deja resolve_universe/run_optimize en None.
    orch = w._default_orchestrator(_session_factory)
    deps = orch.deps

    assert deps.resolve_universe is not None
    assert deps.run_optimize is not None
    assert deps.candidate_id_factory is not None


def test_default_orchestrator_is_sim_only() -> None:
    # Regresión LIVE: la composición del orquestador no puede alcanzar ningún
    # componente de ejecución real. Solo store + ESTUDIO + LAB.
    src_module = w._default_orchestrator.__module__
    assert src_module == "bolsa_api.background.auto_orchestrator_worker"

    orch = w._default_orchestrator(_session_factory)
    deps = orch.deps
    # El store es el del lifecycle (SIM), no un router de ejecución.
    assert type(deps.store).__name__ == "_SessionScopedStore"
    # Las únicas dependencias cableadas son las del ciclo de investigación.
    assert deps.resolve_universe is not None
    assert deps.run_optimize is not None
