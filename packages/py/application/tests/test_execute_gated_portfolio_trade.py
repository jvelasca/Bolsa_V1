"""ExecuteGatedPortfolioTrade — HTTP paper trade con check_opening (I1)."""

from __future__ import annotations

from typing import Any, Literal

import pytest
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction

from bolsa_application.execute_gated_portfolio_trade import (
    ExecuteGatedPortfolioTrade,
    OpeningVetoedError,
)


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> TradeResult:
        self.calls.append(kwargs)
        side = str(kwargs.get("trade_type", "buy")).lower()
        tx_type: Literal["buy", "sell"] = "sell" if side == "sell" else "buy"
        tx = Transaction(
            id="tx-http",
            type=tx_type,
            instrument_id=kwargs["instrument_id"],
            symbol="SYM",
            quantity=float(kwargs["quantity"]),
            price=float(kwargs["price"]),
            total=float(kwargs["quantity"]) * float(kwargs["price"]),
            executed_at="2026-08-25T00:00:00Z",
        )
        return TradeResult(
            transaction=tx,
            summary=PortfolioSummary(
                portfolio=Portfolio(id="pf", name="p", currency="EUR", cash=0.0),
                positions=[],
                total_market_value=0.0,
                total_cost=0.0,
                total_unrealized_pnl=0.0,
                total_equity=0.0,
            ),
        )


class _AllowSummary:
    async def execute(self, *, account_id: str) -> Any:
        return type("Sum", (), {"total_equity": 10_000.0, "positions": []})()


class _VetoSummary:
    async def execute(self, *, account_id: str) -> Any:
        raise RuntimeError("summary down")


def _uc(*, summary: Any, trade: _FakeExecuteTrade) -> ExecuteGatedPortfolioTrade:
    return ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=summary,
    )


@pytest.mark.asyncio
async def test_gated_http_buy_allows_when_gate_ok() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_AllowSummary(), trade=trade)
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1


@pytest.mark.asyncio
async def test_gated_http_buy_risk_veto_no_trade() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_VetoSummary(), trade=trade)
    with pytest.raises(OpeningVetoedError, match="risk_veto"):
        await uc.execute(
            instrument_id="inst-1",
            trade_type="buy",
            quantity=2.0,
            price=10.0,
            account_id="acc-1",
            idempotency_key="k" * 16,
        )
    assert trade.calls == []


@pytest.mark.asyncio
async def test_gated_http_sell_skips_opening_gate() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc(summary=_VetoSummary(), trade=trade)
    result = await uc.execute(
        instrument_id="inst-1",
        trade_type="sell",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert result.transaction.id == "tx-http"
    assert len(trade.calls) == 1
    assert trade.calls[0]["trade_type"] == "sell"
