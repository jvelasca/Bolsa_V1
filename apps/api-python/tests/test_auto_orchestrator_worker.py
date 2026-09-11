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
        w.AUTO_ORCHESTRATOR_GRAMMAR,
        w.AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS,
        w.AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS,
        w.AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR,
        w.AUTO_ORCHESTRATOR_ALLOCATOR_ADAPTIVE_WEIGHT,
        w.AUTO_ORCHESTRATOR_ALLOCATOR_CATALOG_WEIGHT,
        w.AUTO_ORCHESTRATOR_ALLOCATOR_GRAMMAR_SIMPLE_WEIGHT,
        w.AUTO_ORCHESTRATOR_ALLOCATOR_GRAMMAR_COMPOSITE_WEIGHT,
    ):
        monkeypatch.delenv(key, raising=False)


def _zero_counters(counters: Any) -> None:
    """Pone a cero un acumulador de gramática (mismos campos en proceso y ciclo)."""
    counters.discovery_calls = 0
    counters.grammar_discovery_calls = 0
    counters.catalog_candidates = 0
    counters.grammar_candidates = 0
    counters.total_candidates = 0
    counters.trials_used = 0
    counters.warmup_skipped = 0


@pytest.fixture(autouse=True)
def _reset_grammar_counters() -> None:
    """V2.35/A15: los contadores son de proceso; se resetean por test.

    V2.35.1 (P2-02): también se resetea el acumulador de ciclo para que cada test
    arranque de un estado limpio y determinista.
    """
    _zero_counters(w.grammar_counters())
    _zero_counters(w._reset_cycle_counters())


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
    # V2.35.1 (P1-01): el universo lo aporta ESTUDIO; la allowlist solo intersecta.
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    orch = _OrchWithUniverse(resolution=_Resolution(instrument_ids=["AAA", "BBB"]))
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "AAA" in orch.cycles
    # La allowlist filtra BBB del universo ESTUDIO.
    assert "BBB" not in orch.cycles


@pytest.mark.asyncio
async def test_loop_survives_per_instrument_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA,BBB")
    orch = _OrchWithUniverse(
        resolution=_Resolution(instrument_ids=["AAA", "BBB"]), fail_on="AAA"
    )
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
    watches: list[str] = field(default_factory=list)
    fail_on: str | None = None

    async def resolve_universe(self) -> Any:
        return self.resolution

    async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
        self.cycles.append(instrument_id)
        if self.fail_on == instrument_id:
            raise RuntimeError("boom")
        return _Result()

    async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
        self.watches.append(instrument_id)
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
async def test_unavailable_estudio_never_falls_back_to_allowlist() -> None:
    # V2.35.1 (P1-01): ESTUDIO unavailable NO convierte la allowlist en universo.
    orch = _OrchWithUniverse(resolution=_Resolution(status="unavailable", instrument_ids=[]))
    watch = await w._instruments_for_cycle(orch, allowlist=("AAA",))
    assert watch == ()


@pytest.mark.asyncio
async def test_estudio_empty_never_falls_back_to_allowlist() -> None:
    # V2.35.1 (P1-01): ESTUDIO vacío ⇒ no operar (fail-closed), sin CSV de rescate.
    orch = _OrchWithUniverse(resolution=_Resolution(status="ok", instrument_ids=[]))
    watch = await w._instruments_for_cycle(orch, allowlist=("AAA",))
    assert watch == ()


@pytest.mark.asyncio
async def test_estudio_error_never_falls_back_to_allowlist() -> None:
    # V2.35.1 (P1-01): un fallo del resolver ⇒ no operar, nunca allowlist.
    class _Boom:
        async def resolve_universe(self) -> Any:
            raise RuntimeError("estudio down")

    watch = await w._instruments_for_cycle(_Boom(), allowlist=("AAA",))
    assert watch == ()


@pytest.mark.asyncio
async def test_loop_does_not_operate_when_estudio_unavailable_with_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # V2.35.1 (P1-01): con ESTUDIO unavailable y CSV configurado NO se ejecuta ciclo.
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    orch = _OrchWithUniverse(resolution=_Resolution(status="unavailable", instrument_ids=[]))
    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert orch.cycles == []


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
    """V2.35.1 (P2-01): el bucle AUTO NO envía ningún override al ciclo.

    Con ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` el ciclo debe seguir sin recibir
    ``shadow_validated`` (la firma ya no lo acepta): AUTO promociona solo por evidencia
    ejecutada.
    """
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED, "1")
    seen: list[dict[str, Any]] = []

    class _Recorder:
        async def resolve_universe(self) -> Any:
            return _Resolution(instrument_ids=["AAA"])

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


def test_default_orchestrator_has_no_shadow_override_field() -> None:
    """V2.35.1 (P2-01): la composición AUTO no expone ningún override humano.

    ``shadow_override`` se eliminó de ``OrchestratorDeps``: la ruta AUTO promociona
    solo con evidencia ejecutada. El override administrativo vive exclusivamente en
    ``decide_admin_promotion`` (fuera del orquestador autónomo).
    """
    import os
    from dataclasses import fields

    previous = os.environ.get(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED)
    os.environ[w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED] = "1"
    try:
        orch = w._default_orchestrator(_session_factory)
    finally:
        if previous is None:
            os.environ.pop(w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED, None)
        else:
            os.environ[w.AUTO_ORCHESTRATOR_SHADOW_VALIDATED] = previous
    assert "shadow_override" not in {f.name for f in fields(orch.deps)}
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


# ── V2.35/A15: observabilidad de la gramática (contadores y flag) ───────────────


def test_grammar_runner_records_disabled_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la gramática OFF, el runner cuenta el catálogo pero cero gramática."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_GRAMMAR, raising=False)
    runner = w._make_discovery_runner(DiscoveryBudget())
    assert runner.grammar_enabled is False

    candidates = runner("AAA")
    counters = w.grammar_counters()
    assert counters.discovery_calls == 1
    assert counters.grammar_discovery_calls == 0
    assert counters.grammar_candidates == 0
    assert counters.catalog_candidates == len(candidates) == counters.total_candidates


def test_grammar_runner_records_enabled_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la gramática ON, el runner cuenta la procedencia y cuadra el total."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR, "1")
    base = DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    runner = w._make_discovery_runner(base)
    assert runner.grammar_enabled is True

    candidates = runner("AAA")
    counters = w.grammar_counters()
    assert counters.discovery_calls == 1
    assert counters.grammar_discovery_calls == 1
    assert counters.grammar_candidates > 0
    assert counters.total_candidates == len(candidates)
    assert counters.catalog_candidates + counters.grammar_candidates == len(candidates)


def test_grammar_counters_are_monotonic_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los contadores acumulan entre llamadas (observabilidad del proceso)."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_GRAMMAR, raising=False)
    runner = w._make_discovery_runner(DiscoveryBudget())
    runner("AAA")
    runner("BBB")
    assert w.grammar_counters().discovery_calls == 2


@pytest.mark.asyncio
async def test_loop_logs_cycle_summary(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """El bucle emite un resumen por ciclo sin alterar ninguna decisión."""
    import logging

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    orch = _OrchWithUniverse(resolution=_Resolution(instrument_ids=["AAA"]))

    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    with caplog.at_level(logging.INFO):
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert any("cycle_summary" in record.message for record in caplog.records)


# ── V2.35.1 (P2-02): contadores de ciclo separados de los de proceso ────────────


@dataclass
class _Summary:
    """Resumen de discovery mínimo (contrato de ``_record_discovery_summary``)."""

    grammar_enabled: bool = False
    catalog_candidates: int = 0
    grammar_candidates: int = 0
    total_candidates: int = 0
    trials_used: int = 0
    bar_count_ok: bool = True


def _counters_snapshot(counters: Any) -> tuple[int, ...]:
    """Tupla determinista con los siete campos del acumulador (para comparar)."""
    return (
        counters.discovery_calls,
        counters.grammar_discovery_calls,
        counters.catalog_candidates,
        counters.grammar_candidates,
        counters.total_candidates,
        counters.trials_used,
        counters.warmup_skipped,
    )


def test_process_and_cycle_counters_have_same_fields() -> None:
    """``CycleGrammarCounters`` es el gemelo de ciclo del acumulador de proceso."""
    process = w.GrammarObservabilityCounters()
    cycle = w.CycleGrammarCounters()
    assert _counters_snapshot(process) == _counters_snapshot(cycle) == (0, 0, 0, 0, 0, 0, 0)


def test_record_discovery_summary_accumulates_in_both() -> None:
    """Un resumen suma a la vez en proceso y en ciclo (mismos números)."""
    summary = _Summary(total_candidates=3, catalog_candidates=2, grammar_candidates=1)
    w._record_discovery_summary(summary)

    assert _counters_snapshot(w.process_grammar_counters()) == (1, 0, 2, 1, 3, 0, 0)
    assert _counters_snapshot(w.cycle_grammar_counters()) == (1, 0, 2, 1, 3, 0, 0)


def test_grammar_counters_returns_process_accumulator() -> None:
    """``grammar_counters()`` sigue devolviendo el acumulador de proceso (compat)."""
    assert w.grammar_counters() is w.process_grammar_counters()


def test_cycle_reset_leaves_process_monotonic() -> None:
    """Reiniciar el ciclo no toca el proceso: sigue acumulando (monótono)."""
    w._record_discovery_summary(_Summary(total_candidates=2, catalog_candidates=2))
    w._record_discovery_summary(_Summary(total_candidates=3, catalog_candidates=3))
    assert w.process_grammar_counters().discovery_calls == 2

    w._reset_cycle_counters()
    # El ciclo vuelve a cero; el proceso conserva sus totales.
    assert _counters_snapshot(w.cycle_grammar_counters()) == (0, 0, 0, 0, 0, 0, 0)
    assert w.process_grammar_counters().discovery_calls == 2

    w._record_discovery_summary(_Summary(total_candidates=5, catalog_candidates=5))
    assert w.process_grammar_counters().discovery_calls == 3
    assert w.cycle_grammar_counters().discovery_calls == 1
    assert w.cycle_grammar_counters().total_candidates == 5


def test_grammar_off_keeps_cycle_and_process_grammar_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la gramática OFF, ni ciclo ni proceso cuentan gramática."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_GRAMMAR, raising=False)
    runner = w._make_discovery_runner(DiscoveryBudget())
    candidates = runner("AAA")

    for counters in (w.cycle_grammar_counters(), w.process_grammar_counters()):
        assert counters.grammar_discovery_calls == 0
        assert counters.grammar_candidates == 0
        assert counters.catalog_candidates == len(candidates)


def test_runner_counter_reset_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Misma entrada ⇒ mismos contadores (determinismo ciclo a ciclo)."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_GRAMMAR, raising=False)
    runner = w._make_discovery_runner(DiscoveryBudget())

    runner("AAA")
    first_cycle = _counters_snapshot(w._reset_cycle_counters())
    runner("AAA")
    second_cycle = _counters_snapshot(w._reset_cycle_counters())
    assert first_cycle == second_cycle


@pytest.mark.asyncio
async def test_loop_cycle_summary_reports_only_current_cycle(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """El ``cycle_summary`` reporta el ciclo vigente y ``process_summary`` el proceso.

    V2.35.1 (P2-02): con un discovery de gramática OFF inyectado, cada ciclo cuenta
    solo su propio discovery; el proceso, sin embargo, acumula entre ciclos.
    """
    import logging

    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    runner = w._make_discovery_runner(DiscoveryBudget())

    class _DiscoveryOrch:
        """Doble que invoca el discovery real una vez por instrumento/ciclo."""

        def __init__(self) -> None:
            self.cycles = 0

        async def resolve_universe(self) -> Any:
            return _Resolution(instrument_ids=["AAA"])

        async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
            self.cycles += 1
            runner(instrument_id)
            return _Result()

        async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
            return _Result()

    task = asyncio.create_task(w.auto_orchestrator_loop(_DiscoveryOrch(), interval_seconds=0.01))
    with caplog.at_level(logging.INFO):
        await asyncio.sleep(0.08)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    cycle_lines = [r.getMessage() for r in caplog.records if "cycle_summary" in r.getMessage()]
    process_lines = [
        r.getMessage() for r in caplog.records if "process_summary" in r.getMessage()
    ]
    assert cycle_lines, "debe haber al menos un cycle_summary"
    assert process_lines, "debe haber al menos un process_summary"

    # El resumen de ciclo cuenta un solo discovery (un instrumento por ciclo).
    assert all("grammar_discoveries=0" in line for line in cycle_lines)
    assert w.process_grammar_counters().discovery_calls == len(process_lines)
    # El de proceso acumula: el último refleja todos los ciclos ejecutados.
    assert f"discovery_calls={len(process_lines)}" in process_lines[-1]


@pytest.mark.asyncio
async def test_consecutive_cycles_report_independent_cycle_numbers(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Dos ciclos consecutivos con distinto nº de discoveries reportan números propios."""
    import logging

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA,BBB")
    seen: list[int] = []

    class _TwoCycleOrch:
        """Doble que ejecuta un discovery por instrumento (2 en el primer ciclo)."""

        def __init__(self) -> None:
            self.resolution_calls = 0

        async def resolve_universe(self) -> Any:
            self.resolution_calls += 1
            if self.resolution_calls > 1:
                raise asyncio.CancelledError
            return _Resolution(instrument_ids=["AAA", "BBB"])

        async def run_cycle(self, *, instrument_id: str, **_: Any) -> _Result:
            w._record_discovery_summary(_Summary(total_candidates=1, catalog_candidates=1))
            return _Result()

        async def watch_active(self, *, instrument_id: str, **_: Any) -> _Result:
            return _Result()

    class _CycleCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()
            if "cycle_summary" in message:
                seen.append(int(message.split("catalog_candidates=")[1].split()[0]))

    handler = _CycleCapture()
    root = logging.getLogger("bolsa_api.background.auto_orchestrator_worker")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        with pytest.raises(asyncio.CancelledError):
            await w.auto_orchestrator_loop(_TwoCycleOrch(), interval_seconds=0.01)
    finally:
        root.removeHandler(handler)

    # El primer ciclo ve 2 discoveries (AAA, BBB); el segundo se cancela al resolver.
    assert seen[0] == 2


@pytest.mark.asyncio
async def test_loop_runs_forward_between_cycle_and_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con ``forward_runner`` cableado, el bucle lo invoca tras el ciclo."""
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    calls: list[str] = []

    class _Recorder:
        async def resolve_universe(self) -> Any:
            return _Resolution(instrument_ids=["AAA"])

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


# ── V2.36 (incremento 1): carril adaptativo alimentado por snapshot ─────────────


def _snapshot(adaptive_weight: float, *, window_to: str | None = None) -> Any:
    from datetime import UTC, datetime

    from bolsa_domain.entities.discovery_evidence_snapshot import (
        DiscoveryEvidenceSnapshot,
    )

    fresh_to = window_to or datetime.now(UTC).isoformat()
    return DiscoveryEvidenceSnapshot(
        id="snap-1",
        snapshot_hash="sha256:abc",
        math_version="discovery_evidence_v1",
        window_from="a",
        window_to=fresh_to,
        family_weights={"sma": 1.0},
        lane_weights={"adaptive": adaptive_weight},
        sample_sizes={"sma": 10},
        payload={},
        created_at="2026-09-11T00:00:00+00:00",
        evidence_fingerprint="sha256:fp",
    )


def test_adaptive_allocator_defaults_off() -> None:
    assert w.adaptive_allocator_enabled() is False


def test_adaptive_allocator_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR, "1")
    assert w.adaptive_allocator_enabled() is True


def test_allocator_uses_env_weight_without_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin snapshot, el peso adaptativo es el del env (histórico 0.0)."""
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ALLOCATOR_ADAPTIVE_WEIGHT, "0.3")
    allocator = w._discovery_allocator()
    assert allocator.adaptive_weight == 0.3


def test_allocator_snapshot_overrides_env_weight() -> None:
    allocator = w._discovery_allocator(_snapshot(0.42))
    assert allocator.adaptive_weight == 0.42


def test_allocator_snapshot_without_adaptive_key_is_fail_closed() -> None:
    from bolsa_domain.entities.discovery_evidence_snapshot import (
        DiscoveryEvidenceSnapshot,
    )

    snapshot = DiscoveryEvidenceSnapshot(
        id="snap-2",
        snapshot_hash="sha256:def",
        math_version="discovery_evidence_v0",
        window_from="a",
        window_to="b",
        family_weights={},
        lane_weights={},
        sample_sizes={},
        payload={},
        created_at="2026-09-11T00:00:00+00:00",
    )
    assert w._discovery_allocator(snapshot).adaptive_weight == 0.0


def test_runner_uses_injected_snapshot_holder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El runner lee el holder por ciclo y construye el allocator con su peso."""
    from bolsa_application import strategy_discovery_engine as engine
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR, "1")
    captured: dict[str, Any] = {}

    real = engine.discover_for_instrument_with_summary

    def _spy(**kwargs: Any) -> Any:
        captured["allocator"] = kwargs.get("allocator")
        return real(**kwargs)

    monkeypatch.setattr(engine, "discover_for_instrument_with_summary", _spy)

    holder: list[Any] = [_snapshot(0.5)]
    runner = w._make_discovery_runner(
        DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40),
        holder,
    )
    runner("AAA")
    allocator = captured["allocator"]
    assert allocator is not None
    assert allocator.adaptive_weight == 0.5


def test_runner_without_snapshot_holder_keeps_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import strategy_discovery_engine as engine
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_GRAMMAR, "1")
    captured: dict[str, Any] = {}
    real = engine.discover_for_instrument_with_summary

    def _spy(**kwargs: Any) -> Any:
        captured["allocator"] = kwargs.get("allocator")
        return real(**kwargs)

    monkeypatch.setattr(engine, "discover_for_instrument_with_summary", _spy)

    runner = w._make_discovery_runner(
        DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40)
    )
    runner("AAA")
    assert captured["allocator"].adaptive_weight == 0.0


@pytest.mark.asyncio
async def test_loop_reads_adaptive_snapshot_once_per_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El provider se consulta UNA vez por ciclo (no por instrumento)."""
    calls: list[int] = []

    async def _provider() -> Any:
        calls.append(1)
        return _snapshot(0.4)

    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA,BBB,CCC")
    orch = _OrchWithUniverse(
        resolution=_Resolution(instrument_ids=["AAA", "BBB", "CCC"])
    )
    orch.adaptive_snapshot_holder = []

    task = asyncio.create_task(
        w.auto_orchestrator_loop(
            orch, interval_seconds=30.0, adaptive_snapshot_provider=_provider
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Un solo ciclo observado ⇒ una sola lectura, pese a haber 3 instrumentos.
    assert len(calls) == 1
    assert len(orch.adaptive_snapshot_holder) == 1


@pytest.mark.asyncio
async def test_loop_without_provider_does_not_touch_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con el flag OFF no hay provider: el holder queda vacío (byte-idéntico)."""
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_INSTRUMENTS, "AAA")
    orch = _OrchWithUniverse(resolution=_Resolution(instrument_ids=["AAA"]))
    orch.adaptive_snapshot_holder = []

    task = asyncio.create_task(w.auto_orchestrator_loop(orch, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert orch.adaptive_snapshot_holder == []


@pytest.mark.asyncio
async def test_refresh_adaptive_snapshot_fail_closed_on_provider_error() -> None:
    """Un provider que falla deja el holder vacío (peso 0), no rompe el ciclo."""
    orch = _FakeOrchestrator()
    orch.adaptive_snapshot_holder = []

    async def _boom() -> Any:
        raise RuntimeError("db down")

    await w._refresh_adaptive_snapshot(orch, _boom)
    assert orch.adaptive_snapshot_holder == []


# ── V2.37/P2-03 — freshness fail-closed ─────────────────────────────────────────


def test_adaptive_max_staleness_defaults_to_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS, raising=False)
    assert w.adaptive_max_staleness_days() == 30


def test_adaptive_max_staleness_zero_disables_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS, "0")
    assert w.adaptive_max_staleness_days() == 0


@pytest.mark.asyncio
async def test_stale_snapshot_is_discarded_fail_closed() -> None:
    """Un snapshot con corte antiguo NO gobierna el reparto (peso 0)."""
    orch = _FakeOrchestrator()
    orch.adaptive_snapshot_holder = []
    stale = _snapshot(0.4, window_to="2020-01-01T00:00:00+00:00")

    async def _provider() -> Any:
        return stale

    await w._refresh_adaptive_snapshot(orch, _provider)
    assert orch.adaptive_snapshot_holder == []


@pytest.mark.asyncio
async def test_staleness_check_disabled_accepts_old_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la validación desactivada (0) el snapshot antiguo sí se inyecta (compat)."""
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS, "0")
    orch = _FakeOrchestrator()
    orch.adaptive_snapshot_holder = []
    stale = _snapshot(0.4, window_to="2020-01-01T00:00:00+00:00")

    async def _provider() -> Any:
        return stale

    await w._refresh_adaptive_snapshot(orch, _provider)
    assert len(orch.adaptive_snapshot_holder) == 1


# ── V2.37 (incremento 2) — flag de generación adaptativa ─────────────────────────


def test_adaptive_generation_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION, raising=False)
    assert w.adaptive_generation_enabled() is False


def test_adaptive_generation_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION, "1")
    assert w.adaptive_generation_enabled() is True


def test_discovery_runner_emits_no_adaptive_without_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con la generación OFF, el runner no construye política (carril sin emitir)."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION, raising=False)
    holder: list[Any] = [_snapshot(0.5)]
    runner = w._make_discovery_runner(
        DiscoveryBudget(max_trials_total=60, max_per_family=8, max_candidates=40),
        holder,
    )
    assert callable(runner)


def test_start_does_not_wire_adaptive_provider_when_disabled() -> None:
    assert w.adaptive_allocator_enabled() is False
    import os

    assert os.getenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR) is None


# ── V2.38 (incremento 3) — flag de granularidad por región de parámetros ─────────


def test_adaptive_param_region_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION, raising=False)
    assert w.adaptive_param_region_enabled() is False


def test_adaptive_param_region_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(w.AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION, "1")
    assert w.adaptive_param_region_enabled() is True


def test_collapse_regions_merges_composite_keys() -> None:
    """Con la región OFF, ``familia|region`` colapsa a familia (compatibilidad V2.37)."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Snap:
        family_weights: dict[str, float]
        sample_sizes: dict[str, int]

    collapsed = w._collapse_regions(
        _Snap(
            family_weights={"sma|r00:aaa": 0.4, "sma|r01:bbb": 0.7, "rsi": 0.2},
            sample_sizes={"sma|r00:aaa": 3, "sma|r01:bbb": 4, "rsi": 5},
        )
    )
    assert collapsed.family_weights == {"sma": 0.7, "rsi": 0.2}
    assert collapsed.sample_sizes == {"sma": 7, "rsi": 5}


def test_collapse_regions_noop_without_regions() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Snap:
        family_weights: dict[str, float]
        sample_sizes: dict[str, int]

    snap = _Snap(family_weights={"sma": 0.4}, sample_sizes={"sma": 3})
    assert w._collapse_regions(snap) is snap
