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
        object(), instrument_id="AAA", watch=("AAA",)
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
        factory, instrument_id="AAA", watch=("AAA",)
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

    # V2.31/A11: el decider clásico ya no recibe fallback del worker ⇒ sin señal
    # propia habilitada, la ACTIVE queda en HOLD (nunca hereda la acción del spine).
    decider = await w.load_active_strategy_decider(
        factory, instrument_id="AAA", watch=("AAA",)
    )
    assert decider is not None
    prop = decider("AAA")
    assert prop.source == "active-strategy:ver-1"
    assert prop.action == "HOLD"


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


# ── V2.29/A10: SignalEvaluator real (env-gated) ─────────────────────────────────


def _active_with_executable() -> Any:
    from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

    def _spec(period: int) -> dict[str, Any]:
        return {"definitionId": "sma", "parameters": {"period": period}}

    return ActiveStrategy(
        version_id="ver-sig",
        candidate_id="cand-sig",
        instrument_id="AAA",
        name="SMA",
        definition={
            "lot_qty": 42.0,
            "watch": ["AAA"],
            "executable": {
                "presetKey": "sma_crossover",
                "indicatorSpecs": [_spec(2), _spec(4)],
                "entries": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "indicator_cross",
                            "leftSpec": _spec(2),
                            "rightSpec": _spec(4),
                            "direction": "bullish",
                            "signalKind": "entry_long",
                        }
                    ],
                },
                "exits": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "indicator_cross",
                            "leftSpec": _spec(2),
                            "rightSpec": _spec(4),
                            "direction": "bearish",
                            "signalKind": "exit",
                        }
                    ],
                },
            },
        },
    )


class _FakeOhlcv:
    def __init__(self, closes: list[float]) -> None:
        self._closes = closes

    async def get_bars(self, instrument_id: str, *, timeframe: Any = None, limit: Any = None):
        from bolsa_domain.entities.ohlcv_bar import OhlcvBar

        return [
            OhlcvBar(
                timestamp=f"2026-01-{i + 1:02d}",
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1,
            )
            for i, c in enumerate(self._closes)
        ]


@pytest.mark.asyncio
async def test_signal_disabled_uses_classic_decider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin señal habilitada la ACTIVE no opera (HOLD): no hereda la acción del spine."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    monkeypatch.delenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", raising=False)
    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        InMemoryStrategyLifecycleStore,
    )

    store = InMemoryStrategyLifecycleStore()
    await store.save_active(
        ActiveStrategyRecord(active=_active_with_executable(), promoted_at="2026-09-10")
    )
    factory, StoreCls, sls = _stub_session_factory(store)
    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", StoreCls, raising=True)

    # El worker solo pasa ``signal_enabled`` cuando el flag de entorno está ON; aquí se
    # omite (default False) ⇒ decider clásico sin señal propia ⇒ HOLD.
    decider = await w.load_active_strategy_decider(
        factory,
        instrument_id="AAA",
        watch=("AAA",),
    )
    assert decider is not None
    assert decider("AAA").action == "HOLD"


@pytest.mark.asyncio
async def test_signal_enabled_uses_own_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", "1")
    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        InMemoryStrategyLifecycleStore,
    )

    store = InMemoryStrategyLifecycleStore()
    await store.save_active(
        ActiveStrategyRecord(active=_active_with_executable(), promoted_at="2026-09-10")
    )
    factory, StoreCls, sls = _stub_session_factory(store)
    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", StoreCls, raising=True)

    decider = await w.load_active_strategy_decider(
        factory,
        instrument_id="AAA",
        watch=("AAA",),
        signal_enabled=True,
        ohlcv=_FakeOhlcv([10.0] * 7 + [20.0]),
    )
    assert decider is not None
    prop = decider("AAA")
    assert prop.action == "BUY"  # señal propia (cruce en la última barra)
    assert prop.quantity == 42.0  # lote de la ACTIVE
    assert prop.source == "active-strategy:ver-sig"


@pytest.mark.asyncio
async def test_signal_enabled_without_bars_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin barras la ACTIVE queda en HOLD (fail-closed V2.31/A11), no en el spine."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", "1")
    from bolsa_application.strategy_lifecycle_store import (
        ActiveStrategyRecord,
        InMemoryStrategyLifecycleStore,
    )

    store = InMemoryStrategyLifecycleStore()
    await store.save_active(
        ActiveStrategyRecord(active=_active_with_executable(), promoted_at="2026-09-10")
    )
    factory, StoreCls, sls = _stub_session_factory(store)
    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", StoreCls, raising=True)

    decider = await w.load_active_strategy_decider(
        factory,
        instrument_id="AAA",
        watch=("AAA",),
        signal_enabled=True,
        ohlcv=_FakeOhlcv([]),  # sin barras ⇒ HOLD (no se opera)
    )
    assert decider is not None
    assert decider("AAA").action == "HOLD"


def test_signal_flag_defaults_off() -> None:
    import os

    os.environ.pop("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", None)
    assert w.active_strategy_signal_enabled() is False
