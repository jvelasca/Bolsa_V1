"""W2 · Fase A — short-circuit de BARRA: equivalencia ESTRICTA (`Δ = 0`).

El diseño v2 de ``GRANULARIDAD-OPERATIVA`` exige que la optimización de Fase A sea
**semánticamente neutra**: se conserva el bucle de 60 s y se deja de releer, dentro de la
MISMA barra D1, el I/O de DATO que la barra ya decidió. La condición para aprobarla es un
golden de equivalencia ``OLD (60 s)`` vs ``NEW (dato de barra reutilizado)`` con
``Δ fills = Δ cycles = Δ reservas = Δ settlements = Δ PnL = Δ evidence = 0``.

Qué fija esta suite, y por qué importa:

* **Neutro sobre el informe del día.** El control (``OLD``: el mismo turno durable con el
  seam apagado) y el nuevo (``NEW``) corren EXACTAMENTE la misma secuencia de turnos, y el
  informe diario agregado —embudo, journal, procedencia del ATR, atribución, PnL— sale
  idéntico. Sin esto, «optimización» sería un eufemismo de «cambio de comportamiento».
* **El I/O desaparece de verdad.** No basta con que el resultado coincida: se cuentan las
  lecturas por turno (régimen, contexto de cartera, órdenes pendientes) y el turno
  reutilizado NO las hace. Un test que solo comparara informes pasaría aunque el
  short-circuit no llegara a activarse nunca.
* **La PROTECCIÓN no se salta.** Una salida dentro de la barra (el precio rompe el stop
  estructural en un turno intermedio) ocurre en los DOS caminos: el short-circuit ahorra
  I/O de decisión, jamás gestión de posición. Es la esquina que convierte el ahorro en
  fail-open si alguien lo ensancha.
* **Fail-closed en los bordes.** El turno que deja una aprobación SIN consumir no reutiliza
  el dato, y el cambio de barra vuelve a releer. Cada uno tiene su test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_daily_journal import build_auto_daily_report
from bolsa_application.auto_engine_state_store import (
    AutoEngineTickInput,
    InMemoryAutoEngineStore,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import InMemorySimAutoPositionStore

_ACCOUNT = "acc-w2-bar"
_ENGINE = "engine-w2-bar"
_SYMBOLS = ("AAA",)
#: ATR real inyectado (2 % de 100): el stop estructural nace en ``100 − 1.5×2 = 97``.
_ATR = 2.0
#: Precio que rompe ese stop (una salida DENTRO de la barra).
_BREAK = 96.0
#: Turnos D1 del escenario base (todos dentro de la MISMA barra).
_TURNS = 4


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")
    # D3: medir ANTES de vetar. El veto de ATR debe partir del default (off).
    monkeypatch.delenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", raising=False)


def _edge_source(value: float = 0.9) -> Any:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


class _MoneyApplier:
    """Applier hermético: confirma cada fill una sola vez (modo dinero, sin caja real)."""

    async def __call__(self, _execution: Any) -> bool:
        return True


class _CountingAutoStore(InMemoryAutoEngineStore):
    """Espejo durable del motor que CUENTA latidos: ``Δ record_tick`` debe ser 0."""

    def __init__(self) -> None:
        super().__init__()
        self.ticks_written = 0

    async def record_tick(self, tick: AutoEngineTickInput) -> None:
        self.ticks_written += 1
        await super().record_tick(tick)


def _always_buy(symbol: str) -> DecisionPackage:
    """La señal de la barra se re-emite en CADA turno (el caso que infla embudo y journal)."""
    return DecisionPackage(action="BUY", instrument_id=symbol, quantity=250.0)


class _Scenario:
    """Un camino del A/B: worker, stores y el reloj mutable del escenario."""

    def __init__(self, *, prices: dict[str, float], decider: Any) -> None:
        self.prices = prices
        self.auto_store = _CountingAutoStore()
        self.exec_store = InMemoryExecutionEventStore()
        self.reservations = InMemoryReservationStore()
        self._now = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
        self.worker = AutoSimulationWorker(
            clock=self._clock,
            engine_id=_ENGINE,
            account_id=_ACCOUNT,
            sector_source=lambda _symbol: "tech",
            liquidity_source=lambda _symbol: 1_000_000.0,
            edge_source=_edge_source(),
            atr_source=lambda _symbol: _ATR,
            price_script=lambda symbol, _minute: prices[symbol],
            finance_applier=_MoneyApplier(),
            exec_store=self.exec_store,
            position_store=InMemorySimAutoPositionStore(),
            reservation_store=self.reservations,
            exit_order_store=InMemoryExitOrderStore(),
            auto_store=self.auto_store,
            decider=decider,
        )

    def _clock(self) -> datetime:
        """Un minuto por llamada (como ``step_minute_clock``), con salto de barra a mano."""
        self._now = self._now + timedelta(minutes=1)
        return self._now

    def jump_to(self, when: datetime) -> None:
        """Salta a otro día (cambio de barra D1) sin tocar el resto del reloj."""
        self._now = when

    async def turn(self) -> Any:
        return await self.worker.real_turn(
            exec_store=self.exec_store,
            auto_store=self.auto_store,
            finance_applier=None,
            account_id=_ACCOUNT,
            reservation_store=self.reservations,
        )

    async def turns(self, count: int = _TURNS) -> list[Any]:
        return [await self.turn() for _ in range(count)]


def _control(scenario: _Scenario, monkeypatch: pytest.MonkeyPatch) -> None:
    """``OLD``: el turno durable con el short-circuit APAGADO (el bucle de 60 s literal)."""
    monkeypatch.setattr(scenario.worker, "_v2_bar_short_circuit_applies", lambda: False)


def _count_io(worker: AutoSimulationWorker, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Cuenta las lecturas de DATO del turno (lo que la Fase A debe dejar de pagar)."""
    counts = {"refresh_regime": 0, "trade_context": 0, "open_orders": 0}

    def _wrap(name: str, key: str) -> None:
        original = getattr(worker, name)

        async def _counted(*args: Any, **kwargs: Any) -> Any:
            counts[key] += 1
            return await original(*args, **kwargs)

        monkeypatch.setattr(worker, name, _counted)

    _wrap("_v2_refresh_regime", "refresh_regime")
    _wrap("_v2_refresh_trade_context", "trade_context")
    _wrap("_v2_refresh_open_orders", "open_orders")
    return counts


def _daily(worker: AutoSimulationWorker) -> Any:
    """Informe del día agregado con las mediciones del worker (el «evidence» de Fase A)."""
    return build_auto_daily_report(
        rows=worker.journal_pairs(),
        atr_sources=worker.atr_source_counts(),
        net_cash_delta=Decimal("0"),
        ledger_remainder=Decimal("0"),
        opportunities=worker.opportunity_rows(),
        measurements=worker.operation_measurements(),
        seen=worker.seen_signals(),
    )


def _report(worker: AutoSimulationWorker) -> dict[str, Any]:
    """El informe del día como diccionario (la magnitud que se compara entre caminos)."""
    return _daily(worker).as_dict()


def _management_codes(worker: AutoSimulationWorker) -> list[str]:
    """Motivos de gestión de posición journalizados (payload ``reasonCodes``)."""
    return [
        code
        for entry in worker._v2_journal  # noqa: SLF001
        if entry.payload is not None and entry.event_type == "auto_position_management"
        for code in entry.payload["reasonCodes"]
    ]


# ── A/B de equivalencia estricta ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_same_bar_turns_reuse_the_datum_without_changing_the_daily_report(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Δ = 0`` sobre el informe del día, y el I/O de dato SÍ desaparece.

    Cuatro turnos D1 sobre la MISMA barra con la señal re-emitida en cada uno (el caso que
    infla embudo y journal). El control relee régimen/contexto/órdenes en los cuatro; el
    short-circuit solo en el primero. El informe agregado —embudo, procedencia del ATR,
    journal y atribución por estrategia— debe ser EXACTAMENTE el mismo en los dos.
    """
    prices = {"AAA": 100.0}
    new = _Scenario(prices=prices, decider=_always_buy)
    old = _Scenario(prices=prices, decider=_always_buy)
    _control(old, monkeypatch)
    io_new = _count_io(new.worker, monkeypatch)
    io_old = _count_io(old.worker, monkeypatch)

    new_reports = await new.turns()
    old_reports = await old.turns()

    # (1) El short-circuit se activó: todos los turnos posteriores al primero reutilizan.
    assert new.worker._v2_bar_short_circuit_ticks == _TURNS - 1, (  # noqa: SLF001
        "los turnos posteriores al primero deben reutilizar el dato de barra"
    )
    assert old.worker._v2_bar_short_circuit_ticks == 0  # noqa: SLF001

    # (2) El I/O de DATO desaparece de los turnos reutilizados (no es un no-op silencioso).
    assert io_new == {"refresh_regime": 1, "trade_context": 1, "open_orders": 1}, io_new
    assert io_old == {
        "refresh_regime": _TURNS,
        "trade_context": _TURNS,
        "open_orders": _TURNS,
    }, io_old

    # (3) El heartbeat NO se toca: mismo número de latidos durables en los dos caminos.
    assert new.auto_store.ticks_written == old.auto_store.ticks_written == _TURNS

    # (4) Δ evidence = 0: el informe del día es el MISMO (embudo, ATR, journal, atribución).
    assert _report(new.worker) == _report(old.worker)

    # (5) Δ fills = Δ cycles = Δ settlements = Δ PnL = Δ reservas = 0.
    assert [r.fills for r in new_reports] == [r.fills for r in old_reports]
    assert new.worker.open_symbols == old.worker.open_symbols
    assert dict(new.worker._open) == dict(old.worker._open)  # noqa: SLF001
    assert new.worker._v2_reservations == old.worker._v2_reservations == ()  # noqa: SLF001
    assert new.worker.seen_signals() == old.worker.seen_signals() > 0
    assert new.worker.atr_source_counts() == old.worker.atr_source_counts()


@pytest.mark.asyncio
async def test_an_exit_inside_the_bar_is_never_short_circuited(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La PROTECCIÓN no se salta: el stop roto a mitad de barra vende en ambos caminos.

    Es la esquina que impide que el ahorro sea fail-open. El turno 2 reutiliza el dato de
    barra para DECIDIR (la señal de la barra ya está consumida), pero el bucle por símbolo
    sigue corriendo: el precio rompe el stop estructural (97) dentro de la MISMA barra y la
    salida se materializa en los DOS caminos, con el mismo motivo y el mismo informe.
    """
    prices = {"AAA": 100.0}
    new = _Scenario(prices=prices, decider=_always_buy)
    old = _Scenario(prices=prices, decider=_always_buy)
    _control(old, monkeypatch)

    await new.turn()
    await old.turn()
    assert tuple(new.worker.open_symbols) == tuple(old.worker.open_symbols) == ("AAA",), (
        "el turno 1 abre"
    )

    prices["AAA"] = _BREAK  # el stop estructural (97) cae DENTRO de la barra
    new_exit = await new.turn()
    old_exit = await old.turn()
    prices["AAA"] = 100.0
    await new.turn()
    await old.turn()

    assert not new.worker.open_symbols and not old.worker.open_symbols, "el libro cierra"
    assert new_exit.fills == old_exit.fills > 0, "el stop roto debe vender en el mismo turno"

    # El motivo de cierre del día es el stop estructural, y el journal de gestión coincide.
    new_day = _daily(new.worker)
    assert dict(new_day.exit_reasons) == {"structural_stop": 1}, new_day.as_dict()
    assert new_day.exits == 1
    assert _management_codes(new.worker) == _management_codes(old.worker)

    # Y el turno del stop SÍ reutilizó el dato de barra: la protección convivió con el ahorro.
    assert new.worker._v2_bar_short_circuit_ticks >= 2, (  # noqa: SLF001
        "el ahorro de I/O debe ser compatible con la gestión de posición dentro de la barra"
    )
    assert _report(new.worker) == _report(old.worker)


# ── Fail-closed en los bordes ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_bar_with_an_unconsumed_approval_keeps_re_reading(
    v2_env: None,
) -> None:
    """Barra con aprobación SIN consumir ⇒ no se reutiliza el dato (el reintento observa).

    El fill se ancla al minuto, así que una aprobación cuyo fill no materializó todavía
    PUEDE consumirse en el turno siguiente: reutilizar el dato ahí perdería la entrada. La
    vía fail-closed es no reutilizar mientras quede una aprobación viva.
    """
    scenario = _Scenario(prices={"AAA": 100.0}, decider=_always_buy)
    await scenario.turn()
    # El turno dejó la barra liquidada: el dato de barra queda acreditado.
    assert scenario.worker._v2_bar_plan_bar != ""  # noqa: SLF001

    # Las TRES condiciones de la guarda, una a una (el seam lo enciende ``real_turn``, así
    # que aquí se fija a mano para aislar el predicado).
    scenario.worker._v2_bar_short_circuit = True  # noqa: SLF001
    assert scenario.worker._v2_bar_short_circuit_applies() is True  # noqa: SLF001
    scenario.worker._v2_bar_pending = True  # noqa: SLF001
    assert scenario.worker._v2_bar_short_circuit_applies() is False, (  # noqa: SLF001
        "una aprobación viva dentro de la barra impide reutilizar el dato"
    )
    scenario.worker._v2_bar_pending = False  # noqa: SLF001
    scenario.worker._v2_bar_plan_bar = ""  # noqa: SLF001
    assert scenario.worker._v2_bar_short_circuit_applies() is False, (  # noqa: SLF001
        "sin dato de barra acreditado no hay nada que reutilizar"
    )


@pytest.mark.asyncio
async def test_the_approval_that_never_filled_is_what_blocks_the_reuse(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La guarda de pendiente la ENCIENDE el propio turno, no una bandera del test.

    Se veta la liquidación (la orden no materializa ningún chunk): la aprobación queda
    emitida y su señal sin consumir, así que el turno siguiente NO puede reutilizar el dato
    de barra — hay un reintento observable dentro de la barra que perdería la entrada. El
    contador de I/O lo mide: ningún turno se ahorra la lectura.
    """
    import bolsa_api.background.auto_simulation_worker as worker_module

    class _NoFill:
        async def __call__(self, _store: Any, **kwargs: Any) -> tuple[Any, dict[str, str]]:
            from bolsa_application.simulated_broker import SimulatedOrderResult
            from bolsa_application.simulated_settlement import auto_venue_order_id

            return (
                SimulatedOrderResult(
                    venue_order_id=auto_venue_order_id(
                        engine_id=kwargs.get("engine_id") or _ENGINE,
                        account_id=kwargs.get("account_id"),
                        instrument_id=str(kwargs["instrument_id"]),
                        side=str(kwargs["side"]),
                        logical_order_id=kwargs.get("logical_order_id") or "logical",
                    ),
                    status="rejected",
                    reason="market_out",
                    scheduled_gap_seconds=0.3,
                    fills=(),
                    queue_event="ok",
                    cumulative_filled_quantity=Decimal("0"),
                ),
                {},
            )

    monkeypatch.setattr(worker_module, "submit_simulated_order", _NoFill())
    scenario = _Scenario(prices={"AAA": 100.0}, decider=_always_buy)
    io = _count_io(scenario.worker, monkeypatch)

    await scenario.turns(2)

    assert scenario.worker._v2_bar_pending is True, (  # noqa: SLF001
        "una aprobación sin consumir debe bloquear la reutilización del dato de barra"
    )
    assert scenario.worker._v2_bar_short_circuit_ticks == 0, (  # noqa: SLF001
        "ningún turno puede ahorrarse la lectura mientras haya una aprobación viva"
    )
    assert io["refresh_regime"] == 2, io


@pytest.mark.asyncio
async def test_changing_the_bar_re_reads_the_datum(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Al cambiar de barra el dato se relee: la memoria de barra no sobrevive al reloj.

    La deduplicación de señal y el consumo viven ACOTADOS a su barra. Si la barra nueva
    heredara el «ya cargado», el motor dejaría de decidir el día siguiente.
    """
    scenario = _Scenario(prices={"AAA": 100.0}, decider=_always_buy)
    io = _count_io(scenario.worker, monkeypatch)
    await scenario.turns()
    assert io["refresh_regime"] == 1, io
    assert scenario.worker._v2_bar_plan_bar == scenario.worker._v2_current_bar_start()  # noqa: SLF001

    scenario.jump_to(datetime(2026, 9, 16, 9, 0, tzinfo=UTC))
    await scenario.turn()
    assert io["refresh_regime"] == 2, "la barra nueva vuelve a leer el dato"
    assert scenario.worker._v2_bar_plan_bar == scenario.worker._v2_current_bar_start()  # noqa: SLF001
    # Y dentro de la barra nueva el ahorro vuelve a aplicar (el estado se rearma, no se pierde).
    scenario.worker._v2_bar_short_circuit = True  # noqa: SLF001
    assert scenario.worker._v2_bar_short_circuit_applies() is True  # noqa: SLF001
    scenario.worker._v2_bar_short_circuit = False  # noqa: SLF001
    assert scenario.worker._v2_bar_short_circuit_ticks == 3, (  # noqa: SLF001
        "los cuatro turnos de la barra anterior reutilizaron el dato en tres de ellos; el "
        "turno de la barra nueva RELEYÓ (no cuenta como reutilizado)"
    )
