"""V2.42 slice 2b — reloj de mantenimiento (E1), invalidación de tesis (E3) y ATR real (E2).

Hermético (sin PG): settlement contra ``InMemoryExecutionEventStore``, reloj y precio
inyectables. Certifica los cuatro comportamientos que 2b añade al worker V2:

* el techo de mantenimiento se **congela en el nacimiento** y, pasado, produce una salida
  REAL (``TIME_STOP``) con motivo propio en el journal (E1 · D1);
* la invalidación **confirmada** de la tesis vende (``EXIT`` real, no ``REVIEW``) y deja
  ``thesis_exit`` en el journal (E3 · D2);
* la marca adversa de cada tick (pico + MFE/MAE) **persiste**: no vive sólo en la copia
  del tick (E3: de ella depende que la invalidación sobreviva a un reinicio);
* la geometría usa el ATR **real** cuando existe y lo declara cuando no, con veto
  fail-closed detrás de ``AUTO_ENGINE_SIM_V2_ATR_REQUIRED`` (E2 · D3).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_reason_codes import (
    ATR_GEOMETRY,
    ATR_SOURCE_FALLBACK,
    ATR_SOURCE_REAL,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOLS = ["AAA"]
#: Plantilla de salida por defecto del motor V2 (``V2Tunables.exit_template``).
_TEMPLATE = "moderate"


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
    # El ``.env`` de la raíz se carga en el conftest: el veto de ATR debe partir SIEMPRE
    # del default (cada test lo activa explícitamente si lo necesita).
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", raising=False)


def _buy_lot(lot: float = 250.0) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=lot)

    return _d


def _hold() -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _edge_source(value: float = 0.9):
    """``EdgeReportSource`` fake: edge persistido por versión (sin PG)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


def _trade_kwargs() -> dict[str, object]:
    """Fuentes que hacen el pipeline OPERABLE (sin ellas el motor es fail-closed)."""
    return {
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "edge_source": _edge_source(),
    }


def _worker(*, clock=None, **kwargs: object) -> AutoSimulationWorker:
    defaults: dict[str, object] = dict(_trade_kwargs())
    defaults.update(kwargs)
    defaults.setdefault("exec_store", InMemoryExecutionEventStore())
    if clock is None:
        _start, clock = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(clock=clock, **defaults)  # type: ignore[arg-type]


def _clock_holder(now: datetime):
    """Reloj mutable: el test decide cuándo avanza el tiempo (días, no minutos)."""
    holder = {"now": now}
    return holder, lambda: holder["now"]


def _journal_codes(worker: AutoSimulationWorker) -> list[str]:
    """Motivos de gestión de posición journalizados (payload ``reasonCodes``)."""
    return [
        code
        for entry in worker._v2_journal
        if entry.payload is not None and entry.event_type == "auto_position_management"
        for code in entry.payload["reasonCodes"]
    ]


def _deadline_from_iso(created_at: str | None, days: int) -> str | None:
    """``created_at + days`` en el MISMO formato que ``PositionState`` (ISO-UTC con Z)."""
    if not created_at:
        return None
    born = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(UTC)
    return (born + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── E1 · D1: el techo de mantenimiento se congela al nacer ───────────────────────────


@pytest.mark.asyncio
async def test_v2_entry_freezes_holding_deadline_from_template(v2_env: None) -> None:
    """El techo nace con la posición (plantilla vigente) y NO se re-deriva en cada tick."""
    from bolsa_analytics.cognitive.exit_policy import resolve_holding_horizon

    days = resolve_holding_horizon(_TEMPLATE).max_holding_period_days
    assert days > 0, "la plantilla debe declarar horizonte; sin él TIME_STOP sería inerte"

    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()

    position = worker._v2_positions.get("AAA")
    assert position is not None, "la entrada debe crear el PositionState"
    frozen = _deadline_from_iso(position.created_at, days)
    assert frozen is not None
    assert position.holding_deadline_at == frozen

    worker._decider = _hold()
    await worker.auto_turn()  # un minuto más de reloj
    assert worker._v2_positions["AAA"].holding_deadline_at == frozen, "el techo no se mueve"


@pytest.mark.asyncio
async def test_v2_time_exit_sells_and_journals_time_exit(v2_env: None) -> None:
    """Pasado el techo, la posición se VENDE con motivo ``time_exit`` (no un hold eterno)."""
    holder, clock = _clock_holder(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = _worker(clock=clock)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0, "la entrada se ejecuta"

    deadline = worker._v2_positions["AAA"].holding_deadline_at
    assert deadline is not None
    holder["now"] = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)  # pasado el techo
    worker._decider = _hold()
    for _ in range(4):
        await worker.auto_turn()
        if worker._open.get("AAA", Decimal("0")) <= 0:
            break

    assert worker._open.get("AAA", Decimal("0")) == 0, "el techo debe cerrar la posición"
    codes = _journal_codes(worker)
    assert "time_exit" in codes, f"la salida por tiempo debe declararse (visto: {sorted(set(codes))})"
    assert "AAA" not in worker._v2_positions, "posición cerrada ⇒ sin estado vivo"


@pytest.mark.asyncio
async def test_v2_before_the_deadline_time_exit_does_not_fire(v2_env: None) -> None:
    """El techo no es un cierre anticipado: el día anterior la posición sigue viva."""
    holder, clock = _clock_holder(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    worker = _worker(clock=clock)
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0
    deadline = worker._v2_positions["AAA"].holding_deadline_at
    assert deadline is not None

    holder["now"] = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)  # techo: 2026-10-30
    worker._decider = _hold()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) > 0, "antes del techo no hay salida por tiempo"
    assert "time_exit" not in _journal_codes(worker)
    assert worker._v2_positions["AAA"].holding_deadline_at == deadline, "el techo no se mueve"


# ── E3 · D2: la invalidación confirmada vende ────────────────────────────────────────


@pytest.mark.asyncio
async def test_v2_confirmed_thesis_invalidation_sells_full_position(v2_env: None) -> None:
    """Nivel de invalidación declarado y atravesado ⇒ venta total con ``thesis_exit``.

    El techo se declara en el nacimiento (aquí mediante el seam: hoy ningún productor
    manda ``invalidationPrice`` al ``TradePlan``, así que el nivel cae al stop estructural
    y el que dispara es el stop; el motor SÍ honra un nivel más estrecho, que es lo que
    este test certifica).
    """
    holder, clock = _clock_holder(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    prices = {"v": 100.0}
    worker = _worker(clock=clock, price_script=lambda _s, _m: prices["v"])
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    born = worker._v2_positions["AAA"]
    assert born.invalidation_price == born.initial_stop, "sin nivel declarado, el stop es el nivel"
    worker._v2_positions["AAA"] = replace(born, invalidation_price=99.5)

    # 99.0 atraviesa el nivel de tesis pero NO el stop estructural (97): la venta sólo
    # puede venir de la invalidación.
    prices["v"] = 99.0
    worker._decider = _hold()
    for _ in range(4):
        await worker.auto_turn()
        if worker._open.get("AAA", Decimal("0")) <= 0:
            break

    assert worker._open.get("AAA", Decimal("0")) == 0, "la invalidación confirmada vende"
    codes = _journal_codes(worker)
    assert "thesis_exit" in codes, f"la salida por tesis debe declararse (visto: {set(codes)})"


@pytest.mark.asyncio
async def test_v2_stop_out_is_not_declared_as_thesis_exit(v2_env: None) -> None:
    """Cuando decide el STOP, el journal dice stop: la tesis no se apropia de la venta."""
    prices = {"v": 100.0}

    worker = _worker(price_script=lambda _s, _m: prices["v"])
    worker._decider = _buy_lot()
    await worker.auto_turn()
    assert worker._open.get("AAA", Decimal("0")) > 0

    prices["v"] = 96.0  # rompe el stop estructural (97)
    worker._decider = _hold()
    for _ in range(4):
        await worker.auto_turn()
        if worker._open.get("AAA", Decimal("0")) <= 0:
            break

    assert worker._open.get("AAA", Decimal("0")) == 0, "el stop debe cerrar"
    codes = _journal_codes(worker)
    assert "thesis_exit" not in codes, "un stop-out no es una salida por tesis"
    assert "time_exit" not in codes


@pytest.mark.asyncio
async def test_v2_adverse_mark_is_persisted_not_only_in_the_tick_copy(v2_env: None) -> None:
    """La marca adversa (MFE/MAE) sobrevive al tick y al reinicio, no sólo en la copia.

    Es la memoria de la que depende E3: si el peor adverso se quedara dentro del
    ``outcome`` del tick, un reinicio lo perdería y una invalidación ya confirmada
    volvería a parecer intacta.
    """
    from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

    account = "acc-v2-mark-durable"
    prices = {"v": 100.0}
    pos_store = InMemorySimAutoPositionStore()
    store = InMemoryExecutionEventStore()
    _start, clock1 = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1,
        exec_store=store,
        position_store=pos_store,
        account_id=account,
        price_script=lambda _s, _m: prices["v"],
        **_trade_kwargs(),  # type: ignore[arg-type]
    )
    w1._decider = _buy_lot()
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0

    prices["v"] = 98.0  # adverso pero sin tocar el stop (97) ni el techo
    w1._decider = _hold()
    await w1.auto_turn()

    live = w1._v2_positions["AAA"]
    mae = live.mfe_mae.get("maeR")
    assert mae is not None and float(mae) < 0, "la marca adversa debe quedar en el PositionState"
    durable = (await pos_store.read_projection(account, "auto-sim"))["AAA"]
    assert durable.position_state is not None
    assert durable.position_state["mfeMae"]["maeR"] == mae, "y en el espejo durable"

    # Segundo extremo adverso: el pico del trailing NO se mueve (sigue en el precio de
    # entrada), así que el único testigo de que la marca avanzó es el propio MAE. Sin el
    # sensor del ``mfeMae`` este tick se perdería y la invalidación de tesis retrocedería.
    prices["v"] = 97.3
    await w1.auto_turn()
    live = w1._v2_positions["AAA"]
    mae = live.mfe_mae.get("maeR")
    assert mae is not None and float(mae) == pytest.approx(-0.9, abs=0.01), (
        "el nuevo extremo adverso (-0,9R) debe quedar en el PositionState"
    )
    durable = (await pos_store.read_projection(account, "auto-sim"))["AAA"]
    assert durable.position_state is not None
    assert durable.position_state["mfeMae"]["maeR"] == mae, "y en el espejo durable"

    # Reinicio: el nuevo worker readopta el plan durable y conserva la memoria del adverso.
    prices["v"] = 100.0  # el mark actual no puede empeorar el MAE persistido
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 15, 10, 0, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2,
        exec_store=store,
        position_store=pos_store,
        account_id=account,
        price_script=lambda _s, _m: prices["v"],
        **_trade_kwargs(),  # type: ignore[arg-type]
    )
    await w2.readopt_positions()
    assert w2._open.get("AAA", Decimal("0")) > 0, "debe readoptar la posición durable"
    w2._decider = _hold()
    await w2.auto_turn()  # la gestión adopta el plan persistido
    restored = w2._v2_positions.get("AAA")
    assert restored is not None, "debe readoptar el plan durable"
    assert restored.mfe_mae.get("maeR") == mae, "el peor adverso sobrevive al reinicio"


@pytest.mark.asyncio
async def test_v2_favourable_mark_is_persisted_even_without_r_memory(v2_env: None) -> None:
    """El pico en PRECIO se persiste aunque el R no se pueda medir (sin ``initial_risk``).

    La marca del tick tiene dos testigos: ``mfeMae`` (en R) y el pico del trailing (en
    precio). Sin ``initial_risk`` el primero **no puede** cambiar — no hay R que medir —,
    de modo que el único testigo de que la marca avanzó es el pico en precio. Si ese
    camino no persistiera, un reinicio perdería el ancla del trailing y el stop podría
    ratchear desde un extremo viejo (el `highWatermark` es exactamente esa memoria).
    """
    from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

    account = "acc-v2-mark-watermark"
    prices = {"v": 100.0}
    pos_store = InMemorySimAutoPositionStore()
    store = InMemoryExecutionEventStore()
    _start, clock1 = step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1,
        exec_store=store,
        position_store=pos_store,
        account_id=account,
        price_script=lambda _s, _m: prices["v"],
        **_trade_kwargs(),  # type: ignore[arg-type]
    )
    w1._decider = _buy_lot()
    await w1.auto_turn()
    assert w1._open.get("AAA", Decimal("0")) > 0

    # Posición SIN memoria en R: `mfeMae` queda congelado y sólo el pico puede avanzar.
    live = w1._v2_positions["AAA"]
    w1._v2_positions["AAA"] = replace(live, initial_risk=None, mfe_mae={})
    before = dict(w1._v2_positions["AAA"].trailing or {}).get("highWatermark")

    prices["v"] = 101.5  # favorable y por debajo de T1 (103): ni parcial ni break-even
    w1._decider = _hold()
    await w1.auto_turn()

    marked = w1._v2_positions["AAA"]
    after = dict(marked.trailing or {}).get("highWatermark")
    assert marked.mfe_mae.get("mfeR") is None, "sin riesgo inicial no hay R que medir"
    assert after is not None and (before is None or float(after) > float(before)), (
        "el pico favorable debe avanzar aunque no haya R"
    )
    durable = (await pos_store.read_projection(account, "auto-sim"))["AAA"]
    assert durable.position_state is not None
    assert (durable.position_state.get("trailing") or {}).get("highWatermark") == after, (
        "el pico es estado del tick siguiente: sin persistirlo, el reinicio pierde el ancla"
    )


# ── E2 · D3: ATR real, declarado, y veto fail-closed ─────────────────────────────────


@pytest.mark.asyncio
async def test_v2_entry_uses_real_atr_geometry(v2_env: None) -> None:
    """Con ATR real la geometría de riesgo sale de él (no del 2% sintético)."""
    atr = 2.5
    worker = _worker(atr_source=lambda _symbol: atr)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    position = worker._v2_positions.get("AAA")
    assert position is not None
    # entry 100, k=1.5 ⇒ stop 100 − 3.75 = 96.25; R = 3.75 ⇒ T1 103.75 / T2 107.5.
    assert position.initial_stop == 96.25, "el stop debe venir del ATR real"
    assert position.target1 == 103.75
    assert worker._v2_atr_source_counts[ATR_SOURCE_REAL] == 1
    assert ATR_GEOMETRY not in _journal_codes(worker), "un ATR real no se declara como reserva"


@pytest.mark.asyncio
async def test_v2_synthetic_atr_is_declared_as_fallback(v2_env: None) -> None:
    """Sin ATR real, la reserva se DECLARA en el journal (nunca se disfraza de dato real)."""
    worker = _worker()  # sin atr_source ⇒ fallback declarado
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._v2_atr_source_counts[ATR_SOURCE_FALLBACK] == 1
    codes = _journal_codes(worker)
    assert ATR_GEOMETRY in codes
    entry = next(
        e
        for e in worker._v2_journal
        if e.payload is not None and e.payload.get("atrSource") == ATR_SOURCE_FALLBACK
    )
    assert entry.payload is not None
    assert entry.payload["atrRequired"] is False
    assert entry.payload["vetoed"] is False, "con el veto OFF la reserva entra, pero se declara"


@pytest.mark.asyncio
async def test_v2_atr_required_vetoes_entry_without_real_atr(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1`` ⇒ sin ATR real NO hay entrada (fail-closed)."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "1")
    worker = _worker()
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0, "el sintético no puede sostener el riesgo"
    assert worker._v2_positions.get("AAA") is None
    codes = _journal_codes(worker)
    assert ATR_GEOMETRY in codes
    assert any(
        e.payload is not None
        and e.payload.get("atrSource") == ATR_SOURCE_FALLBACK
        and e.payload.get("vetoed") is True
        for e in worker._v2_journal
    ), "el veto debe quedar declarado con su procedencia"


@pytest.mark.asyncio
async def test_v2_atr_required_allows_entry_with_real_atr(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El veto no es un bloqueo ciego: con ATR real la entrada sigue siendo operable."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "1")
    worker = _worker(atr_source=lambda _symbol: 2.0)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) > 0, "con ATR real la geometría es verificable"
    assert worker._v2_atr_source_counts[ATR_SOURCE_REAL] == 1
    assert worker._v2_positions["AAA"].initial_stop == 97.0
