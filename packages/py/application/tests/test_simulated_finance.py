"""V2.22 / A9 (last gap) — hermético de la finance SIM-ONLY para fills AUTO.

Sin PG: ejercita el tornillo ``simulated_finance`` por el lado puro/mapper +
``InMemoryExecutionEventStore`` + un executor de ExecuteTrade *fake* (captura la
``idempotency_key``/args) para probar, de forma determinista:

* mapping puro: ``sim_fill_finances`` / ``resolve_execution_finance`` dan UN
  ``SimulatedFillFinance`` por fill materializable (price/qty del schedule), venues OK;
  un venue LIVE no abre dinero (fail-closed) y la guarda ``guard_sim_only_venue``
  bloquea cualquier venue no-AUTO.
* idempotencia por fill: aplicar el MISMO ``execution_id`` dos veces (CAS/lease de
  ``apply_execution_financial_once``) efectúa el ExecuteTrade-fake UNA sola vez y la 2ª
  devuelve ``already_applied``; la ``idempotency_key`` usada es la
  ``simulated_idempotency_key`` canónica (nunca otra).
* finance SIM-ONLY / no-LIVE: un venue {paper, simulated} sí materializa; cualquier
  intento en venue live queda fuera del mapper y del applier.
* invariante del dominio sobre un mini-día determinista (compra qty@px, vende @px) con
  la carpeta pura ``sim_roundtrip_accounting``: el libro con dinero real no-degenerado
  cumple ``equity == initial + realized`` (lo que el aggregator M7 delega a
  ``assert_equity_invariant``).
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

import pytest

from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_execution_financial_once,
)
from bolsa_application.simulated_broker import simulated_fill_schedule
from bolsa_application.simulated_finance import (
    SimulatedFillFinance,
    build_simulated_execute_trade_applier,
    guard_sim_only_venue,
    resolve_execution_finance,
    sim_fill_finances,
    sim_roundtrip_accounting,
)
from bolsa_application.simulated_settlement import simulated_execution_candidates
from bolsa_domain.errors import PermanentRejectionError
from bolsa_domain.lifecycle import LIFECYCLE_CASH, LifecycleAccounting, assert_equity_invariant

_Q = Decimal("100.000000")


class _FakeExecuteTrade:
    """Executor de ExecuteTrade *fake* pero idéntico por shape (graba los args).

    NO es dinero real: solo captura, para el test hermético, qué ExecuteTrade se habría
    hecho por fill (instrument/side/qty/price/account + ``idempotency_key``) y recuerda
    cuántas veces se efectuó CADA key (los duplicados no deben re-efectuarse).
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.effective: set[str] = set()

    async def execute(self, **kwargs: object) -> object:
        key = str(kwargs.get("idempotency_key"))
        self.calls.append(kwargs)
        # idempotencia real del ExecuteTrade por key: un 2º same-key NO dobla.
        ok = key not in self.effective
        if ok:
            self.effective.add(key)
        return ok


def _schedule(side: str, *, seed: int = 7, qty: Decimal = _Q, base_mid: float = 100.0):
    return simulated_fill_schedule(
        instrument_id="AAA",
        side=side,
        quantity=qty,
        venue_order_id=f"sim-{side}-AAA-{seed}",
        seed=seed,
        fill_chunks=3,
        base_mid=base_mid,
    )


def test_mapper_one_finance_per_fill_venue_ok() -> None:
    result = _schedule("buy", qty=_Q)
    fin = sim_fill_finances(
        result, instrument_id="AAA", side="buy", account_id="acc-1", venue="simulated"
    )
    assert len(fin) == len(result.fills)
    for f, fill in zip(fin, result.fills, strict=False):
        assert isinstance(f, SimulatedFillFinance)
        assert f.instrument_id == "AAA"
        assert f.trade_type == "buy"
        assert f.execution_id == fill.execution_id
        assert f.quantity == abs(fill.qty_delta)
        assert f.price == fill.price
        assert f.venue_is_sim_only
        assert f.idempotency_key.startswith("sim-fin-")


def test_mapper_fail_closed_on_live_venue() -> None:
    result = _schedule("sell")
    assert (
        sim_fill_finances(
            result, instrument_id="AAA", side="sell", account_id="acc-1", venue="live"
        )
        == ()
    )
    # La guarda SIM-ONLY también bloquea un venue no-AUTO.
    with pytest.raises(ValueError):
        guard_sim_only_venue("xtb")
    guard_sim_only_venue("simulated")  # sin lanzar.


def test_resolve_execution_finance_matches_or_fails_closed() -> None:
    result = _schedule("buy")
    events = simulated_execution_candidates(
        result,
        instrument_id="AAA",
        account_id="acc-1",
        venue="simulated",
    )
    assert events
    resolved = [
        resolve_execution_finance(
            result,
            execution=ev,
            instrument_id="AAA",
            side="buy",
            account_id="acc-1",
        )
        for ev in events
    ]
    assert all(r is not None for r in resolved)
    # event de otro resultado (no match) → fail-closed None, sin abrir dinero.
    foreign = ExecutionEvent(
        execution_id="foreign#9", order_id="o", venue="SIMULATED", qty=Decimal("1")
    )
    assert (
        resolve_execution_finance(
            result,
            execution=foreign,
            instrument_id="AAA",
            side="buy",
            account_id="acc-1",
        )
        is None
    )
    # venue live sobre el evento → None (nunca abre una vía REAL).
    live_event = ExecutionEvent(
        execution_id="livex#1", order_id="o", venue="LIVE", qty=Decimal("1")
    )
    assert (
        resolve_execution_finance(
            result,
            execution=live_event,
            instrument_id="AAA",
            side="buy",
            account_id="acc-1",
        )
        is None
    )


def _applier_for(result, *, fake: object):
    """Fina applier: ExecuteTrade-seco(idempotente por key) sobre un SIM result."""

    def _resolver(execution: ExecutionEvent) -> SimulatedFillFinance | None:
        return resolve_execution_finance(
            result,
            execution=execution,
            instrument_id="AAA",
            side="buy",
            account_id="acc-1",
        )

    return build_simulated_execute_trade_applier(fake, _resolver)


def test_applier_fail_closed_on_foreign_event_and_live_venue() -> None:
    fake = _FakeExecuteTrade()
    result = _schedule("buy")

    def _resolver(execution: ExecutionEvent) -> SimulatedFillFinance | None:
        # Devuelve None para lo que no sea un fill de ESTE schedule A en venue auto
        # (fail-closed): nunca abre dinero sin un contexto viable.
        return resolve_execution_finance(
            result, execution=execution, instrument_id="AAA", side="buy", account_id="acc-1"
        )

    applier = build_simulated_execute_trade_applier(fake, _resolver)

    async def _go() -> None:
        # Evento ajeno (otro result / no-match) → applier devuelve False (no APPLY).
        foreign = ExecutionEvent(
            execution_id="foreign#1", order_id="o", venue="SIMULATED", qty=Decimal("1")
        )
        assert await applier(foreign) is False
        # Venue LIVE en el evento → mapper → None → applier False (nunca abre REAL).
        live = ExecutionEvent(
            execution_id="sim-buy-AAA-7#1", order_id="o", venue="LIVE", qty=Decimal("1")
        )
        assert await applier(live) is False

    asyncio.run(_go())
    assert fake.calls == []  # ningún ExecuteTrade-fake ocurrió (dinero intacto).


class _ExplodingExecuteTrade:
    """ExecuteTrade que SIEMPRE lanza: simula un fallo transitorio (PG/dominio)."""

    async def execute(self, **kwargs: object) -> object:
        raise RuntimeError("deadlock simulado")


def test_applier_keeps_fail_closed_and_LOGS_the_swallowed_cause(caplog) -> None:
    """FLAKE-1 (2026-09-29): el applier sigue devolviendo ``False`` (nunca APPLIED por
    excepción), pero la CAUSA deja de tragarse.

    Antes, un ``ExecuteTrade`` que lanzaba producía un fill en ``RETRY`` con
    ``error="apply_ineffective"`` y CERO rastro del motivo: un rojo del CI (como el
    intermitente de ``lifecycle-pg``) era indistinguible de un ``None`` del resolver.
    Este gate fija que la traza queda registrada sin cambiar la semántica.
    """
    result = _schedule("buy")
    applier = _applier_for(result, fake=_ExplodingExecuteTrade())
    fill = result.fills[0]
    event = ExecutionEvent(
        execution_id=fill.execution_id,
        order_id="o",
        venue="SIMULATED",
        qty=abs(fill.qty_delta),
    )

    with caplog.at_level(logging.ERROR):
        ok = asyncio.run(applier(event))

    assert ok is False  # contrato intacto: jamás APPLIED por excepción.
    records = [r for r in caplog.records if r.name.endswith("simulated_finance")]
    assert records, "el fallo de ExecuteTrade debe dejar rastro en el log"
    record = records[-1]
    assert record.levelno == logging.ERROR
    assert event.execution_id in record.getMessage()  # el ejecutor sabe QUÉ fill falló
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)  # ...y POR QUÉ (traza completa)
    assert "deadlock simulado" in str(record.exc_info[1])


class _PermanentlyRejectingExecuteTrade:
    """ExecuteTrade que rechaza de forma DETERMINISTA (p.ej. sin acciones)."""

    async def execute(self, **kwargs: object) -> object:
        raise PermanentRejectionError("No tienes suficientes acciones. En cartera: 0.0")


def test_applier_propagates_permanent_rejection_instead_of_swallowing() -> None:
    """OBS-21: un rechazo PERMANENTE del dominio NO se traga como ``False``.

    El applier debe RE-LANZAR ``PermanentRejectionError`` para que el store lo
    clasifique como ``FAILED`` (no reintentable), en vez de devolver ``False`` y que
    ``retryable_on_ineffective`` lo encamine a un ``RETRY`` indefinido. Sigue siendo
    fail-closed: JAMÁS se marca APPLIED por excepción.
    """
    result = _schedule("buy")
    applier = _applier_for(result, fake=_PermanentlyRejectingExecuteTrade())
    fill = result.fills[0]
    event = ExecutionEvent(
        execution_id=fill.execution_id,
        order_id="o",
        venue="SIMULATED",
        qty=abs(fill.qty_delta),
    )

    with pytest.raises(PermanentRejectionError):
        asyncio.run(applier(event))


def test_apply_idempotent_same_fill_effective_once() -> None:
    store = InMemoryExecutionEventStore()
    fake = _FakeExecuteTrade()

    def run() -> list[str]:
        async def _go() -> list[str]:
            result = _schedule("buy")
            outcomes: list[str] = []
            finance = _applier_for(result, fake=fake)
            for ev in simulated_execution_candidates(
                result,
                instrument_id="AAA",
                account_id="acc-1",
                venue="simulated",
            ):
                first = await apply_execution_financial_once(
                    store, execution=ev, apply_finance=finance, owner="t-fin-herm-1"
                )
                outcomes.append(first)
                # reintento del MISMO fill (crash/relaunch) → ya_applied, sin doblar.
                second = await apply_execution_financial_once(
                    store, execution=ev, apply_finance=finance, owner="t-fin-herm-2"
                )
                assert second == "already_applied", second
            return outcomes

        return asyncio.run(_go())

    outcomes = run()
    # Cada fill del resultado se materializó una sola vez (primera pasada => applied).
    assert outcomes and all(o == "applied" for o in outcomes), outcomes
    n_fills = len(outcomes)
    # idempotencia real: cada execution_id se efectuó EXACTAMENTE una vez en el fake.
    assert len(fake.calls) == n_fills
    assert len(fake.effective) == n_fills
    assert len({c["idempotency_key"] for c in fake.calls}) == n_fills
    for call in fake.calls:
        assert str(call["idempotency_key"]).startswith("sim-fin-")
        assert call["trade_type"] == "buy"


def test_invariant_build_balanced_full_sale():
    """Vuelvo un fill OPEN y un CLOSE fiables a un libro balanceado sobre dinero real.

    Terma de dos vías: compra ``Q`` a ``p1`` y vende ``Q`` a ``p2``. Con la re-ponderación
    de coste medio + realized por venta, el mini-día ``equity == initial + realized``
    (el invariante de dominio) se cumple y conduce a un `LifecycleAccounting`.
    """
    p1 = Decimal("100.00")
    p2 = Decimal("106.00")
    Q = Decimal("100")
    buy = SimulatedFillFinance(
        instrument_id="AAA",
        side="buy",
        execution_id="buy#1",
        quantity=Q,
        price=p1,
        account_id="acc-1",
        venue="simulated",
    )
    sell = SimulatedFillFinance(
        instrument_id="AAA",
        side="sell",
        execution_id="sell#1",
        quantity=Q,
        price=p2,
        account_id="acc-1",
        venue="simulated",
    )
    book = sim_roundtrip_accounting((buy, sell), initial_cash=LIFECYCLE_CASH)
    assert book.remaining == 0
    assert book.fills_credited == 2
    # realized real: (106-100)*100 = 600.
    assert book.realized_pnl == Decimal("600")
    actg = LifecycleAccounting(
        cash=book.initial_cash + book.realized_pnl,
        remaining=Decimal("0"),
        realized_pnl=book.realized_pnl,
        unrealized_pnl=Decimal("0"),
        total_pnl=book.realized_pnl,
        last_price=book.last_price,
        market_value=Decimal("0"),
        total_equity=book.total_equity,
        avg_cost=p1,
        initial_equity=book.initial_cash,
    )
    assert_equity_invariant(actg)  # no lanza ⇒ invariante OK con dinero no degenerado.
    assert actg.total_equity == actg.initial_equity + actg.realized_pnl


def test_roundtrip_idempotent_on_replay() -> None:
    """Un replay del mismo execution_id no dobla el libro (idempotencia por fill)."""
    p = Decimal("100.00")
    Q = Decimal("100")
    buy = SimulatedFillFinance(
        instrument_id="AAA",
        side="buy",
        execution_id="b#1",
        quantity=Q,
        price=p,
        account_id="acc-1",
        venue="simulated",
    )
    sell = SimulatedFillFinance(
        instrument_id="AAA",
        side="sell",
        execution_id="s#1",
        quantity=Q,
        price=p,
        account_id="acc-1",
        venue="simulated",
    )
    once = sim_roundtrip_accounting((buy, sell), initial_cash=LIFECYCLE_CASH)
    replay = sim_roundtrip_accounting((buy, buy, sell, sell), initial_cash=LIFECYCLE_CASH)
    assert once.fills_credited == 2
    assert replay.fills_credited == 2  # buy/sell repetidos NO se vuelven a contar.
    assert replay.cash == once.cash == LIFECYCLE_CASH  # ambas vías balanceadas a nulo.


# ── FLAKE-1 (2026-09-30): el corte de la parcial NO es simétrico entre patas ──────
# El rojo intermitente de ``lifecycle-pg`` (``test_finance_auto_day_materializes_
# executetrade_exactly_once`` → ``AssertionError: RETRY``) NO era el motor, ni la clave
# de idempotencia, ni una carrera de entorno: era el FIXTURE. Ni ``draw_queue_noise`` ni
# ``mid_cut`` dependen del ``venue_order_id`` — dependen de ``(seed, side,
# instrument_id)``, es decir de la PATA. Con el MISMO seed, la pata ``buy`` puede cortar
# sus parciales antes que la pata ``sell``; el fixture asumía un ida-y-vuelta net-zero con
# la MISMA cantidad en las dos patas, así que la venta podía pedir más de lo que la compra
# había dejado en cartera. El rechazo del repositorio era CORRECTO (fail-closed): el
# defecto era construir ese plan. Medido: ~6,6 % de los ``instrument_id`` sorteados por el
# gate PG (y ese mismo patrón de tranchas #2/#3 en el run ``36681305812``).
# Estos gates fijan el mecanismo y el invariante del arreglo, SIN PG.

_FLAKE1_INSTRUMENT = "inst-fin-59e064e70b"  # instrument_id REAL del rojo 36681305812
_FLAKE1_SEED = 2  # seed que el selector del gate PG elegía para ese instrument_id
_FLAKE1_TOTAL = Decimal("60")


def _chunks_for(
    instrument_id: str, side: str, *, seed: int, quantity: Decimal
) -> tuple[Decimal, ...]:
    """Deltas por parcial de una pata (mismos inputs que ``submit_simulated_order``)."""
    result = simulated_fill_schedule(
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        venue_order_id=f"sim-{side}-{instrument_id}-{seed}",
        seed=seed,
        fill_chunks=3,
        base_mid=100.0,
    )
    return tuple(f.qty_delta for f in result.fills)


def _finances_for(
    instrument_id: str,
    chunks_by_side: dict[str, tuple[Decimal, ...]],
) -> tuple[SimulatedFillFinance, ...]:
    """Traduce los deltas por pata a las finanzas por fill que consume el libro puro."""
    out: list[SimulatedFillFinance] = []
    for side, chunks in chunks_by_side.items():
        for seq, qty in enumerate(chunks, start=1):
            out.append(
                SimulatedFillFinance(
                    instrument_id=instrument_id,
                    side=side,
                    execution_id=f"{side}#{seq}",
                    quantity=qty,
                    price=Decimal("100.00"),
                    account_id="acc-flake1",
                    venue="simulated",
                )
            )
    return tuple(out)


def test_flake1_partial_cut_is_asymmetric_across_sides() -> None:
    """La RAÍZ: con el mismo seed, ``buy`` se corta y ``sell`` no (30 ≠ 60)."""
    buy = _chunks_for(_FLAKE1_INSTRUMENT, "buy", seed=_FLAKE1_SEED, quantity=_FLAKE1_TOTAL)
    sell = _chunks_for(_FLAKE1_INSTRUMENT, "sell", seed=_FLAKE1_SEED, quantity=_FLAKE1_TOTAL)
    assert buy == (Decimal("30.000000"),), buy
    assert sell == (Decimal("30.000000"), Decimal("14.100000"), Decimal("15.900000")), sell
    assert sum(buy, Decimal("0")) != sum(sell, Decimal("0"))
    # ...y las DOS patas tienen fills: el selector clásico las daba por buenas.
    assert buy and sell


def test_flake1_oversell_plan_is_rejected_by_the_pure_domain_mirror() -> None:
    """El plan que el fixture viejo construía lo RECHAZA el propio espejo del dominio.

    Vender más de lo que dejó la compra no es «un RETRY misterioso»: es oversell, y el
    libro puro lo nombra. Es la lectura que faltaba para no culpar al motor.
    """
    buy = _chunks_for(_FLAKE1_INSTRUMENT, "buy", seed=_FLAKE1_SEED, quantity=_FLAKE1_TOTAL)
    sell = _chunks_for(_FLAKE1_INSTRUMENT, "sell", seed=_FLAKE1_SEED, quantity=_FLAKE1_TOTAL)
    with pytest.raises(ValueError, match="sell exceeds the held position"):
        sim_roundtrip_accounting(_finances_for(_FLAKE1_INSTRUMENT, {"buy": buy, "sell": sell}))


def test_flake1_sizing_the_sell_to_the_realized_buy_never_oversells() -> None:
    """El ARREGLO: dimensionar la venta a lo que la compra LIQUIDA ⇒ net-zero sin oversell.

    Se comprueba en el caso real del rojo y en una rejilla FIJA de ``instrument_id`` (sin
    lotería), y se exige que la rejilla CUBRA el fallo (la suposición vieja sí sobrevende):
    un gate que no alcanza al fallo que arregla no sella nada.
    """
    buy = _chunks_for(_FLAKE1_INSTRUMENT, "buy", seed=_FLAKE1_SEED, quantity=_FLAKE1_TOTAL)
    realized = sum(buy, Decimal("0"))
    sell = _chunks_for(_FLAKE1_INSTRUMENT, "sell", seed=_FLAKE1_SEED, quantity=realized)
    book = sim_roundtrip_accounting(_finances_for(_FLAKE1_INSTRUMENT, {"buy": buy, "sell": sell}))
    assert book.remaining == 0  # ida-y-vuelta CERRADO (net-zero)
    assert book.fills_credited == 1 + len(sell)

    oversold_with_old_assumption = 0
    for i in range(600):
        iid = f"inst-flake1-{i:04d}"
        # Espejo del selector del gate PG: primer seed con fills en AMBAS patas.
        for seed in range(1, 5_000):
            b = _chunks_for(iid, "buy", seed=seed, quantity=_FLAKE1_TOTAL)
            if not b:
                continue
            r = sum(b, Decimal("0"))
            s = _chunks_for(iid, "sell", seed=seed, quantity=r)
            if s:
                break
        else:  # pragma: no cover — la rejilla debe tener plan para todo iid.
            raise AssertionError(f"sin ida-y-vuelta viable para {iid!r}")

        # Con el dimensionado viejo (venta a la cantidad nominal) SÍ había oversell...
        if sum(_chunks_for(iid, "sell", seed=seed, quantity=_FLAKE1_TOTAL), Decimal("0")) > r:
            oversold_with_old_assumption += 1
        # ...y con el arreglo la venta nunca excede la cartera, ni cierra negativa.
        assert sum(s, Decimal("0")) <= r
        assert sim_roundtrip_accounting(_finances_for(iid, {"buy": b, "sell": s})).remaining >= 0

    assert oversold_with_old_assumption > 0, "el gate debe alcanzar el fallo que arregla"
