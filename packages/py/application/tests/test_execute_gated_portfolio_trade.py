"""ExecuteGatedPortfolioTrade — HTTP paper trade con check_opening (I1)."""

from __future__ import annotations

from typing import Any, Literal

import pytest

from bolsa_application.execute_gated_portfolio_trade import (
    ExecuteGatedPortfolioTrade,
    OpeningVetoedError,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction


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


class _FillStore:
    def __init__(self) -> None:
        self.inserts: list[dict] = []
        self.open_by_instrument: dict[tuple[str, str], dict] = {}

    async def get_by_open_transaction_id(self, open_transaction_id: str):
        return None

    async def get_open_for_instrument(self, account_id: str, instrument_id: str):
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs):
        row = {"id": kwargs.get("position_id") or "pos-new", **kwargs}
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        self.inserts.append(kwargs)
        return row


class _ExitStore:
    def __init__(self, row=None):
        self.row = row
        self.updates = []

    async def get_open_for_instrument(self, account_id: str, instrument_id: str):
        return self.row

    async def update_state(self, *, position_id: str, status: str, position_state: dict):
        self.updates.append({"status": status})
        return self.row


@pytest.mark.asyncio
async def test_gated_http_buy_persists_manual_position() -> None:
    trade = _FakeExecuteTrade()
    fill_store = _FillStore()
    uc = ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_AllowSummary(),
        position_from_fill=PersistPositionFromFill(fill_store),
        position_from_exit=PersistPositionFromExit(_ExitStore()),
    )
    await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert len(fill_store.inserts) == 1
    assert fill_store.inserts[0]["birth_override_reason"] == "human_manual"


class _FakeOhlcv:
    def __init__(self, last_bar: str) -> None:
        self._last_bar = last_bar

    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: object = None
    ) -> str | None:
        return self._last_bar


class _FakeMandatesOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return True, "st-mandate-1"


class _FakeInstrumentDataStatus:
    def __init__(self, warnings: tuple[str, ...]) -> None:
        self._warnings = warnings

    async def execute(self, instrument_id: str, *, timeframe: object = None) -> Any:
        return type("Status", (), {"sanity_warnings": self._warnings})()


def _uc_with_sanity(*, warnings: tuple[str, ...], trade: _FakeExecuteTrade) -> ExecuteGatedPortfolioTrade:
    from datetime import UTC, datetime

    return ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_AllowSummary(),
        ohlcv=_FakeOhlcv(datetime.now(UTC).isoformat()),  # type: ignore[arg-type]
        mandates=_FakeMandatesOpen(),  # type: ignore[arg-type]
        instrument_data_status=_FakeInstrumentDataStatus(warnings),
    )


@pytest.mark.asyncio
async def test_gated_http_buy_sanity_split_vetoes() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc_with_sanity(
        warnings=("movimiento 55.00% en 2024-01-01 — revisar split/dividendo",),
        trade=trade,
    )
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
async def test_gated_http_buy_sanity_gap_only_allows() -> None:
    trade = _FakeExecuteTrade()
    uc = _uc_with_sanity(warnings=("gap de 2 días",), trade=trade)
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
