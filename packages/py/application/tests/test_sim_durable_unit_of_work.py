"""V2.24.2 (P2-B) — unidad-de-trabajo proyección + finance en UNA transacción.

Test hermético del commit condicional de ``sim_durable_store``: con
``autocommit=False`` (unidad-de-trabajo) NINGÚN store commitea por su cuenta y el
caller decide; con ``autocommit=True`` (default) cada store conserva su commit
propio (durabilidad-e-idempotencia). No toca PostgreSQL real: usa una sesión fake
que registra ``execute``/``commit``/``rollback``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from bolsa_application.sim_durable_store import (
    PostgresSimAutoPositionStore,
    PostgresSimFillFinanceContextStore,
    SimDurableUnitOfWork,
    SimFillFinanceContext,
)


class _FakeSession:
    def __init__(self) -> None:
        self.executes = 0
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _stmt: Any) -> None:
        self.executes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _context() -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id="exec-uow-1",
        instrument_id="inst-1",
        side="buy",
        quantity=Decimal("10"),
        price=Decimal("100"),
        account_id="acc-1",
        venue="simulated",
        idempotency_key="idem-uow-1",
    )


@pytest.mark.asyncio
async def test_stores_autocommit_by_default() -> None:
    """Comportamiento histórico intacto: cada store commitea por su cuenta."""
    session = _FakeSession()
    finance = PostgresSimFillFinanceContextStore(session)
    position = PostgresSimAutoPositionStore(session)
    await finance.save(_context())
    await position.upsert("acc-1", "eng-1", "AAPL", Decimal("10"))
    assert session.commits == 2


@pytest.mark.asyncio
async def test_unit_of_work_defers_commit_to_caller() -> None:
    """Con autocommit=False, los stores NO commitean; el caller lo hace UNA vez."""
    session = _FakeSession()
    uow = SimDurableUnitOfWork.open(session)
    await uow.finance_store.save(_context())
    await uow.position_store.upsert("acc-1", "eng-1", "AAPL", Decimal("10"))
    assert session.commits == 0  # ninguno de los dos espejos commiteó por su cuenta
    assert session.executes == 2
    await uow.commit()
    assert session.commits == 1  # un único commit para ambos espejos


@pytest.mark.asyncio
async def test_unit_of_work_rollback_leaves_nothing_committed() -> None:
    """Si la unidad-de-trabajo revierte, ningún espejo queda persistido."""
    session = _FakeSession()
    uow = SimDurableUnitOfWork.open(session)
    await uow.finance_store.save(_context())
    await uow.position_store.delete("acc-1", "eng-1", "AAPL")
    await uow.rollback()
    assert session.commits == 0
    assert session.rollbacks == 1
