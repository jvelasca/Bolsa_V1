"""LR-1 — ReconcileLiveLedger use-case tests."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.reconcile_live_ledger import (
    ReconcileLiveLedger,
    ReconcileLiveLedgerInput,
)


class _Cash:
    def __init__(self, cash: float) -> None:
        self.cash = cash

    async def get_cash(self, account_id: str) -> float:
        return self.cash


class _Holdings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def list_holdings(self, account_id: str) -> list[dict[str, Any]]:
        return self.rows


class _Live:
    def __init__(
        self,
        cash: float,
        positions: list[dict[str, Any]],
        *,
        fail: bool = False,
    ) -> None:
        self.cash = cash
        self.positions = positions
        self.fail = fail

    async def fetch_cash(self) -> float:
        if self.fail:
            raise RuntimeError("venue down")
        return self.cash

    async def fetch_positions(self) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("venue down")
        return self.positions


@pytest.mark.asyncio
async def test_reconcile_clean() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(500.0),
        holdings=_Holdings([{"instrument_id": "inst-1", "quantity": 10.0}]),
        live=_Live(500.0, [{"instrumentId": "inst-1", "quantity": 10.0}]),
    )
    report = await uc.reconcile(ReconcileLiveLedgerInput(account_id="acc-1"))
    assert report is not None
    assert report.status == "clean"
    assert report.account_id == "acc-1"


@pytest.mark.asyncio
async def test_reconcile_drift_cash() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(500.0),
        holdings=_Holdings([]),
        live=_Live(400.0, []),
    )
    report = await uc.reconcile(ReconcileLiveLedgerInput(account_id="acc-1"))
    assert report is not None
    assert report.status == "drift"


@pytest.mark.asyncio
async def test_reconcile_unavailable_missing_client() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(1.0),
        holdings=_Holdings([]),
        live=None,
    )
    report = await uc.reconcile(ReconcileLiveLedgerInput(account_id="acc-1"))
    assert report is not None
    assert report.status == "unavailable"


@pytest.mark.asyncio
async def test_reconcile_unavailable_on_exception() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(1.0),
        holdings=_Holdings([]),
        live=_Live(0.0, [], fail=True),
    )
    report = await uc.reconcile(ReconcileLiveLedgerInput(account_id="acc-1"))
    assert report is not None
    assert report.status == "unavailable"


@pytest.mark.asyncio
async def test_reconcile_holding_without_live_expected() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(1.0),
        holdings=_Holdings([{"instrument_id": "legacy", "quantity": 3.0}]),
        live=_Live(1.0, []),
    )
    report = await uc.reconcile(ReconcileLiveLedgerInput(account_id="acc-1"))
    assert report is not None
    assert report.status == "clean"
    legacy = next(c for c in report.checks if c.id == "holding_without_live")
    assert legacy.outcome == "expected"


@pytest.mark.asyncio
async def test_blank_account_returns_none() -> None:
    uc = ReconcileLiveLedger(
        cash=_Cash(1.0),
        holdings=_Holdings([]),
        live=_Live(1.0, []),
    )
    assert await uc.reconcile(ReconcileLiveLedgerInput(account_id="  ")) is None
