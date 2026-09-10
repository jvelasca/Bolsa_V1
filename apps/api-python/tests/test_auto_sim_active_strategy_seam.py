"""V2.26 / A10 — seam ACTIVE→AUTO por ``DecisionProvider`` (tests herméticos).

Certifica que la estrategia promovida entra en el AUTO SOLO por el seam del decider:
``load_active_strategy_decider`` lee la activa del store y ``AutoSimRuntime.set_decider``
la instala; el gate de entorno default OFF y la ausencia de activa preservan el spine.
No requiere PG (se inyecta un session_factory falso).
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_api.background import auto_simulation_worker as w


def _stub_session_factory(store: Any) -> Any:
    class _Session:
        async def __aenter__(self) -> Any:
            return object()

        async def __aexit__(self, *_: Any) -> None:
            return None

    class _Factory:
        def __call__(self) -> _Session:
            return _Session()

    # Parchea el store Postgres para devolver el activo del store hermético.
    import bolsa_application.strategy_lifecycle_store as sls

    class _Store:
        def __init__(self, session: Any) -> None:
            self._session = session

        async def get_active(self, *, instrument_id: str) -> Any:
            return await store.get_active(instrument_id=instrument_id)

    return _Factory(), _Store, sls


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", raising=False)


@pytest.mark.asyncio
async def test_load_active_decider_disabled_by_default() -> None:
    decider = await w.load_active_strategy_decider(
        object(), instrument_id="AAA", fallback=lambda s: None, watch=("AAA",)
    )
    assert decider is None


@pytest.mark.asyncio
async def test_load_active_decider_returns_none_without_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    from bolsa_application.strategy_lifecycle_store import InMemoryStrategyLifecycleStore

    store = InMemoryStrategyLifecycleStore()
    factory, StoreCls, sls = _stub_session_factory(store)
    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", StoreCls, raising=True)
    decider = await w.load_active_strategy_decider(
        factory, instrument_id="AAA", fallback=lambda s: None, watch=("AAA",)
    )
    assert decider is None


@pytest.mark.asyncio
async def test_load_active_decider_wraps_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        InMemoryStrategyLifecycleStore,
    )
    from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

    store = InMemoryStrategyLifecycleStore()
    await store.save_active(
        ActiveStrategyRecord(
            active=ActiveStrategy(
                version_id="ver-1",
                candidate_id="cand-1",
                instrument_id="AAA",
                name="SMA",
                definition={"lot_qty": 10.0, "watch": ["AAA"]},
            ),
            promoted_at="2026-09-10",
        )
    )
    factory, StoreCls, sls = _stub_session_factory(store)
    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", StoreCls, raising=True)

    def fallback(symbol: str) -> Any:
        from bolsa_application.decision_contract import DecisionPackage

        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=5.0)

    decider = await w.load_active_strategy_decider(
        factory, instrument_id="AAA", fallback=fallback, watch=("AAA",)
    )
    assert decider is not None
    prop = decider("AAA")
    assert prop.source == "active-strategy:ver-1"


@pytest.mark.asyncio
async def test_set_decider_installs_provider() -> None:
    from bolsa_application.auto_orchestrator import active_strategy_decider
    from bolsa_application.decision_contract import DecisionPackage
    from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

    active = ActiveStrategy(
        version_id="ver-9",
        candidate_id="c9",
        instrument_id="AAA",
        name="SMA",
        definition={"lot_qty": 7.0, "watch": ["AAA"]},
    )
    decider = active_strategy_decider(active=active, fallback=lambda s: DecisionPackage(
        action="BUY", instrument_id=s, quantity=7.0
    ), watch=("AAA",))

    class _FakeWorker:
        _decider = None

    class _FakeRuntime:
        _worker = _FakeWorker()

        from bolsa_api.background.auto_simulation_worker import AutoSimRuntime as _R

        set_decider = _R.set_decider

    runtime = _FakeRuntime()
    runtime.set_decider(None)  # no-op
    assert runtime._worker._decider is None
    runtime.set_decider(decider)
    assert runtime._worker._decider is decider
