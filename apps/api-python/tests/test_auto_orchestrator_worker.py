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
        w.AUTO_ORCHESTRATOR_FORWARD,
        w.AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS,
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


@pytest.mark.asyncio
async def test_loop_does_not_pass_shadow_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2.32.1 (P2-02): el bucle AUTO NO cablea el override del operador.

    Con ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` el ciclo debe seguir sin recibir
    ``shadow_validated``: AUTO promociona solo por evidencia ejecutada.
    """
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED, "1")
    seen: list[dict[str, Any]] = []

    class _Recorder:
        async def run_cycle(self, *, instrument_id: str, **kwargs: Any) -> _Result:
            seen.append({"instrument_id": instrument_id, **kwargs})
            return _Result()

        async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
            return _Result()

    task = asyncio.create_task(w.auto_orchestrator_loop(_Recorder(), interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert seen, "el bucle debe haber ejecutado ciclos"
    assert all("shadow_validated" not in call for call in seen)


def test_default_orchestrator_does_not_wire_shadow_override() -> None:
    """V2.32.1 (P2-02): la composición AUTO deja ``shadow_override=None`` (sin bypass)."""
    import os

    previous = os.environ.get(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED)
    os.environ[w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED] = "1"
    try:
        orch = w._default_orchestrator(_session_factory)
    finally:
        if previous is None:
            os.environ.pop(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED, None)
        else:
            os.environ[w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED] = previous
    assert orch.deps.shadow_override is None
    # H1: el hold-out estricto es invariante de la ruta; no hay flag de escape en deps.
    assert not hasattr(orch.deps, "shadow_require_holdout")


def test_health_thresholds_are_calibrated() -> None:
    """V2.32.1 (auditoría 2b): el AUTO fija umbrales predictivos reales (no ``None``)."""
    th = w._health_thresholds()
    assert th.min_credibility is not None
    assert th.min_edge is not None


# ── V2.33/A13: forward paper (default OFF, reversible) ───────────────────────────


def test_forward_defaults_off() -> None:
    """El forward es OFF por defecto: sin env no se ejecuta ni persiste."""
    assert w.forward_enabled() is False


def test_forward_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_FORWARD, "1")
    assert w.forward_enabled() is True


def test_forward_window_bars_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    assert w._forward_window_bars() == w._FORWARD_WINDOW_BARS_DEFAULT
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS, "120")
    assert w._forward_window_bars() == 120
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS, "basura")
    assert w._forward_window_bars() == w._FORWARD_WINDOW_BARS_DEFAULT


# ── V2.34/A14: gramática de Discovery (default OFF, reversible) ─────────────────


def test_grammar_defaults_off() -> None:
    """La gramática es OFF por defecto: el discovery queda idéntico a A13."""
    assert w.grammar_enabled() is False


def test_grammar_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR, "1")
    assert w.grammar_enabled() is True


def test_grammar_budget_wraps_discovery_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """El ``GrammarBudget`` envuelve el presupuesto global y respeta el techo de bloques."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    base = DiscoveryBudget(max_trials_total=48, max_per_family=8, max_candidates=24)
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS, "2")
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS, "3")

    budget = w._grammar_budget(base)
    assert budget.base is base
    assert budget.max_components == 2
    assert budget.max_per_component_variant == 3


def test_grammar_budget_caps_excessive_components() -> None:
    """Un valor de env disparatado se acota al techo duro (3) vía ``normalized``."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    budget = w._grammar_budget(DiscoveryBudget())
    assert budget.normalized().max_components <= 3


def test_discovery_runner_includes_grammar_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la gramática ON el runner emite candidatas gramaticales; con OFF no."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    base = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_GRAMMAR, raising=False)
    off_runner = w._make_discovery_runner(base)
    off_candidates = off_runner("AAA")

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR, "1")
    on_runner = w._make_discovery_runner(base)
    on_candidates = on_runner("AAA")

    assert not [
        c for c in off_candidates if str(c.strategy_family).startswith("grammar:")
    ]
    assert [c for c in on_candidates if str(c.strategy_family).startswith("grammar:")]


@pytest.mark.asyncio
async def test_loop_runs_forward_between_cycle_and_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con ``forward_runner`` cableado, el bucle lo invoca tras el ciclo."""
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    calls: list[str] = []

    class _Recorder:
        async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
            calls.append(f"cycle:{instrument_id}")
            return _Result()

        async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
            calls.append(f"watch:{instrument_id}")
            return _Result()

    async def _forward(instrument_id: str) -> None:
        calls.append(f"forward:{instrument_id}")
        return None

    task = asyncio.create_task(
        w.auto_orchestrator_loop(
            _Recorder(), interval_seconds=0.01, forward_runner=_forward
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "forward:AAA" in calls, calls
    assert calls.index("forward:AAA") > calls.index("cycle:AAA"), calls
    assert calls.index("watch:AAA") > calls.index("forward:AAA"), calls


def test_start_does_not_wire_forward_when_disabled() -> None:
    """Sin el gate ON, el arranque no construye un forward runner (idempotente)."""
    import os

    assert w.forward_enabled() is False
    assert os.getenv(w.AUTO_ORCHESTRATOR_FORWARD) is None


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
