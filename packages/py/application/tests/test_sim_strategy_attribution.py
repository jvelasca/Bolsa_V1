"""V2.28 / A10 (P1-02 real) — tests de propagación de la atribución de estrategia.

Cadena que se verifica (toda hermética, sin PG):

1. ``submit_simulated_order(..., strategy_version_id=...)`` persiste el contexto de cada
   fill con esa versión (``sim_fill_finance_context.strategy_version_id``).
2. ``list_for_strategy_version`` recupera EXACTAMENTE esos fills y no otros.
3. El resolver durable (crash/relaunch) reconstruye la finance conservando la atribución.
4. La contabilidad observada sobre esos fills produce las métricas esperadas.

Es el cimiento del cierre del P1-02: sin esta propagación la vigilancia real no puede
saber a qué versión pertenece cada fill.

Nota de calibración: el settlement es determinista y algunas semillas no producen fills
(``submitted``/``rejected``). El módulo usa semillas verificadas como productoras de fills
(``7``, ``101``) para que las aserciones sean sobre fills reales, no vacías.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore
from bolsa_application.sim_finance_context import build_durable_finance_resolver
from bolsa_application.simulated_settlement import submit_simulated_order
from bolsa_application.strategy_observed_metrics import compute_observed_metrics_from_fills

pytestmark = pytest.mark.asyncio

# Semillas verificadas como productoras de fills con base_mid=100 y qty=10.
_SEED_FILLED = 7


async def _settle(
    exec_store: InMemoryExecutionEventStore,
    ctx_store: InMemorySimFillFinanceContextStore,
    *,
    side: str,
    seed: int,
    quantity: str,
    strategy_version_id: str | None,
) -> object:
    result, _outcomes = await submit_simulated_order(
        exec_store,
        instrument_id="SAN.MC",
        side=side,
        quantity=Decimal(quantity),
        account_id="acc-1",
        venue="simulated",
        seed=seed,
        order_id=f"o-{seed}",
        engine_id="auto-sim",
        logical_order_id=f"l-{seed}",
        context_store=ctx_store,
        strategy_version_id=strategy_version_id,
    )
    return result


async def test_settlement_persists_strategy_version_on_each_fill() -> None:
    exec_store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()

    result = await _settle(
        exec_store,
        ctx_store,
        side="buy",
        seed=_SEED_FILLED,
        quantity="10",
        strategy_version_id="ver-abc",
    )

    assert result.fills, "el settlement determinista debe producir fills"
    for fill in result.fills:
        ctx = await ctx_store.get(fill.execution_id)
        assert ctx is not None
        assert ctx.strategy_version_id == "ver-abc"


async def test_settlement_without_strategy_version_leaves_attribution_null() -> None:
    exec_store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()

    result = await _settle(
        exec_store,
        ctx_store,
        side="buy",
        seed=_SEED_FILLED,
        quantity="10",
        strategy_version_id=None,
    )

    assert result.fills
    ctx = await ctx_store.get(result.fills[0].execution_id)
    assert ctx is not None
    # Sin atribución declarada NO se inventa una versión.
    assert ctx.strategy_version_id is None


async def test_list_for_strategy_version_filters_exactly() -> None:
    exec_store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()

    await _settle(
        exec_store, ctx_store, side="buy", seed=7, quantity="10", strategy_version_id="ver-a"
    )
    await _settle(
        exec_store, ctx_store, side="buy", seed=101, quantity="10", strategy_version_id="ver-b"
    )

    only_a = await ctx_store.list_for_strategy_version("ver-a")
    assert only_a
    assert all(row.strategy_version_id == "ver-a" for row in only_a)
    only_b = await ctx_store.list_for_strategy_version("ver-b")
    assert only_b
    assert all(row.strategy_version_id == "ver-b" for row in only_b)
    assert len(only_a) + len(only_b) == ctx_store.size()


async def test_durable_resolver_preserves_attribution() -> None:
    """Tras crash, el resolver reconstruye la finance SIN perder la versión."""
    exec_store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()

    result = await _settle(
        exec_store,
        ctx_store,
        side="buy",
        seed=_SEED_FILLED,
        quantity="10",
        strategy_version_id="ver-crash",
    )
    assert result.fills

    resolver = build_durable_finance_resolver(ctx_store)

    class _Execution:
        def __init__(self, execution_id: str) -> None:
            self.execution_id = execution_id
            self.account_id = "acc-1"

    finance = await resolver(_Execution(result.fills[0].execution_id))
    assert finance is not None
    assert finance.strategy_version_id == "ver-crash"


async def test_observed_metrics_over_attributed_fills() -> None:
    """Fills atribuidos a una versión producen métricas sin contaminación de otras."""
    exec_store = InMemoryExecutionEventStore()
    ctx_store = InMemorySimFillFinanceContextStore()

    await _settle(
        exec_store, ctx_store, side="buy", seed=7, quantity="10", strategy_version_id="ver-1"
    )
    await _settle(
        exec_store, ctx_store, side="sell", seed=101, quantity="10", strategy_version_id="ver-1"
    )
    # Ruido de OTRA versión que no debe contaminar las métricas.
    await _settle(
        exec_store, ctx_store, side="buy", seed=7, quantity="999", strategy_version_id="ver-otra"
    )

    fills = await ctx_store.list_for_strategy_version("ver-1")
    metrics = compute_observed_metrics_from_fills(fills, min_trades=1)
    assert metrics is not None
    # El schedule divide cada orden en varios fills parciales; la venta cruza esos lotes
    # ⇒ varios round-trips FIFO. Lo relevante es que hayan CERRADO (trades > 0) y que el
    # ruido de ``ver-otra`` no haya participado.
    assert metrics.trades > 0
    assert metrics.realized_pnl != Decimal("0")
    # El ruido (qty 999 de otra versión) no está en la serie de ver-1.
    assert metrics.committed_capital < Decimal("2000")
