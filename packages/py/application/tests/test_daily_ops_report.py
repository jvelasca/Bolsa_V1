"""GetDailyOpsReport — agrupación semanal + trades del día."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from bolsa_domain.entities.account import LedgerEntry

from bolsa_application.daily_ops_report import GetDailyOpsReport, _day_key


def _ledger(
    *,
    id: str,
    type: str,
    amount: float,
    balance_after: float,
    executed_at: str,
) -> LedgerEntry:
    return LedgerEntry(
        id=id,
        account_id="acc-1",
        portfolio_id="pf-1",
        type=type,
        amount=amount,
        currency="EUR",
        balance_after=balance_after,
        instrument_id="inst-1",
        symbol="AAA",
        quantity=1.0,
        price=abs(amount),
        reference_type=None,
        reference_id=None,
        description=None,
        executed_at=executed_at,
    )


class _FakeSummary:
    async def execute(self, account_id: str) -> Any:
        return SimpleNamespace(account_id=account_id)


class _FakeLedger:
    def __init__(self, entries: list[LedgerEntry]) -> None:
        self._entries = entries

    async def execute(
        self, account_id: str, limit: int = 400, offset: int = 0
    ) -> list[LedgerEntry]:
        return self._entries


class _FakeF3:
    def __init__(self, queue: list[dict[str, Any]] | None) -> None:
        self._queue = queue

    async def get(self, account_id: str) -> Any:
        if self._queue is None:
            return None
        return SimpleNamespace(queue=self._queue)


def test_day_key_parses_iso() -> None:
    assert _day_key("2026-08-04T15:00:00Z") == "2026-08-04"
    assert _day_key("2026-08-04") == "2026-08-04"
    assert _day_key("bad") is None


@pytest.mark.asyncio
async def test_week_trade_counts_and_f3() -> None:
    as_of = date(2026, 8, 4)
    entries = [
        _ledger(
            id="1",
            type="buy",
            amount=-100,
            balance_after=900,
            executed_at="2026-08-04T10:00:00Z",
        ),
        _ledger(
            id="2",
            type="sell",
            amount=50,
            balance_after=950,
            executed_at="2026-08-04T12:00:00Z",
        ),
        _ledger(
            id="3",
            type="deposit",
            amount=200,
            balance_after=1150,
            executed_at="2026-08-04T14:00:00Z",
        ),
        _ledger(
            id="4",
            type="buy",
            amount=-20,
            balance_after=880,
            executed_at="2026-08-02T09:00:00Z",
        ),
        _ledger(
            id="5",
            type="buy",
            amount=-10,
            balance_after=700,
            executed_at="2026-07-20T09:00:00Z",
        ),
    ]
    uc = GetDailyOpsReport(
        _FakeSummary(),  # type: ignore[arg-type]
        _FakeLedger(entries),  # type: ignore[arg-type]
        _FakeF3([{"id": "f3-1"}, {"id": "f3-2"}]),  # type: ignore[arg-type]
        opinion_repo=None,
    )
    bundle = await uc.execute("acc-1", as_of=as_of)

    assert bundle.as_of == as_of
    assert len(bundle.trades_today) == 2
    assert len(bundle.ledger_today) == 3
    assert bundle.f3_pending_count == 2
    assert len(bundle.week) == 7
    assert bundle.week[0]["date"] == "2026-07-29"
    assert bundle.week[-1]["date"] == "2026-08-04"
    day_row = next(d for d in bundle.week if d["date"] == "2026-08-04")
    assert day_row["tradeCount"] == 2
    assert day_row["ledgerCount"] == 3
    assert day_row["balanceAfter"] == 1150.0
    aug2 = next(d for d in bundle.week if d["date"] == "2026-08-02")
    assert aug2["tradeCount"] == 1
    # Outside week window ignored
    assert sum(d["tradeCount"] for d in bundle.week) == 3
