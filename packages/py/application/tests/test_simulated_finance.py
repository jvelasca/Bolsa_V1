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
from decimal import Decimal

import pytest
from bolsa_domain.lifecycle import LIFECYCLE_CASH, LifecycleAccounting, assert_equity_invariant

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


def _applier_for(result, *, fake: _FakeExecuteTrade):
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
