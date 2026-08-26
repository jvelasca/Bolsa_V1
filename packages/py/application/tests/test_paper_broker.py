"""PaperBroker.submit — CREATED→SUBMITTED→FILLED; boom → UNKNOWN."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.paper_broker import PaperBroker


class _OkExecute:
    async def execute(self, **kwargs: Any) -> Any:
        return type("Trade", (), {"transaction_id": "tx-pb"})()


class _BoomExecute:
    async def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("ledger timeout")


@pytest.mark.asyncio
async def test_submit_ok_fills_paper_order() -> None:
    broker = PaperBroker(_OkExecute())
    result = await broker.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
        price=100.0,
        account_id="acc-1",
        idempotency_key="idem-1",
        intent_id="intent-1",
    )
    assert result.status == "executed"
    assert result.transaction_id == "tx-pb"
    assert result.paper_order.status == "FILLED"
    assert result.paper_order.venue == "PAPER"
    assert result.paper_order.transaction_id == "tx-pb"
    receipt = result.receipt()
    assert receipt.venue == "PAPER"
    assert receipt.adapter == "paper_broker"
    assert receipt.fill_status == "executed"


@pytest.mark.asyncio
async def test_submit_exception_marks_unknown() -> None:
    broker = PaperBroker(_BoomExecute())
    result = await broker.submit(
        instrument_id="inst-1",
        side="sell",
        quantity=5.0,
        price=50.0,
        account_id="acc-1",
        idempotency_key="idem-2",
    )
    assert result.status == "unknown"
    assert result.reason == "ledger timeout"
    assert result.paper_order.status == "UNKNOWN"
    assert result.paper_order.transaction_id is None
    assert result.trade is None
    receipt = result.receipt()
    assert receipt.fill_status == "unknown"
    assert receipt.venue == "PAPER"
