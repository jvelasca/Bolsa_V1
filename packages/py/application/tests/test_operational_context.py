"""V1.47 — OperationalContext / MarketSnapshot / nextAction."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from bolsa_application.operational_context import (
    FakeMarketDataPort,
    MarketSnapshot,
    OperationalContextBuilder,
    classify_market_data,
    is_stop_touched,
    resolve_paper_desk_next_action,
)
from bolsa_market.market_calendar import resolve_session_state, session_is_open


def test_classify_market_data() -> None:
    expected = date(2026, 8, 31)
    assert classify_market_data(last_price=None, bar_date=None, expected=expected) == "MISSING"
    assert (
        classify_market_data(last_price=100.0, bar_date="2026-08-20", expected=expected)
        == "STALE"
    )
    assert (
        classify_market_data(last_price=100.0, bar_date="2026-08-31", expected=expected)
        == "FRESH"
    )
    assert (
        classify_market_data(last_price=-1.0, bar_date="2026-08-31", expected=expected)
        == "INVALID"
    )


def test_stop_touched_long() -> None:
    assert is_stop_touched(direction="long", mark=94.0, stop=95.0) is True
    assert is_stop_touched(direction="long", mark=100.0, stop=95.0) is False
    assert is_stop_touched(direction="long", mark=None, stop=95.0) is False


def test_next_action_mapping() -> None:
    assert (
        resolve_paper_desk_next_action(status="held", decision_verdict="HOLD", reason="data_stale")
        == "REVISAR_DATOS_NO_FRESCOS"
    )
    assert (
        resolve_paper_desk_next_action(
            status="held",
            decision_verdict="HOLD",
            reason="queue_next_session",
            session="CLOSED",
        )
        == "ESPERAR_APERTURA"
    )
    assert (
        resolve_paper_desk_next_action(status="protected", decision_verdict="TRAIL")
        == "MONITOR"
    )
    assert (
        resolve_paper_desk_next_action(
            status="protected",
            decision_verdict="TRAIL",
            reason="dry_run",
        )
        == "SUBIR_STOP"
    )
    assert resolve_paper_desk_next_action(status="denied", decision_verdict="REDUCE") == "BLOQUEADO"


def test_session_weekend_closed() -> None:
    saturday = datetime(2026, 6, 27, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    assert resolve_session_state(exchange="BME", as_of=saturday) == "CLOSED"
    assert session_is_open("CLOSED") is False


def test_session_open_and_post() -> None:
    morning = datetime(2026, 6, 24, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    evening = datetime(2026, 6, 24, 18, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    assert resolve_session_state(exchange="BME", as_of=morning) == "OPEN"
    assert resolve_session_state(exchange="BME", as_of=evening) == "POST"


@pytest.mark.asyncio
async def test_builder_derives_drift_and_snapshots() -> None:
    class _Recon:
        async def portfolio_recon_status(self, account_id: str) -> str:
            _ = account_id
            return "drift"

    port = FakeMarketDataPort(
        {
            "MSFT": MarketSnapshot(
                instrument_id="MSFT",
                last_price=110.0,
                permission="FRESH",
                source="test",
            )
        }
    )
    ctx = await OperationalContextBuilder(port, _Recon()).build("acc-1", ["MSFT"])
    assert ctx.portfolio.drift is True
    assert ctx.mark_price("MSFT") == 110.0
    assert ctx.market_for("AAPL") is None


@pytest.mark.asyncio
async def test_builder_unavailable_is_not_drift() -> None:
    class _Boom:
        async def portfolio_recon_status(self, account_id: str) -> str:
            _ = account_id
            raise RuntimeError("down")

    port = FakeMarketDataPort(
        {
            "MSFT": MarketSnapshot(
                instrument_id="MSFT",
                last_price=110.0,
                permission="FRESH",
                source="test",
            )
        }
    )
    ctx = await OperationalContextBuilder(port, _Boom()).build("acc-1", ["MSFT"])
    assert ctx.portfolio.recon_status == "unavailable"
    assert ctx.portfolio.drift is False
