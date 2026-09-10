"""V2.23 / A9 (Bloque 5 · P1-05) — persistencia + resolver durable del contexto por fill.

Une la mitad pura de ``simulated_finance`` (mapper ``sim_fill_finances``) con el
espejo durable ``sim_fill_finance_context`` (``sim_durable_store``):

* ``persist_fill_finance_context`` — durante la liquidación de un order SIM, guarda
  por ``execution_id`` el contexto financiero (instrument/side/qty/price/account/
  venue) ANTES de mover dinero. Idempotente por PK.
* ``build_durable_finance_resolver`` — devuelve un ``FinanceResolver`` **asíncrono**
  que reconstruye la finance de un fill leyendo SOLO del store durable por
  ``execution_id`` (sin memoria del ``SimulatedOrderResult``), de modo que un apply
  tras crash/relaunch siga encontrando el contexto. Fail-closed: sin fila o venue no
  SIM-ONLY ⇒ ``None`` (el applier no materializa; el outcome queda RETRY, nunca
  APPLIED en falso).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bolsa_application.sim_durable_store import (
    SimFillFinanceContext,
    SimFillFinanceContextStore,
)
from bolsa_application.simulated_finance import SimulatedFillFinance, sim_fill_finances

__all__ = [
    "build_durable_finance_resolver",
    "persist_fill_finance_context",
]


async def persist_fill_finance_context(
    context_store: SimFillFinanceContextStore,
    result: Any,
    *,
    instrument_id: str,
    side: str,
    account_id: str | None,
    venue: str,
    strategy_version_id: str | None = None,
) -> int:
    """Persiste el contexto durable de cada fill del order. Devuelve nº de filas.

    Idempotente (PK ``execution_id``): un re-registro no duplica. Usa el mapper puro
    ``sim_fill_finances`` (mismo precio/cantidad deterministas que la liquidación) y
    por tanto reutiliza la MISMA identidad financiera del fill.

    V2.28 / A10 (P1-02 real): ``strategy_version_id`` atribuye el fill a la versión de
    estrategia ACTIVE que lo originó (``None`` = sin atribución; nunca se inventa).
    """
    finances: tuple[SimulatedFillFinance, ...] = sim_fill_finances(
        result,
        instrument_id=instrument_id,
        side=side,
        account_id=account_id,
        venue=venue,
    )
    saved = 0
    for fin in finances:
        await context_store.save(
            SimFillFinanceContext(
                execution_id=fin.execution_id,
                instrument_id=fin.instrument_id,
                side=fin.side,
                quantity=Decimal(fin.quantity),
                price=Decimal(fin.price),
                account_id=fin.account_id,
                venue=fin.venue,
                idempotency_key=fin.idempotency_key,
                strategy_version_id=strategy_version_id,
            )
        )
        saved += 1
    return saved


def build_durable_finance_resolver(
    context_store: SimFillFinanceContextStore,
) -> Any:
    """Resolver asíncrono ``ExecutionEvent -> SimulatedFillFinance | None`` durable.

    El applier (``build_simulated_execute_trade_applier``) acepta un resolver que
    devuelva un awaitable; aquí se hace porque la lectura del contexto es async.
    """

    async def _resolve(execution: Any) -> SimulatedFillFinance | None:
        execution_id = str(getattr(execution, "execution_id", "") or "")
        if not execution_id:
            return None
        ctx = await context_store.get(execution_id)
        if ctx is None:
            return None
        try:
            return SimulatedFillFinance(
                instrument_id=ctx.instrument_id,
                side=ctx.side,
                execution_id=ctx.execution_id,
                quantity=Decimal(ctx.quantity),
                price=Decimal(ctx.price),
                account_id=ctx.account_id or getattr(execution, "account_id", None),
                venue=ctx.venue or "simulated",
                strategy_version_id=ctx.strategy_version_id,
            )
        except ValueError:
            # Contexto inválido (venue no sim-only, qty<=0…) ⇒ fail-closed.
            return None

    return _resolve
