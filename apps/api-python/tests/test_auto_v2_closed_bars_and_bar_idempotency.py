"""V2.88.16 (``W3``) — frontera de barras CERRADAS e idempotencia INTRA-BARRA (hermético, sin PG).

El incremento ``W3`` mueve **dos** cosas del tiempo del motor y ninguna de las dos es
observable con un test de caja blanca del helper (que sólo probaría el helper):

1. **NO lookahead**: la decisión de la barra ``B`` se alimenta con las barras **CERRADAS**
   (``<= B-1``). La frontera la aporta el motor (``_v2_closed_bar_as_of``) y la aplica el
   cargador que el motor COMPONE (``make_closed_bar_loader``) para régimen, ATR y señal. Aquí
   se comprueba en los dos planos: el valor de la frontera a lo largo del reloj y que la
   ventana que produce el cargador (el MISMO objeto, con el MISMO provider de frontera) deja
   fuera la barra EN CURSO — incluso si el port de barras no soporta ``date_to`` (la guardia
   en cliente no puede depender del repositorio).
2. **Idempotencia intra-barra**: el desenlace de mercado de la barra es ÚNICO. Donde el ancla
   vieja (``seed = minuto``) re-sorteaba la cola cada 60 s — y un reintento dentro de la barra
   podía LLENAR lo que el turno anterior rechazó —, el ancla de barra reproduce el MISMO
   veredicto: el reintento no puede cambiar lo que la barra ya decidió.

El segundo test se construye con la propiedad INVERSA a propósito: se busca un instrumento y
una barra donde el ancla de barra **rechaza** y el ancla de minuto (minuto 2) **llenaría**. Si
alguien devuelve el seed al minuto, el reintento llena y el test rompe (``M280``); si alguien
congela el tick (``M281``), la identidad de dos barras distintas colisiona y también rompe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.closed_bars import (
    bar_tick,
    last_closed_bar_day,
    make_closed_bar_loader,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.exit_order_store import InMemoryExitOrderStore
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore
from bolsa_application.reservation_store import InMemoryReservationStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimConsumedSignalStore,
    InMemorySimFillFinanceContextStore,
)
from bolsa_application.simulated_broker import fill_seed, simulated_fill_schedule

ACCOUNT_ID = "acc-v28816-bars"
ENGINE_ID = "auto-sim-v28816-bars"

#: Reloj del arnés: un instante cualquiera DENTRO de la barra ``2026-09-18`` (ancla a
#: medianoche UTC). La frontera de barras cerradas de esa barra es ``2026-09-17``.
_CLOCK_DAY = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
_CLOSED_DAY = "2026-09-17"
_NEXT_CLOSED_DAY = "2026-09-18"

#: Cantidad de la barrida del segundo test: el reparto de tranchas depende SOLO del contexto
#: de mercado (seed/side/instrument), nunca de la cantidad.
_PROBE_QTY = Decimal("100")
_FILL_CHUNKS = 4


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v28816_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


# ── Port de barras en memoria (el port que el motor lee de verdad) ────────────────────


@dataclass(frozen=True)
class _Bar:
    timestamp: str
    close: float = 100.0


class _OhlcvPort:
    """``get_bars`` en memoria; ``supports_date_to=False`` finge un port de firma reducida."""

    def __init__(self, bars: dict[str, list[_Bar]], *, supports_date_to: bool = True) -> None:
        self._bars = bars
        self._supports_date_to = supports_date_to
        self.calls: list[dict[str, Any]] = []

    async def get_bars(
        self,
        symbol: str,
        *,
        timeframe: Any = None,
        limit: int | None = None,
        date_to: str | None = None,
    ) -> list[_Bar]:
        self.calls.append({"symbol": symbol, "date_to": date_to, "limit": limit})
        if date_to is not None and not self._supports_date_to:
            raise TypeError("get_bars() got an unexpected keyword argument 'date_to'")
        bars = list(self._bars.get(str(symbol), []))
        if date_to is not None:
            bars = [b for b in bars if b.timestamp[:10] <= str(date_to)]
        return bars[: int(limit)] if limit else bars


def _bars_for(*days: str) -> dict[str, list[_Bar]]:
    return {"AAA": [_Bar(timestamp=f"{day}T21:00:00+00:00") for day in days]}


# ── Worker mínimo sobre espejos en memoria ────────────────────────────────────────────


class _ClockHolder:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _Stores:
    def __init__(self) -> None:
        self.exec_store = InMemoryExecutionEventStore()
        self.contexts = InMemorySimFillFinanceContextStore()
        self.reservations = InMemoryReservationStore()
        self.positions = InMemorySimAutoPositionStore()
        self.exit_orders = InMemoryExitOrderStore()
        self.kill_state = InMemoryKillSwitchStore()
        self.consumed = InMemorySimConsumedSignalStore()


async def _apply_true(_event: object) -> bool:
    return True


def _worker(
    stores: _Stores, *, clock: Any, decider: _Prov, extra: dict[str, Any] | None = None
) -> AutoSimulationWorker:
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _edge(_ref: str, _account: str | None) -> float | None:
        return 0.9

    kwargs: dict[str, Any] = {
        "clock": clock,
        "exec_store": stores.exec_store,
        "context_store": stores.contexts,
        "reservation_store": stores.reservations,
        "position_store": stores.positions,
        "exit_order_store": stores.exit_orders,
        "kill_switch_store": stores.kill_state,
        "consumed_signal_store": stores.consumed,
        "account_id": ACCOUNT_ID,
        "engine_id": ENGINE_ID,
        "finance_applier": _apply_true,
        "price_script": lambda _symbol, _tick: 100.0,
        "decider": decider,
        "sector_source": lambda _symbol: "tech",
        "liquidity_source": lambda _symbol: 1_000_000.0,
        "atr_source": lambda _symbol: 2.0,
        "edge_source": EdgeReportSource(reader=_edge),
    }
    kwargs.update(extra or {})
    return AutoSimulationWorker(**kwargs)


# ══ 1 · NO LOOKAHEAD: la decisión nunca ve la barra en curso ══════════════════════════


def test_the_closed_bar_boundary_is_the_bar_before_the_one_in_course(
    v28816_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La frontera del motor es ``B-1``, CONSTANTE dentro de la barra y avanza al cambiarla."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    holder = _ClockHolder(_CLOCK_DAY)
    worker = _worker(_Stores(), clock=holder, decider=lambda _s: DecisionPackage("HOLD", "AAA", 0))

    # Dentro de la barra 2026-09-18 (a cualquier hora del día) la frontera es 2026-09-17.
    assert worker._v2_bar_tick() == bar_tick(_CLOCK_DAY, "1d")  # noqa: SLF001 — seam medido.
    for hour in (0, 9, 23):
        holder.now = _CLOCK_DAY.replace(hour=hour)
        worker._advance()  # noqa: SLF001 — el turno refresca el reloj del motor.
        assert worker._v2_closed_bar_as_of() == _CLOSED_DAY, hour  # noqa: SLF001

    # Al cruzar la medianoche cambia la barra Y la frontera: la barra 09-18 pasa a estar
    # CERRADA (es lo único que puede alimentar la decisión del 09-19).
    holder.now = datetime(2026, 9, 19, 0, 30, tzinfo=UTC)
    worker._advance()  # noqa: SLF001
    assert worker._v2_bar_tick() == bar_tick(holder.now, "1d")  # noqa: SLF001
    assert worker._v2_closed_bar_as_of() == _NEXT_CLOSED_DAY  # noqa: SLF001


@pytest.mark.asyncio
async def test_the_loader_the_engine_composes_excludes_the_bar_in_course(
    v28816_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con el MISMO cargador y la MISMA frontera del motor, la barra en curso queda fuera."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    holder = _ClockHolder(_CLOCK_DAY)
    worker = _worker(_Stores(), clock=holder, decider=lambda _s: DecisionPackage("HOLD", "AAA", 0))

    bars = _bars_for("2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19")
    port = _OhlcvPort(bars)
    loader = make_closed_bar_loader(port, ("AAA",), worker._v2_closed_bar_as_of)  # noqa: SLF001

    snapshot = await loader()
    assert [bar.timestamp[:10] for bar in snapshot["AAA"]] == ["2026-09-16", "2026-09-17"], (
        "la decisión del 09-18 sólo puede ver las barras cerradas (<= 09-17): ni la barra en "
        "curso (09-18) ni el futuro (09-19) entran en la ventana"
    )

    # La frontera es un PROVIDER: al cambiar de barra el cargador se mueve sin recomponerse.
    holder.now = datetime(2026, 9, 19, 0, 30, tzinfo=UTC)
    worker._advance()  # noqa: SLF001 — el turno refresca el reloj del motor.
    snapshot = await loader()
    assert [bar.timestamp[:10] for bar in snapshot["AAA"]] == [
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
    ], "al cerrarse la barra 09-18 entra en la ventana, y la 09-19 sigue fuera"

    # El repositorio real filtra por ``date_to``; la guardia en CLIENTE no puede depender de
    # él: con un port de firma reducida la ventana es la MISMA (lee de más, no decide de más).
    reduced = _OhlcvPort(bars, supports_date_to=False)
    reduced_snapshot = await make_closed_bar_loader(
        reduced, ("AAA",), worker._v2_closed_bar_as_of  # noqa: SLF001
    )()
    assert [bar.timestamp[:10] for bar in reduced_snapshot["AAA"]] == [
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
    ]


@pytest.mark.asyncio
async def test_an_unreadable_boundary_or_undated_bar_yields_an_EMPTY_window(
    v28816_env: None,
) -> None:
    """Fail-closed: sin frontera expresable (o con barra sin fecha) NO hay ventana ⇒ HOLD."""
    moment = _CLOCK_DAY
    # Granularidad sub-diaria: la frontera «día de la última barra cerrada» no es expresable
    # a día, así que el motor NO decide (nunca degrada a «las barras de hoy»: eso es el
    # lookahead que ``W3`` cierra).
    assert last_closed_bar_day(moment, "1m") == ""
    assert last_closed_bar_day(moment, "1h") == ""

    port = _OhlcvPort({"AAA": [_Bar(timestamp=f"{_CLOSED_DAY}T21:00:00+00:00"), _Bar("")]})
    assert await make_closed_bar_loader(port, ("AAA",), "")() == {}
    undated_only = _OhlcvPort({"AAA": [_Bar("")]})
    assert await make_closed_bar_loader(undated_only, ("AAA",), _CLOSED_DAY)() == {}, (
        "una barra sin fecha legible se DESCARTA: jamás se asume que es del pasado"
    )


def test_the_runtime_composes_regime_and_atr_with_the_closed_bar_boundary(
    v28816_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cableado (no promesa): régimen y ATR reciben la frontera del motor como provider."""
    import bolsa_api.background.auto_simulation_worker as worker_mod

    real = worker_mod.make_closed_bar_loader
    seen: list[dict[str, Any]] = []

    def _spy(ohlcv: Any, symbols: Any, as_of: Any, **kwargs: Any) -> Any:
        seen.append({"symbols": tuple(symbols), "as_of": as_of, "kwargs": kwargs})
        return real(ohlcv, symbols, as_of, **kwargs)

    monkeypatch.setattr(worker_mod, "make_closed_bar_loader", _spy)
    boundary = lambda: _CLOSED_DAY  # noqa: E731 — el provider que expone el motor.

    worker_mod._compose_atr_source(object(), watch=("AAA",), as_of=boundary)
    worker_mod._compose_regime_source(object(), watch=("AAA",), as_of=boundary)

    assert len(seen) == 2, "régimen y ATR deben componerse AMBOS con la frontera cerrada"
    assert all(entry["as_of"] is boundary for entry in seen), seen
    assert [entry["symbols"] for entry in seen] == [("AAA",), ("AAA",)], seen


# ══ 2 · IDEMPOTENCIA INTRA-BARRA: el desenlace de la barra es ÚNICO ═══════════════════


def _rejected_on_the_bar_but_filled_by_minute(prefix: str) -> str:
    """Id determinista: BUY **rechazado** con el ancla de barra y LLENO con el ancla de minuto.

    La propiedad es la que hace del test una medida y no una narración: si alguien devuelve el
    seed al minuto (``M280``), el reintento intra-barra del segundo turno LLENA ⇒ el invariante
    «el reintento no puede cambiar el veredicto de la barra» rompe de verdad.
    """
    tick = bar_tick(_CLOCK_DAY, "1d")

    def _probe(seed: int, candidate: str) -> Any:
        return simulated_fill_schedule(
            instrument_id=candidate,
            side="buy",
            quantity=_PROBE_QTY,
            venue_order_id=f"probe-{candidate}-{seed}",
            seed=seed,
            fill_chunks=_FILL_CHUNKS,
            base_mid=100.0,
        )

    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        if _probe(fill_seed(tick, candidate), candidate).status not in {"rejected", "unknown"}:
            continue
        # ``_minute`` del primer y segundo turno (``_advance`` incrementa por turno).
        if _probe(fill_seed(1, candidate), candidate).status in {"rejected", "unknown"}:
            if _probe(fill_seed(2, candidate), candidate).status in {"filled", "partial"}:
                return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} rechaza con el ancla de BARRA y llena con el "
        "ancla de MINUTO (turnos 1 y 2); revisar ``draw_queue_noise``"
    )


def _buy_once(symbol: str, quantity: float = 250.0) -> _Prov:
    def _d(_symbol: str) -> DecisionPackage:
        if _symbol == symbol:
            return DecisionPackage(
                action="BUY",
                instrument_id=symbol,
                quantity=quantity,
                source="active-strategy:bars-1",
            )
        return DecisionPackage(action="HOLD", instrument_id=_symbol, quantity=0)

    return _d


def _partial_buy_instrument_id(prefix: str) -> str:
    """Id determinista cuyo BUY llena PARCIAL (≥2 tranchas) en la barra del arnés.

    El fill parcial es lo que deja posición y cola de reserva vivas: sin él, «el reintento no
    duplica» pasaría por vacío (no habría nada que duplicar).
    """
    tick = bar_tick(_CLOCK_DAY, "1d")
    for n in range(8192):
        candidate = f"{prefix}{n:010d}"
        result = simulated_fill_schedule(
            instrument_id=candidate,
            side="buy",
            quantity=_PROBE_QTY,
            venue_order_id=f"probe-{candidate}",
            seed=fill_seed(tick, candidate),
            fill_chunks=_FILL_CHUNKS,
            base_mid=100.0,
        )
        if result.status == "partial" and len(result.fills) >= 2:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} tiene BUY PARCIAL en la barra del arnés"
    )


async def _turn(worker: AutoSimulationWorker, stores: _Stores, auto_store: Any) -> None:
    """Un turno DURABLE (``real_turn``): es donde viven el claim y el settlement."""
    await worker.real_turn(
        exec_store=stores.exec_store,
        auto_store=auto_store,
        finance_applier=None,
        account_id=ACCOUNT_ID,
        reservation_store=stores.reservations,
    )


@pytest.mark.asyncio
async def test_an_intra_bar_retry_reuses_the_bar_anchor_and_cannot_double_the_day(
    v28816_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El reintento intra-barra reusa el ancla de la barra: mismo seed, cero doble efecto.

    Dos fases, las dos medidas en la costura REAL del venue (``submit_simulated_order``):

    * **A · la barra rechaza**: tres turnos (minutos 1..3, MISMA barra) proponen la entrada y
      la cola la rechaza. El reintento SÍ llega al venue (si no, el test no mide nada) y lo
      hace con el **mismo seed y el mismo ``order_id``** que el primer turno: el ancla es la
      barra, no el minuto. Con el seed por minuto (``M280``) el segundo turno sería un sorteo
      NUEVO — el instrumento elegido llena en el minuto 2 — y el dinero se movería dentro de
      la barra que ya había decidido.
    * **B · la barra llena PARCIAL**: con la posición parcial ya materializada, el reintento
      intra-barra **no vuelve a emitir** (el compromiso determinista de la barra está vivo):
      una sola llamada al venue y la posición no crece. Es la mitad financiera del invariante:
      «cero doble efecto», no «cero reintento».

    Cierra con el cruce de barra: ancla distinta ⇒ identidad distinta (sin colisión) y sorteo
    nuevo (``M281``: un tick congelado repartiría el mismo desenlace a todas las barras).
    """
    import bolsa_api.background.auto_simulation_worker as worker_mod
    from bolsa_application.auto_engine_state_store import InMemoryAutoEngineStore

    calls: list[dict[str, Any]] = []
    real_submit = worker_mod.submit_simulated_order

    async def _spy(store: Any, **kwargs: Any) -> Any:
        calls.append({key: kwargs.get(key) for key in ("seed", "order_id", "logical_order_id")})
        return await real_submit(store, **kwargs)

    monkeypatch.setattr(worker_mod, "submit_simulated_order", _spy)

    # ── FASE A · la barra RECHAZA la entrada ─────────────────────────────────────────
    rejected = _rejected_on_the_bar_but_filled_by_minute("inst-v28816-rej-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", rejected)
    stores_a = _Stores()
    auto_a = InMemoryAutoEngineStore()
    _start, clock_a = step_minute_clock(_CLOCK_DAY)
    worker_a = _worker(stores_a, clock=clock_a, decider=_buy_once(rejected))

    for _ in range(3):
        await _turn(worker_a, stores_a, auto_a)

    assert len(calls) >= 2, (
        "el escenario exige un reintento intra-barra que LLEGUE al venue (si el engine lo "
        "veta antes, el test no mide el ancla temporal)"
    )
    assert len({call["seed"] for call in calls}) == 1, (
        "el ancla temporal del fill es la BARRA: el seed no puede cambiar entre minutos de "
        f"la misma barra (con el seed por minuto, el reintento llenaría): {calls}"
    )
    assert len({str(call["order_id"]) for call in calls}) == 1, calls
    assert worker_a._v2_bar_tick() == bar_tick(_CLOCK_DAY, "1d")  # noqa: SLF001
    assert worker_a._v2_closed_bar_as_of() == _CLOSED_DAY  # noqa: SLF001
    assert worker_a._open.get(rejected, Decimal("0")) == 0, (  # noqa: SLF001
        "la barra rechazó la orden: el reintento NO puede materializarla (el desenlace del "
        "venue es único por barra)"
    )

    # ── FASE B · la barra llena PARCIAL (y el reintento no duplica) ───────────────────
    calls.clear()
    partial = _partial_buy_instrument_id("inst-v28816-part-")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", partial)
    stores_b = _Stores()
    auto_b = InMemoryAutoEngineStore()
    _start_b, clock_b = step_minute_clock(_CLOCK_DAY)
    worker_b = _worker(stores_b, clock=clock_b, decider=_buy_once(partial))

    await _turn(worker_b, stores_b, auto_b)
    held = worker_b._open.get(partial, Decimal("0"))  # noqa: SLF001
    assert held > 0, "la fase B necesita un fill PARCIAL materializado"
    assert held < Decimal("250"), f"el fill debe ser parcial (no completo): {held}"
    calls_after_open = len(calls)

    for _ in range(2):
        await _turn(worker_b, stores_b, auto_b)

    assert len(calls) == calls_after_open == 1, (
        "con el compromiso de la barra VIVO, el reintento intra-barra no vuelve a emitir: "
        f"una sola llamada al venue ({len(calls)})"
    )
    assert worker_b._open.get(partial, Decimal("0")) == held, (  # noqa: SLF001
        f"el reintento intra-barra no puede duplicar la posición: {worker_b._open}"
    )
    live = await stores_b.reservations.list_live(ACCOUNT_ID, limit=100)
    assert len(live) == 1 and live[0].instrument_id == partial, (
        "el compromiso de la barra sigue siendo UNO (no uno por reintento)"
    )

    # ── Cruce de barra: ancla distinta ⇒ identidad distinta (sin colisión) ────────────
    holder = _ClockHolder(_CLOCK_DAY + timedelta(days=1))
    worker_b._clock = holder  # noqa: SLF001 — el reloj del motor se mueve a la barra nueva.
    worker_b._advance()  # noqa: SLF001
    next_tick = worker_b._v2_bar_tick()  # noqa: SLF001
    assert next_tick == bar_tick(holder.now, "1d")
    assert next_tick != bar_tick(_CLOCK_DAY, "1d"), (
        "una barra distinta NO puede compartir el tick (M281)"
    )
    assert fill_seed(next_tick, partial) != fill_seed(bar_tick(_CLOCK_DAY, "1d"), partial), (
        "cada barra estrena su propio sorteo de mercado (un tick congelado lo repartiría)"
    )
    assert worker_b._v2_closed_bar_as_of() == "2026-09-18"  # noqa: SLF001


# ══ 3 · W4 (paso 2b) · la foto del PRECIO es la del tick de BARRA ══════════════════════


@pytest.mark.asyncio
async def test_every_price_read_in_a_bar_shares_the_bar_tick(
    v28816_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``W4``/paso ``2b``: TODAS las lecturas de precio usan el tick de BARRA, no el minuto.

    El contrato de ``PriceScript`` (``W3``) fija que el ``tick`` que recibe el proveedor es el
    de la **barra** (estable dentro de ella), para que la referencia de un reintento
    intra-barra sea la MISMA. El paso ``2b`` cierra la incoherencia que quedó a medias: la
    decisión y el *mark* leían ``self._minute`` (que avanza cada 60 s) mientras el *fill* ya
    usaba el tick de barra ⇒ dos precios de instantes distintos dentro del mismo tick.

    El script REGISTRA el tick que recibe y devuelve un precio dependiente de él: si una
    lectura vuelve al minuto (``M292``), el registro deja de ser de un solo tick.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    holder = _ClockHolder(_CLOCK_DAY)
    seen: list[int] = []

    def _script(_symbol: str, tick: int) -> float:
        seen.append(int(tick))
        return 100.0

    worker = _worker(
        _Stores(),
        clock=holder,
        decider=lambda symbol: DecisionPackage("BUY", symbol, 200.0),
        extra={"price_script": _script},
    )
    await worker.auto_turn()
    # Segundo turno DENTRO de la misma barra (otra hora del mismo día): el ancla no se mueve.
    holder.now = _CLOCK_DAY.replace(hour=10)
    await worker.auto_turn()

    expected = bar_tick(_CLOCK_DAY, "1d")
    assert seen, "un turno con candidata LEE precio (si no, el test no mediría nada)"
    assert set(seen) == {expected}, (
        "todas las lecturas de la barra comparten el tick de barra "
        f"({expected}), no el minuto: {sorted(set(seen))}"
    )

