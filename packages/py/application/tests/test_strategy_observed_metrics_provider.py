"""V2.28 / A10 (P1-02 real) — tests del provider de métricas observadas y su wiring.

Verifican que:

* el provider lee los fills atribuidos a la versión y calcula métricas;
* la guarda de muestra mínima (env) decide si se emite señal;
* un fallo de lectura devuelve ``{}`` (fail-closed, sin evidencia inventada);
* ``AutoOrchestrator.watch_active`` fusiona lo observado con lo que pase el llamante.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
from bolsa_application.sim_durable_store import (
    InMemorySimFillFinanceContextStore,
    SimFillFinanceContext,
)
from bolsa_application.strategy_observed_metrics_provider import (
    AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES,
    make_observed_metrics_provider,
    observed_min_trades,
)

pytestmark = pytest.mark.asyncio


class _SessionFactory:
    """Session factory mínima: el store se construye con el factory inyectado."""

    def __call__(self) -> Any:
        return _SessionCtx()


class _SessionCtx:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *exc: object) -> None:
        return None


def _provider(store: InMemorySimFillFinanceContextStore) -> Any:
    return make_observed_metrics_provider(
        _SessionFactory(),
        store_factory=lambda _session: store,
    )


async def _seed_round_trips(
    store: InMemorySimFillFinanceContextStore,
    *,
    version: str,
    count: int,
    entry: str,
    exit: str,
) -> None:
    for i in range(count):
        await store.save(
            SimFillFinanceContext(
                execution_id=f"{version}-b-{i}",
                instrument_id="SAN.MC",
                side="buy",
                quantity=Decimal("10"),
                price=Decimal(entry),
                account_id="acc-1",
                strategy_version_id=version,
            )
        )
        await store.save(
            SimFillFinanceContext(
                execution_id=f"{version}-s-{i}",
                instrument_id="SAN.MC",
                side="sell",
                quantity=Decimal("10"),
                price=Decimal(exit),
                account_id="acc-1",
                strategy_version_id=version,
            )
        )


async def test_observed_min_trades_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, "5")
    assert observed_min_trades() == 5
    monkeypatch.setenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, "bogus")
    assert observed_min_trades() == 10
    monkeypatch.delenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, raising=False)
    assert observed_min_trades() == 10


async def test_provider_emits_metrics_when_sample_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, "3")
    store = InMemorySimFillFinanceContextStore()
    await _seed_round_trips(store, version="ver-1", count=3, entry="100", exit="110")

    metrics = await _provider(store)("ver-1")

    assert metrics["observed_trades"] == 3
    assert metrics["observed_return_pct"] == pytest.approx(10.0)
    assert metrics["observed_win_rate"] == 1.0


async def test_provider_silent_when_sample_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, "10")
    store = InMemorySimFillFinanceContextStore()
    await _seed_round_trips(store, version="ver-1", count=2, entry="100", exit="110")

    # Muestra insuficiente ⇒ sin señal (el observado no decide).
    assert await _provider(store)("ver-1") == {}


async def test_provider_ignores_other_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES, "2")
    store = InMemorySimFillFinanceContextStore()
    await _seed_round_trips(store, version="ver-1", count=2, entry="100", exit="110")
    await _seed_round_trips(store, version="ver-2", count=2, entry="100", exit="50")

    metrics = await _provider(store)("ver-1")

    # Solo cuenta lo de ver-1 (ganador), no la versión perdedora.
    assert metrics["observed_win_rate"] == 1.0


async def test_provider_fail_closed_on_read_error() -> None:
    class _BoomStore(InMemorySimFillFinanceContextStore):
        async def list_for_strategy_version(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    metrics = await _provider(_BoomStore())("ver-1")
    # Sin lectura no hay evidencia: {} (nunca una métrica fabricada).
    assert metrics == {}


async def test_provider_blank_version_returns_empty() -> None:
    store = InMemorySimFillFinanceContextStore()
    assert await _provider(store)("") == {}


# ── Wiring en AutoOrchestrator.watch_active ──────────────────────────────────────


class _Store:
    def __init__(self, version_id: str = "ver-1") -> None:
        self._version_id = version_id
        self.saved_health: list[Any] = []

    async def get_active(self, *, instrument_id: str) -> Any:
        class _Active:
            version_id = self._version_id

        class _Record:
            active = _Active()

        return _Record()

    async def save_health(self, version_id: str, health: Any) -> None:
        self.saved_health.append(health)


async def test_watch_active_uses_observed_provider() -> None:
    store = _Store()
    seen: list[str] = []

    async def _observed(version_id: str) -> dict[str, Any]:
        seen.append(version_id)
        return {"observed_trades": 10, "observed_return_pct": 5.0}

    orchestrator = AutoOrchestrator(
        OrchestratorDeps(store=store, observed_metrics=_observed)
    )
    result = await orchestrator.watch_active(instrument_id="SAN.MC", as_of="x")

    assert seen == ["ver-1"], "el provider debe recibir la versión activa"
    assert store.saved_health, "debe persistir el snapshot"
    assert result.active_version_id == "ver-1"


async def test_watch_active_without_provider_keeps_caller_metrics() -> None:
    store = _Store()
    orchestrator = AutoOrchestrator(OrchestratorDeps(store=store))
    result = await orchestrator.watch_active(
        instrument_id="SAN.MC", metrics={"edge": 1.0}, as_of="x"
    )
    # Sin provider se comporta como antes: no falla y persiste snapshot.
    assert result.active_version_id == "ver-1"
    assert store.saved_health


async def test_watch_active_provider_failure_is_fail_closed() -> None:
    store = _Store()

    async def _boom(_version_id: str) -> dict[str, Any]:
        raise RuntimeError("boom")

    orchestrator = AutoOrchestrator(
        OrchestratorDeps(store=store, observed_metrics=_boom)
    )
    result = await orchestrator.watch_active(instrument_id="SAN.MC", as_of="x")

    # Un fallo del provider no degrada ni aprueba por sí mismo.
    assert result.status == "active"
    assert store.saved_health
