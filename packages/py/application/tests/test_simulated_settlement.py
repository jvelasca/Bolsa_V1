"""V2.22 / A9 (M1+M2) — liquidación simulada (sell-side + idempotencia).

Cubre el puente SimulatedBroker → ExecutionEvent → apply idempotente usando el
``InMemoryExecutionEventStore`` (mismo invariante que PG): ninguna traza se
materializa dos veces, y cada ``execution_id`` es único por fill.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
)
from bolsa_application.simulated_broker import simulated_fill_schedule
from bolsa_application.simulated_settlement import (
    apply_simulated_order_once,
    normalized_auto_venue,
    simulated_execution_candidates,
    simulated_idempotency_key,
    submit_simulated_order,
)

_Q = Decimal("100.000000")


class _FakeFinance:
    """Aplicador financiero degenerado del test (espeja ExecuteTrade no-doble).

    Idempotencia real la garantiza el store de ExecutionEvent (N veces el MISMO
    execution_id → una sola materialización).
    """

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: object) -> bool:
        assert isinstance(execution, ExecutionEvent)
        self.applied.append(execution.execution_id)
        return True


def _schedule(side: str, *, seed: int = 7, qty: Decimal = _Q):
    return simulated_fill_schedule(
        instrument_id="AAA",
        side=side,
        quantity=qty,
        venue_order_id=f"sim-{side}-AAA-{seed}",
        seed=seed,
        fill_chunks=3,
        base_mid=100.0,
    )


def test_venue_normalization_allows_only_paper_simulated() -> None:
    assert normalized_auto_venue("simulated") == "simulated"
    assert normalized_auto_venue("sim") == "simulated"
    assert normalized_auto_venue("paper") == "paper"
    assert normalized_auto_venue("dry") == "paper"
    # LIVE y aliases / veneno jamás pasan (tras trim+lower no son sim/paper).
    for bad in ("live", "xtb", "real", "broker_live", "LIVE", "simu", " paperX"):
        assert normalized_auto_venue(bad) is None


def test_execution_candidates_delta_per_fill_seq_and_blocked_live() -> None:
    for side in ("buy", "sell"):
        result = _schedule(side)
        events = simulated_execution_candidates(
            result,
            instrument_id="AAA",
            account_id="acc-1",
            venue="simulated",
        )
        if result.fills:
            assert events, "con fills debe haber candidatos"
            ids = {e.execution_id for e in events}
            assert len(ids) == len(events)  # únicos (fill_seq distintos).
            for e, f in zip(events, result.fills, strict=False):
                assert e.qty <= _Q  # delta, nunca acumulado que exceda.
                assert e.qty == f.qty_delta
                assert e.venue == "SIMULATED"
        else:
            assert events == ()
    # Venue live → cero candidatos (fail-closed).
    blocked = simulated_execution_candidates(
        _schedule("buy"),
        instrument_id="AAA",
        account_id="acc-1",
        venue="live",
    )
    assert blocked == ()


def test_submit_blocked_for_non_auto_venue() -> None:
    store = InMemoryExecutionEventStore()

    async def _go() -> None:
        result, outcomes = await submit_simulated_order(
            store,
            instrument_id="AAA",
            side="buy",
            quantity=_Q,
            account_id="acc-1",
            venue="live",  # → bloqueado.
            seed=7,
            apply_finance=_FakeFinance(),
        )
        assert result.status == "rejected"
        assert result.reason == "venue_not_auto_allowed"
        assert result.fills == ()
        assert outcomes == {}

    asyncio.run(_go())


def test_apply_ignores_non_auto_venue() -> None:
    store = InMemoryExecutionEventStore()
    fin = _FakeFinance()

    async def _go() -> None:
        outcome = await apply_simulated_order_once(
            store,
            result=_schedule("buy"),
            instrument_id="AAA",
            account_id="acc-1",
            venue="live",
            apply_finance=fin,
        )
        # venue no AUTO-allowed → nunca dinero ni trazas.
        assert outcome == {}
        assert fin.applied == []

    asyncio.run(_go())


def test_sell_side_submission_idempotent() -> None:
    store = InMemoryExecutionEventStore()
    fin = _FakeFinance()

    async def run_sell() -> tuple:
        return await submit_simulated_order(
            store,
            instrument_id="AAA",
            side="sell",
            quantity=_Q,
            account_id="acc-1",
            venue="simulated",
            seed=7,
            apply_finance=fin,
        )

    result, outcomes = asyncio.run(run_sell())
    total = sum((f.qty_delta for f in result.fills), Decimal("0"))
    # Contrato de cantidad: deltas nunca sobrepasan lo pedido.
    assert total <= _Q
    # Traders: o un resultado materializable (filled/partial) o terminal sin fill
    # (submitted/rejected/unknown) — pero nunca un status inconsistente.
    assert result.status in {"filled", "partial", "submitted", "rejected", "unknown"}
    if result.fills:
        assert all(
            o in {"applied", "already_applied", "retry_scheduled"} for o in outcomes.values()
        )

    # Segunda liquidación del MISMO seed/order: trazas ya existen → idempotente.
    result2, out2 = asyncio.run(run_sell())
    assert len(out2) == len(outcomes)
    assert result2.venue_order_id == result.venue_order_id
    # El fake NO contó dos veces el mismo execution_id.
    assert len(fin.applied) == len(set(fin.applied))


def test_idempotency_key_stable() -> None:
    k1 = simulated_idempotency_key("sim-aaa#1")
    k2 = simulated_idempotency_key("sim-aaa#1")
    assert k1 == k2
    assert k1.startswith("sim-fin-")
    assert len(k1) <= 128
    assert " " not in k1
