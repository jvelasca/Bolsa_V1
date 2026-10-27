"""B-5 — la ACTIVE declara en el journal POR QUÉ no operó (el caso ``SIGNAL=0``).

Hallazgo de la auditoría 2026-10-26 (§3.7): con ``AUTO_ENGINE_SIM_ACTIVE_STRATEGY=1`` y
``AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL=0`` el decisor devuelve ``HOLD`` y el journal no
decía nada. El operador solo veía «no operó», indistinguible de «no quiso operar».

Aquí se prueba de extremo a extremo en el worker, sin PostgreSQL:

1. Con la señal apagada **no se compra** y el journal publica ``active_signal_disabled``.
2. La declaración es UNA por barra (dos turnos en la misma barra no la duplican).
3. Con la señal encendida pero sin barras el motivo es ``no_snapshot``, no un HOLD mudo.
4. El evento NO entra en el censo de vetos de entrada (``auto_entry_decision``): declarar
   que la estrategia no evaluó no puede contarse como «el mercado vetó».
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from bolsa_api.background import auto_simulation_worker as w
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_reason_codes import (
    ACTIVE_NO_SNAPSHOT,
    ACTIVE_SIGNAL_DISABLED,
    ACTIVE_STRATEGY_HOLD_EVENT,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.market_operability import ENTRY_DECISION_EVENT, collect_journal_reasons
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

_START = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def _active_with_executable() -> ActiveStrategy:
    """ACTIVE que SÍ compraría con la señal encendida (cruce alcista en la última barra)."""

    def _spec(period: int) -> dict[str, Any]:
        return {"definitionId": "sma", "parameters": {"period": period}}

    return ActiveStrategy(
        version_id="ver-sig",
        candidate_id="cand-sig",
        instrument_id="AAA",
        name="SMA",
        definition={
            "lot_qty": 250.0,
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
                timestamp=f"2026-01-{index + 1:02d}",
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1,
            )
            for index, close in enumerate(self._closes)
        ]


class _Session:
    async def __aenter__(self) -> Any:
        return object()

    async def __aexit__(self, *_: Any) -> None:
        return None


class _Factory:
    def __call__(self) -> _Session:
        return _Session()


@pytest.fixture
def _store(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Store hermético con la ACTIVE publicada (sin PostgreSQL)."""
    import bolsa_application.strategy_lifecycle_store as sls

    store = sls.InMemoryStrategyLifecycleStore()

    class _Store:
        def __init__(self, session: Any) -> None:
            self._session = session

        async def get_active(self, *, instrument_id: str) -> Any:
            return await store.get_active(instrument_id=instrument_id)

    monkeypatch.setattr(sls, "PostgresStrategyLifecycleStore", _Store, raising=True)
    return store


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", raising=False)
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY", "1")


def _worker() -> AutoSimulationWorker:
    _start, clock = step_minute_clock(_START)
    return AutoSimulationWorker(
        clock=clock,
        sector_source=lambda _symbol: "tech",
        liquidity_source=lambda _symbol: 1_000_000.0,
        exec_store=InMemoryExecutionEventStore(),
        reservation_store=InMemoryReservationStore(),
        exit_order_store=InMemoryExitOrderStore(),
        price_script=lambda _symbol, _at: 100.0,
    )  # type: ignore[arg-type]


def _hold_payloads(worker: AutoSimulationWorker) -> list[dict[str, Any]]:
    return [
        dict(entry.payload)
        for entry in worker._v2_journal
        if entry.payload is not None and entry.payload.get("event") == ACTIVE_STRATEGY_HOLD_EVENT
    ]


async def _install_decider(
    worker: AutoSimulationWorker,
    *,
    signal_enabled: bool,
    ohlcv: Any = None,
) -> None:
    decider = await w.load_active_strategy_decider(
        _Factory(),
        instrument_id="AAA",
        watch=("AAA",),
        signal_enabled=signal_enabled,
        ohlcv=ohlcv,
    )
    assert decider is not None, "la ACTIVE está publicada en el store hermético"
    worker._decider = decider


# ── el caso que la auditoría pide fijar ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_active_signal_flag_off_blocks_buy_explicitly(
    v2_env: None, _store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ACTIVE_STRATEGY=1`` + ``SIGNAL=0`` ⇒ HOLD **y** motivo ``active_signal_disabled``."""
    await _store.save_active(_active_with_executable_record())
    monkeypatch.delenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", raising=False)

    worker = _worker()
    await _install_decider(worker, signal_enabled=False)
    await worker.auto_turn()

    assert worker._open == {}, "con la señal apagada NO se abre nada"
    payloads = _hold_payloads(worker)
    assert payloads, "el HOLD deja su motivo en el journal"
    row = payloads[-1]
    assert row["reasonCodes"] == [ACTIVE_SIGNAL_DISABLED]
    assert row["event"] != ENTRY_DECISION_EVENT, "no se disfraza de entrada vetada"
    assert row["instrumentId"] == "AAA"
    assert row["action"] == "HOLD"


@pytest.mark.asyncio
async def test_the_declaration_is_one_per_bar(
    v2_env: None, _store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dos turnos en la MISMA barra diaria no repiten la declaración (es un hecho de barra)."""
    await _store.save_active(_active_with_executable_record())
    monkeypatch.delenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", raising=False)

    worker = _worker()
    await _install_decider(worker, signal_enabled=False)
    await worker.auto_turn()
    await worker.auto_turn()

    payloads = _hold_payloads(worker)
    assert len(payloads) == 1, "una declaración por (símbolo, motivo, barra)"


@pytest.mark.asyncio
async def test_the_declaration_is_not_counted_as_an_entry_veto(
    v2_env: None, _store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El censo de operabilidad cuenta ``auto_entry_decision``: el HOLD no lo engorda."""
    await _store.save_active(_active_with_executable_record())
    monkeypatch.delenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", raising=False)

    worker = _worker()
    await _install_decider(worker, signal_enabled=False)
    await worker.auto_turn()

    counts = collect_journal_reasons(
        list(worker._v2_journal), events=frozenset({ENTRY_DECISION_EVENT})
    )
    assert ACTIVE_SIGNAL_DISABLED not in counts


# ── control positivo: el motivo NO es una constante ─────────────────────────────────


@pytest.mark.asyncio
async def test_without_bars_the_reason_is_no_snapshot_not_a_mute_hold(
    v2_env: None, _store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``SIGNAL=1`` sin barras: el fail-closed sigue, pero ahora se explica."""
    await _store.save_active(_active_with_executable_record())
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", "1")

    worker = _worker()
    await _install_decider(worker, signal_enabled=True, ohlcv=_FakeOhlcv([]))
    await worker.auto_turn()

    assert worker._open == {}
    payloads = _hold_payloads(worker)
    assert payloads
    assert payloads[-1]["reasonCodes"] == [ACTIVE_NO_SNAPSHOT]


@pytest.mark.asyncio
async def test_with_bars_the_active_buys_and_declares_no_hold(
    v2_env: None, _store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-falso-positivo: con señal y barras la ACTIVE opera y NO hay declaración de HOLD."""
    await _store.save_active(_active_with_executable_record())
    monkeypatch.setenv("AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL", "1")

    worker = _worker()
    await _install_decider(worker, signal_enabled=True, ohlcv=_FakeOhlcv([10.0] * 7 + [20.0]))
    await worker.auto_turn()

    # La señal se EVALUÓ y entró al pipeline de decisión (hay fila de ENTRADA para AAA, que
    # con la señal apagada NO existe: allí solo hay declaración de HOLD). El veredicto de los
    # gates es otra cosa; lo que se fija es que el motivo de HOLD no se declara al tun-tun.
    decisions = [
        dict(entry.payload)
        for entry in worker._v2_journal
        if entry.payload is not None
        and entry.payload.get("event") == ENTRY_DECISION_EVENT
        and entry.payload.get("instrumentId") == "AAA"
    ]
    assert decisions, "la ACTIVE sí decidió sobre AAA"
    assert _hold_payloads(worker) == []


def _active_with_executable_record() -> Any:
    from bolsa_application.strategy_lifecycle_store import ActiveStrategyRecord

    return ActiveStrategyRecord(active=_active_with_executable(), promoted_at="2026-09-10")
