"""AUTO 2.0 (V2) — integración del pipeline de decisión en el worker SIM.

Hermético (sin PG): settlement contra ``InMemoryExecutionEventStore``, reloj y precio
deterministas. Valida que con ``AUTO_ENGINE_SIM_V2=1``:

* las entradas pasan por OpportunityRanker → PortfolioDecisionEngine → TradePlan
  (el tamaño lo fija el RiskAllocator, NO el ``lot_qty`` del decider),
* el régimen manda (UNKNOWN ⇒ exit-only ⇒ ninguna entrada),
* la gestión de posición usa PositionState + ExitPlan + PositionDecision,
* con el gate OFF nada cambia (comportamiento v2.39.x intacto).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    FillObservation,
    step_minute_clock,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOLS = ["AAA"]


def _bars(step: float, length: int = 120) -> list[dict[str, float]]:
    """Serie sintética con tendencia (``step``>0 alcista, <0 bajista)."""
    out: list[dict[str, float]] = []
    for i in range(length):
        close = 100.0 + step * i
        out.append({"close": close, "high": close * 1.004, "low": close * 0.996})
    return out


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _buy_lot(lot: float = 250.0) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=lot)

    return _d


def _hold() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _worker(**kwargs: object) -> AutoSimulationWorker:
    defaults: dict[str, object] = dict(_trade_kwargs())
    defaults.update(kwargs)
    # Store hermético por defecto; un test puede inyectar el suyo (si no, el default
    # pisaría su ``exec_store`` y no podría preparar trazas pendientes).
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))[1],
        **defaults,  # type: ignore[arg-type]
    )


def _edge_source(value: float = 0.9):
    """``EdgeReportSource`` fake: edge persistido por versión de estrategia (sin PG)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _trade_kwargs() -> dict[str, object]:
    """Fuentes de dato que hacen el pipeline OPERABLE (V2.40.1).

    Sin sector/liquidez/edge conocidos el motor es fail-closed y NO abre nada, así que
    los tests de mecánica del worker inyectan estos fakes. Los tests del propio
    fail-closed pasan ``None``/valores ausentes para certificar el veto.
    """
    return {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
    }


@pytest.mark.asyncio
async def test_v2_gate_enabled_flag(v2_env: None) -> None:
    worker = _worker()
    assert worker.v2_enabled() is True


def test_v2_off_by_default_keeps_legacy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(V2_ENGINE_ENV, raising=False)
    worker = _worker()
    assert worker.v2_enabled() is False


@pytest.mark.asyncio
async def test_v2_entry_uses_risk_allocator_not_lot_qty(v2_env: None) -> None:
    """El tamaño lo fija el RiskAllocator (1% de 100k / stop de 3) y no el lot 250."""
    worker = _worker()
    worker._decider = _buy_lot(250.0)
    await worker.auto_turn()
    held = worker._open.get("AAA", Decimal("0"))
    assert held > 0, "el pipeline V2 debe abrir una posición aprobada"
    # Precio 100, ATR = 2% de 100 = 2 ⇒ stop = 100 − 1.5×2 = 97 ⇒ distancia 3.
    # risk 1000 / 3 = 333.33, acotado por max_position_pct 20% ⇒ 200 uds.
    assert held == Decimal("200.000000"), f"esperado sizing del allocator, no lot_qty (held={held})"


@pytest.mark.asyncio
async def test_v2_unknown_regime_blocks_entries(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UNKNOWN ⇒ exit-only: el pipeline no emite ninguna propuesta de entrada."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "")  # sin régimen ⇒ UNKNOWN
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0
    assert worker._v2_plan is not None
    assert worker._v2_plan.regime == "UNKNOWN"


@pytest.mark.asyncio
async def test_v2_position_state_created_on_entry(v2_env: None) -> None:
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()
    position = worker._v2_positions.get("AAA")
    assert position is not None, "la apertura V2 debe crear un PositionState"
    assert position.status == "OPEN"
    assert position.initial_stop == 97.0
    assert position.target1 == 103.0
    assert position.target2 == 106.0


@pytest.mark.asyncio
async def test_v2_no_duplicate_entry_while_held(v2_env: None) -> None:
    """Con posición abierta el pipeline rechaza la re-entrada (position_exists)."""
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()
    before = worker._open["AAA"]
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open["AAA"] == before, "no debe apilar una segunda entrada"


@pytest.mark.asyncio
async def test_v2_protective_stop_managed_by_position_manager(
    v2_env: None,
) -> None:
    """Caída al stop estructural ⇒ PositionManager cierra (no ProtectionConfig)."""
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0

    worker = _worker(price_script=script)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    worker._decider = _hold()
    await worker.auto_turn()  # precio 96 ≤ stop 97 ⇒ venta total
    assert worker._open.get("AAA", Decimal("0")) == 0, "el stop debe cerrar la posición"
    assert "AAA" not in worker._v2_positions


@pytest.mark.asyncio
async def test_v2_target1_reduces_not_full_exit(v2_env: None) -> None:
    """T1 alcanzado ⇒ reducción parcial (moderate 30%), no cierre total."""
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 103.5  # ≥ T1 103

    worker = _worker(price_script=script)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    opened = worker._open.get("AAA", Decimal("0"))
    assert opened > 0
    worker._decider = _hold()
    await worker.auto_turn()
    held = worker._open.get("AAA", Decimal("0"))
    assert 0 < held < opened, "T1 debe reducir parcialmente, no cerrar del todo"
    # 30% de 200 = 60 vendidas ⇒ quedan 140.
    assert held == Decimal("140.000000")


@pytest.mark.asyncio
async def test_v2_target1_not_repeated_across_ticks(v2_env: None) -> None:
    """T1 ya ejecutado no se re-dispara: el PositionState es la memoria."""
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 103.5

    worker = _worker(price_script=script)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    worker._decider = _hold()
    await worker.auto_turn()  # reduce T1
    after_first = worker._open.get("AAA", Decimal("0"))
    await worker.auto_turn()  # sigue por encima de T1: no debe volver a reducir
    assert worker._open.get("AAA", Decimal("0")) == after_first


@pytest.mark.asyncio
async def test_v2_regime_exit_only_flattens_open_position(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si el régimen pasa a UNKNOWN, la posición abierta se cierra (exit-only)."""
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "")
    from dataclasses import replace

    worker._v2_tunables = replace(worker._v2_tunables, regime_override=None)
    worker._decider = _hold()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "exit-only debe aplanar"


@pytest.mark.asyncio
async def test_v2_journal_records_reason_codes(v2_env: None) -> None:
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._v2_journal, "el pipeline debe dejar journal del tick"
    payload = worker._v2_journal[0].payload
    assert payload is not None
    assert payload["reasonCodes"] == ["approved"]
    assert payload["tradePlan"]["status"] == "TRIGGERED"


@pytest.mark.asyncio
async def test_v2_adopts_readopted_position_after_restart(v2_env: None) -> None:
    """Tras crash+restart la posición readoptada sigue gestionada por AUTO 2.0.

    P4: el plan operativo (``PositionState``) es durable, así que el reinicio REHIDRATA
    el plan EXACTO que el motor seguía (mismo ``trade_plan_id``, mismo stop) en vez de
    reconstruirlo. La posición nunca queda huérfana ni con una geometría inventada.
    """
    from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account_id = "acc-v2-readopt"

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1,
        exec_store=store,
        position_store=pos_store,
        account_id=account_id,
        **_trade_kwargs(),
    )
    w1._decider = _buy_lot()
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0
    original = w1._v2_positions.get("AAA")
    assert original is not None
    # El plan V2 quedó persistido en el espejo durable en el mismo turno del fill.
    durable_row = (await pos_store.read_projection(account_id, "auto-sim"))["AAA"]
    assert durable_row.position_state, "el plan V2 debe ser durable tras la apertura"

    # Crash + restart: nuevo worker (sin estado V2 en RAM) sobre el MISMO espejo.
    price = {"v": 100.0}

    def script(_symbol: str, _minute: int) -> float:
        return price["v"]

    _s2, clock2 = step_minute_clock(datetime(2026, 9, 15, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2,
        exec_store=store,
        position_store=pos_store,
        account_id=account_id,
        price_script=script,
        **_trade_kwargs(),
    )
    await w2.real_turn(
        exec_store=store,
        auto_store=None,
        finance_applier=None,
        account_id=account_id,
        position_store=pos_store,
    )
    assert w2._open.get("AAA", Decimal("0")) > 0, "debe readoptar la posición"
    adopted = w2._v2_positions.get("AAA")
    assert adopted is not None, (
        "tras el reinicio la posición debe quedar gestionada (adopción), no huérfana"
    )
    assert adopted.trade_plan_id == original.trade_plan_id, "plan durable rehidratado"
    assert adopted.initial_stop == original.initial_stop
    assert adopted.current_stop == original.current_stop
    assert adopted.remaining_quantity == original.remaining_quantity
    assert w2._v2_durable_plans == {}, "el plan durable se consume una sola vez"

    # El stop rehidratado sigue vivo: al romperlo, la posición se cierra.
    price["v"] = 96.0
    w2._decider = _hold()
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == 0, (
        "la posición adoptada debe seguir gestionada (stop vivo)"
    )


@pytest.mark.asyncio
async def test_v2_adopts_with_reconstructed_geometry_without_durable_plan(
    v2_env: None,
) -> None:
    """Sin plan durable (espejo legado/AUTO 1.0) la posición se adopta igual.

    Fallback explícito: cantidad/entrada sí sobreviven, pero no hubo plan V2 que
    persistir. Se adopta con geometría reconstruida (stop = entrada − atr_mult × ATR
    y objetivos en múltiplos de R) y se marca ``adopted`` — gestionar sin estado es
    peor que un plan aproximado, pero nunca se disfraza de plan original.
    """
    from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account_id = "acc-v2-readopt-legacy"
    # Espejo escrito por un camino que NO guardaba plan V2 (sin ``position_state``).
    await pos_store.upsert(
        account_id,
        "auto-sim",
        "AAA",
        Decimal("100"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
    )

    _s, clock = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        position_store=pos_store,
        account_id=account_id,
        price_script=lambda _symbol, _minute: 100.0,
    )
    worker._decider = _hold()
    await worker.readopt_positions()
    adopted = worker._v2_adopt_position("AAA", Decimal("100"))
    assert adopted is not None, "sin plan durable se adopta con geometría reconstruida"
    assert adopted.trade_plan_id == "adopted-AAA"
    assert adopted.initial_stop == 97.0
    assert adopted.remaining_quantity == 100.0


@pytest.mark.asyncio
async def test_v2_regime_source_from_bars_enables_entries(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin override: el régimen sale de las BARRAS (discovery_market_regime_v0)."""
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "")  # sin override ⇒ fuente real

    async def provider() -> dict[str, list[dict[str, float]]]:
        return {"AAA": _bars(+0.6)}

    source = DiscoveryRegimeSource(bars_provider=provider)
    worker = _worker(regime_source=source)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert source.trial_regime() == "trend_up"
    assert source() == "BULL_TREND"
    assert worker._open.get("AAA", Decimal("0")) > 0, "tendencia alcista debe permitir entrar"


@pytest.mark.asyncio
async def test_v2_regime_source_downtrend_blocks_long_entries(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tendencia bajista confirmada ⇒ ningún LONG nuevo (gate direccional)."""
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "")

    async def provider() -> dict[str, list[dict[str, float]]]:
        return {"AAA": _bars(-0.6)}

    source = DiscoveryRegimeSource(bars_provider=provider)
    worker = _worker(regime_source=source)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert source() == "BEAR_TREND"
    assert worker._open.get("AAA", Decimal("0")) == 0, "no se abre LONG en tendencia bajista"
    assert worker._v2_plan.journal_entries[0].payload["reasonCodes"] == ["regime_invalid"]


@pytest.mark.asyncio
async def test_v2_regime_source_error_is_fail_closed(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si no se pueden leer las barras, el régimen queda UNKNOWN ⇒ exit-only."""
    from bolsa_application.auto_v2_entry import DiscoveryRegimeSource

    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "")

    async def boom() -> dict[str, list[dict[str, float]]]:
        raise RuntimeError("feed caído")

    worker = _worker(regime_source=DiscoveryRegimeSource(bars_provider=boom))
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0
    assert worker._v2_plan.regime == "UNKNOWN"


@pytest.mark.asyncio
async def test_v2_sector_source_feeds_concentration_gate(v2_env: None) -> None:
    """El sector inyectado llega al gate: dos entradas del mismo sector no caben."""
    worker = _worker(sector_source=lambda _s: "tech")
    worker._v2_tunables = replace(worker._v2_tunables, max_sector_pct=25.0, top_n=2)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    # Una sola posición (una entrada por símbolo) ⇒ el sector no puede excederse aún.
    assert worker._open.get("AAA", Decimal("0")) > 0
    decision = worker._v2_plan.decisions[0]
    assert decision.sector == "tech", "el sector debe viajar a la decisión"


@pytest.mark.asyncio
async def test_v2_sector_from_memo_wins_over_source(v2_env: None) -> None:
    """Lo que declara la propuesta (``memo``) manda sobre la fuente inyectada."""

    def decider(symbol: str) -> DecisionPackage:
        return DecisionPackage(
            action="BUY",
            instrument_id=symbol,
            quantity=250.0,
            memo="edge=0.9 sector=energy",
        )

    worker = _worker(sector_source=lambda _s: "tech")
    worker._decider = decider
    await worker.auto_turn()
    assert worker._v2_plan.decisions[0].sector == "energy"


@pytest.mark.asyncio
async def test_v2_without_trade_sources_is_fail_closed(v2_env: None) -> None:
    """V2.40.1 (P0-7): sin sector/ADV/edge reales NO hay entrada, aunque haya régimen.

    Es el invariante que cierra el gap de producción de ``v2.40-beta``: el worker real
    corría sin fuentes y el motor, en vez de abrir a ciegas, debe quedarse en NO ENTRY
    con el motivo auditable de la primera fuente que falta (liquidez → edge → sector).
    """
    cases = [
        # (kwargs de fuentes, motivo esperado) — cascada en el orden del motor:
        # liquidez → edge → sector.
        ({"sector_source": None, "liquidity_source": None, "edge_source": None}, "liquidity_unknown"),
        (
            {"sector_source": None, "liquidity_source": lambda _s: 1_000_000.0, "edge_source": None},
            "edge_below_threshold",
        ),
        (
            {
                "sector_source": None,
                "liquidity_source": lambda _s: 1_000_000.0,
                "edge_source": _edge_source(),
            },
            "sector_unknown",
        ),
    ]
    for sources, expected in cases:
        worker = _worker(**sources)
        worker._decider = _buy_lot()
        await worker.auto_turn()
        assert worker._open.get("AAA", Decimal("0")) == 0, f"sin fuentes no se abre ({expected})"
        assert worker._v2_plan.approved_symbols == ()
        assert expected in worker._v2_plan.decisions[0].reason_codes
        assert worker._v2_plan.journal_entries[0].payload["approved"] is False


def test_v2_recon_status_never_blocks_protective_exit(v2_env: None) -> None:
    """Invariante: la reconciliación veta APERTURAS, nunca cierres.

    Regresión: mapear UNKNOWN ⇒ ``drift`` degradaba el stop a REVIEW y dejaba una
    posición con el stop rebasado sin vender (el peor fallo posible).
    """
    from bolsa_application.sim_reconciliation import (
        POSITION_PROJECTION_DIVERGENT,
        POSITION_PROJECTION_OK,
        POSITION_PROJECTION_REBUILT,
        POSITION_PROJECTION_UNKNOWN,
    )

    worker = _worker()
    worker._reconciliation = {"AAA": POSITION_PROJECTION_UNKNOWN}
    assert worker._v2_recon_status("AAA") is None, "UNKNOWN no es drift"
    worker._reconciliation = {"AAA": POSITION_PROJECTION_DIVERGENT}
    assert worker._v2_recon_status("AAA") == "drift"
    worker._reconciliation = {"AAA": POSITION_PROJECTION_OK}
    assert worker._v2_recon_status("AAA") == "clean"
    worker._reconciliation = {"AAA": POSITION_PROJECTION_REBUILT}
    assert worker._v2_recon_status("AAA") == "clean"
    assert worker._v2_recon_status("BBB") is None, "sin veredicto no se afirma limpieza"


@pytest.mark.asyncio
async def test_v2_kill_switch_blocks_everything(v2_env: None) -> None:
    """Fail-closed: con el kill activo el pipeline ni se planifica ni opera."""
    worker = _worker(kill_switch_source=lambda: True)
    worker._decider = _buy_lot()
    report = await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0
    assert worker._v2_plan is None, "sin gate válido no se planifica el tick"
    assert report.vetoes > 0


@pytest.mark.asyncio
async def test_v2_entry_consumes_signal_of_the_bar(v2_env: None) -> None:
    """La señal tomada queda consumida; sin fill NO se quema la señal."""
    from bolsa_application.auto_v2_entry import signal_identity_for_bar

    worker = _worker()
    worker._decider = _hold()
    await worker.auto_turn()
    assert worker._v2_consumed_signals == set(), "sin entrada no se consume la señal"

    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    assert len(worker._v2_consumed_signals) == 1, "un fill ⇒ una señal consumida"

    expected = signal_identity_for_bar(
        instrument_id="AAA",
        action="BUY",
        strategy_version="unversioned",
        timeframe="1d",
        moment=datetime(2026, 9, 15, 9, 1, tzinfo=UTC),
    )
    assert expected is not None
    assert worker._v2_consumed_signals == {expected.signal_id}


@pytest.mark.asyncio
async def test_v2_same_bar_signal_does_not_reopen_after_stop_out(
    v2_env: None,
) -> None:
    """Anti-churn: stop-out y re-entrada en la MISMA barra con la MISMA señal ⇒ no.

    Es el escenario que la identidad de señal existe para matar: el decider sigue
    emitiendo el mismo BUY diario, la posición se cierra por stop dentro de la misma
    barra y el turno siguiente NO puede re-abrirla (misma barra + misma estrategia).
    """
    prices = {"n": 0}

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0  # 2º tick rompe el stop (97)

    worker = _worker(price_script=script)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    worker._decider = _buy_lot()
    await worker.auto_turn()  # stop-out: cierra la posición
    assert worker._open.get("AAA", Decimal("0")) == 0
    # Misma barra (1d) y mismo decider: la señal ya se consumió ⇒ no se re-abre.
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, (
        "la MISMA señal sobre la MISMA barra no puede re-abrir (churn)"
    )
    reasons = [
        code
        for entry in worker._v2_journal
        if entry.payload is not None
        for code in entry.payload["reasonCodes"]
    ]
    assert "signal_duplicate" in reasons


@pytest.mark.asyncio
async def test_v2_new_bar_signal_can_open_again(v2_env: None) -> None:
    """La barra siguiente (otro día) sí puede volver a abrir: nueva identidad."""
    holder = {"now": datetime(2026, 9, 15, 9, 0, tzinfo=UTC)}
    prices = {"n": 0}

    def clock() -> datetime:
        return holder["now"]

    def script(_symbol: str, _minute: int) -> float:
        prices["n"] += 1
        return 100.0 if prices["n"] <= 1 else 96.0

    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        price_script=script,
        **_trade_kwargs(),
    )
    worker._decider = _buy_lot()
    await worker.auto_turn()
    worker._decider = _buy_lot()
    await worker.auto_turn()  # stop-out dentro de la misma barra
    assert worker._open.get("AAA", Decimal("0")) == 0
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) == 0, "misma barra ⇒ no re-abre"

    # Barra nueva (día siguiente): identidad nueva ⇒ vuelve a ser operable.
    holder["now"] = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)
    worker._price_script = lambda _symbol, _minute: 100.0
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._v2_plan is not None
    assert worker._v2_plan.approved_symbols == ("AAA",), (
        "una barra nueva es una oportunidad nueva (no es la señal de ayer)"
    )
    # El settlement SIM es determinista por minuto y puede no cruzar en el primer
    # intento; el pipeline vuelve a proponer hasta que el broker llena.
    for _ in range(4):
        if worker._open.get("AAA", Decimal("0")) > 0:
            break
        worker._decider = _buy_lot()
        await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0, "la entrada de la barra nueva se ejecuta"


@pytest.mark.asyncio
async def test_v2_consumed_signal_survives_restart(v2_env: None) -> None:
    """P4: la señal consumida es DURABLE — un reinicio no reabre la misma oportunidad.

    Sin espejo, el reinicio vaciaría la memoria de dedupe y el turno siguiente volvería
    a emitir el MISMO BUY sobre la MISMA barra (churn tras crash). Con el espejo, la
    marca sobrevive: el plan del nuevo worker nace ya vetado.
    """
    from bolsa_application.sim_durable_store import InMemorySimConsumedSignalStore

    signals = InMemorySimConsumedSignalStore()
    account_id = "acc-v2-consumed-durable"
    store = InMemoryExecutionEventStore()

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1,
        exec_store=store,
        account_id=account_id,
        consumed_signal_store=signals,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )
    w1._decider = _buy_lot()
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0, "la entrada se ejecuta"
    consumed_ids = set(w1._v2_consumed_signals)
    assert len(consumed_ids) == 1
    bar = w1._v2_current_bar_start()
    assert bar, "barra corriente identificable"
    assert await signals.list_bar(account_id, "auto-sim", bar) == sorted(consumed_ids), (
        "la marca quedó persistida en el espejo durable"
    )

    # Crash + restart en la MISMA barra: la señal ya está consumida en el espejo.
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 15, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2,
        exec_store=store,
        account_id=account_id,
        consumed_signal_store=signals,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )
    assert w2._v2_consumed_signals == set(), "el proceso nuevo nace sin memoria de RAM"
    w2._decider = _buy_lot()
    await w2.auto_turn()
    assert w2._v2_consumed_signals == consumed_ids, "la carga durable repone el dedupe"
    assert w2._open.get("AAA", Decimal("0")) == 0, (
        "la señal consumida antes del crash no puede re-abrir la posición"
    )
    reasons = [
        code
        for entry in w2._v2_journal
        if entry.payload is not None
        for code in entry.payload["reasonCodes"]
    ]
    assert "signal_duplicate" in reasons


@pytest.mark.asyncio
async def test_v2_consumed_signals_pruned_to_current_bar(v2_env: None) -> None:
    """El espejo de señales se poda: solo la barra corriente puede deduplicar."""
    from bolsa_application.sim_durable_store import InMemorySimConsumedSignalStore

    signals = InMemorySimConsumedSignalStore()
    account_id = "acc-v2-consumed-prune"
    await signals.mark(
        account_id,
        "auto-sim",
        "sig-de-ayer",
        instrument_id="AAA",
        bar_timestamp="2026-09-14T00:00:00+00:00",
    )
    _s, clock = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        account_id=account_id,
        consumed_signal_store=signals,
        price_script=lambda _symbol, _minute: 100.0,
        **_trade_kwargs(),
    )
    worker._decider = _hold()
    await worker.auto_turn()
    assert await signals.list_bar(account_id, "auto-sim", "2026-09-14T00:00:00+00:00") == [], (
        "las señales de barras anteriores se podan (no crecen sin límite)"
    )
    assert worker._v2_consumed_signals == set(), (
        "una señal de OTRA barra no puede bloquear la barra corriente"
    )


@pytest.mark.asyncio
async def test_v2_full_day_produces_healthy_journal(v2_env: None) -> None:
    """Día completo AUTO 2.0: entradas por pipeline y salidas por régimen exit-only."""
    from dataclasses import replace

    from bolsa_application.auto_daily_journal import build_auto_daily_report

    worker = _worker()
    # Fase 1 — descubrimiento/entrada: el pipeline rankea y abre con sizing propio.
    for _ in range(20):
        worker._decider = _buy_lot()
        await worker.auto_turn()
        if worker.open_symbols:
            break
    assert worker.open_symbols, "el pipeline debe abrir en régimen operable"

    # Fase 2 — el régimen pasa a UNKNOWN ⇒ exit-only: la posición se cierra.
    worker._v2_tunables = replace(worker._v2_tunables, regime_override="UNKNOWN")
    worker._decider = _hold()
    for _ in range(10):
        await worker.auto_turn()
        if not worker.open_symbols:
            break
    assert not worker.open_symbols, "exit-only debe aplanar el libro"

    report = build_auto_daily_report(
        rows=worker.journal_pairs(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
    )
    assert report.orders > 0
    assert report.fills > 0
    assert report.positions_created > 0
    assert report.exits > 0
    assert report.no_duplicate_execution_events
    assert report.all_venues_in_auto_sim
    assert report.no_live_bridge_posts
    assert report.ledger_balanced
    assert report.healthy, report.errors


# ── V2.40.4: órdenes PENDIENTES (capital ya comprometido) ──────────────────────


class _StoreWithoutUnapplied(InMemoryExecutionEventStore):
    """Store que NO sabe listar pendientes (protocolo anterior a V2.40.4)."""

    list_unapplied = None  # type: ignore[assignment]


async def _pending_trace(
    store: InMemoryExecutionEventStore,
    *,
    execution_id: str = "ex-pending",
    account_id: str = "acc-v2-open-orders",
    qty: str = "850",
) -> None:
    """Deja una traza ``CAPTURED`` (fill de otro proceso, p.ej. tras un crash)."""
    from bolsa_application.execution_event import ExecutionEvent

    await store.capture(
        ExecutionEvent(
            execution_id=execution_id,
            order_id="o-pending",
            venue="paper",
            venue_order_id="v-1",
            fill_seq=1,
            qty=Decimal(qty),
            account_id=account_id,
        )
    )


async def _finance_context(
    *,
    execution_id: str = "ex-pending",
    account_id: str = "acc-v2-open-orders",
    symbol: str = "AAA",
    side: str = "buy",
    qty: str = "850",
    price: str = "100",
) -> object:
    """Contexto financiero durable del fill (lado/cantidad/precio)."""
    from bolsa_application.sim_durable_store import (
        InMemorySimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    store = InMemorySimFillFinanceContextStore()
    await store.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id=symbol,
            side=side,
            quantity=Decimal(qty),
            price=Decimal(price),
            account_id=account_id,
        )
    )
    return store


@pytest.mark.asyncio
async def test_v2_pending_buy_reserves_cash_and_lowers_available(v2_env: None) -> None:
    """Un BUY en vuelo reserva su notional: el snapshot publica ``available_cash``."""
    account_id = "acc-v2-open-orders"
    store = InMemoryExecutionEventStore()
    await _pending_trace(store, account_id=account_id)
    contexts = await _finance_context(account_id=account_id)
    worker = _worker(exec_store=store, context_store=contexts, account_id=account_id)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert len(worker._v2_open_orders) == 1, "el pendiente debe verse en el libro"
    order = worker._v2_open_orders[0]
    assert order.side == "buy"
    assert order.reserved_cash == 85_000.0, "cantidad × precio del contexto financiero"

    snapshot = worker._v2_snapshot("BULL_TREND")
    assert snapshot.reserved_cash == 85_000.0
    assert snapshot.available_cash == 15_000.0, "100k de equity − 85k comprometidos"


@pytest.mark.asyncio
async def test_v2_pending_buy_blocks_new_entry_fail_closed(v2_env: None) -> None:
    """El libro no medible (riesgo del fill en vuelo desconocido) veta la entrada.

    ``sim_fill_finance_context`` no lleva stop, así que el riesgo de una compra en vuelo
    es un SUELO: el motor no puede afirmar el riesgo pendiente ⇒ no se añade riesgo nuevo
    hasta que la reconciliación materialice el pendiente. El motivo queda en el journal.
    """
    account_id = "acc-v2-open-orders"
    store = InMemoryExecutionEventStore()
    await _pending_trace(store, account_id=account_id)
    contexts = await _finance_context(account_id=account_id)
    worker = _worker(exec_store=store, context_store=contexts, account_id=account_id)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker.open_symbols == (), "un pendiente no cuantificable vetó la apertura"
    reasons = [
        code
        for entry in worker._v2_journal
        if entry.payload is not None
        for code in entry.payload["reasonCodes"]
    ]
    assert "open_orders_unmeasurable" in reasons


@pytest.mark.asyncio
async def test_v2_pending_without_finance_context_is_unknown(v2_env: None) -> None:
    """Sin contexto financiero la orden no se cuantifica: libro UNKNOWN ⇒ veto."""
    account_id = "acc-v2-open-orders"
    store = InMemoryExecutionEventStore()
    await _pending_trace(store, account_id=account_id)
    worker = _worker(exec_store=store, account_id=account_id)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._v2_order_book_measurement == "UNKNOWN"
    assert worker.open_symbols == ()
    assert worker._v2_snapshot("BULL_TREND").reserved_cash == 0.0, (
        "no se declara como 0: el capital es desconocido (el veto lo corta antes)"
    )


@pytest.mark.asyncio
async def test_v2_store_without_list_unapplied_is_unknown(v2_env: None) -> None:
    """Un store que no sabe listar pendientes NO puede afirmar que no hay ninguno."""
    worker = _worker(exec_store=_StoreWithoutUnapplied(), account_id="acc-v2-open-orders")
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._v2_order_book_measurement == "UNKNOWN"
    assert worker.open_symbols == ()


@pytest.mark.asyncio
async def test_v2_known_fill_is_not_reserved_twice(v2_env: None) -> None:
    """Un fill ya reconocido por el libro del worker NO se reserva otra vez.

    ``execution_events`` conserva la fila ``CAPTURED`` cuando no hay applier, pero si el
    worker ya la reconoció su capital ya está en ``positions``: reservarlo de nuevo
    contaría el mismo dinero dos veces y vetaría la cartera entera sin motivo.
    """
    account_id = "acc-v2-open-orders"
    store = InMemoryExecutionEventStore()
    await _pending_trace(store, execution_id="ex-known", account_id=account_id)
    worker = _worker(exec_store=store, account_id=account_id)
    worker._record_applied_event(
        "AAA",
        FillObservation(
            side="buy",
            venue="paper",
            execution_id="ex-known",
            order_id="o-known",
            qty=Decimal("850"),
        ),
        Decimal("100"),
    )
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._v2_open_orders == (), "el fill ya reconocido no está pendiente"
    assert worker._v2_order_book_measurement == "COMPLETE"
    assert worker._v2_snapshot("BULL_TREND").reserved_cash == 0.0
