"""OI-6 — ReconcilePortfolioIntegrity use-case tests."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.reconcile_portfolio_integrity import (
    ReconcilePortfolioIntegrity,
    ReconcilePortfolioIntegrityInput,
)


class _Cash:
    def __init__(self, cash: float) -> None:
        self.cash = cash

    async def get_cash(self, account_id: str) -> float:
        return self.cash


class _Ledger:
    def __init__(self, total: float) -> None:
        self.total = total

    async def sum_cash_amounts(self, account_id: str) -> float:
        return self.total


class _Holdings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def list_holdings(self, account_id: str) -> list[dict[str, Any]]:
        return self.rows


class _Opens:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        return self.rows


class _Txs:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    async def list_transaction_ids(self, account_id: str) -> list[str]:
        return self.ids


def _open_row(*, remaining: float = 10.0, tx: str = "tx-1") -> dict[str, Any]:
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        fill_price=100.0,
        fill_quantity=remaining,
        filled_at="2026-08-26T00:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return {
        "id": "pos-1",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": pos.status,
        "open_transaction_id": tx,
        "position_state": pos.to_dict(),
    }


@pytest.mark.asyncio
async def test_reconcile_clean() -> None:
    uc = ReconcilePortfolioIntegrity(
        cash=_Cash(500.0),
        ledger=_Ledger(500.0),
        holdings=_Holdings([{"instrument_id": "inst-1", "quantity": 10.0}]),
        open_positions=_Opens([_open_row()]),
        transactions=_Txs(["tx-1"]),
    )
    report = await uc.reconcile(
        ReconcilePortfolioIntegrityInput(account_id="acc-1")
    )
    assert report is not None
    assert report.status == "clean"
    assert report.account_id == "acc-1"


@pytest.mark.asyncio
async def test_reconcile_drift_cash() -> None:
    uc = ReconcilePortfolioIntegrity(
        cash=_Cash(500.0),
        ledger=_Ledger(400.0),
        holdings=_Holdings([]),
        open_positions=_Opens([]),
        transactions=_Txs([]),
    )
    report = await uc.reconcile(
        ReconcilePortfolioIntegrityInput(account_id="acc-1")
    )
    assert report is not None
    assert report.status == "drift"


@pytest.mark.asyncio
async def test_reconcile_addon_expected() -> None:
    uc = ReconcilePortfolioIntegrity(
        cash=_Cash(1.0),
        ledger=_Ledger(1.0),
        holdings=_Holdings([{"instrument_id": "inst-1", "quantity": 15.0}]),
        open_positions=_Opens([_open_row(remaining=10.0)]),
        transactions=_Txs(["tx-1"]),
    )
    report = await uc.reconcile(
        ReconcilePortfolioIntegrityInput(account_id="acc-1")
    )
    assert report is not None
    assert report.status == "clean"
    qty = next(c for c in report.checks if c.id == "holding_qty_vs_position")
    assert qty.outcome == "expected"


@pytest.mark.asyncio
async def test_blank_account_returns_none() -> None:
    uc = ReconcilePortfolioIntegrity(
        cash=_Cash(1.0),
        ledger=_Ledger(1.0),
        holdings=_Holdings([]),
        open_positions=_Opens([]),
    )
    assert await uc.reconcile(ReconcilePortfolioIntegrityInput(account_id="  ")) is None
