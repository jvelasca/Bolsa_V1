"""allow_opening_fill — helper pre-fill I1 (Confirm / Fill / HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from bolsa_application.opening_permission import allow_opening_fill
from bolsa_application.operational_incident_store import InMemoryOperationalIncidentStore
from bolsa_application.risk_engine import DATA_FRESHNESS_MAX_AGE_SECONDS


class _AllowSummary:
    async def execute(self, *, account_id: str) -> Any:
        return type("Sum", (), {"total_equity": 10_000.0, "positions": []})()


class _VetoSummary:
    async def execute(self, *, account_id: str) -> Any:
        raise RuntimeError("summary down")


class _FakeMandatesNoOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return False, None


class _FakeMandatesOpen:
    async def get_open_mandate_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> tuple[bool, str | None]:
        return True, "st-mandate-1"


class _FakeOhlcv:
    def __init__(self, last_bar: str | None) -> None:
        self._last_bar = last_bar

    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: object = None
    ) -> str | None:
        return self._last_bar


def _kwargs(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "symbol": "SAN",
        "trade_type": "buy",
        "quantity": 1.0,
        "price": 10.0,
        "signal_kind": "recommend_long",
    }
    base.update(extra)
    return base


@pytest.mark.asyncio
async def test_allow_opening_fill_none_summary_is_legacy_true() -> None:
    assert await allow_opening_fill(portfolio_summary=None, **_kwargs()) is True


@pytest.mark.asyncio
async def test_allow_opening_fill_summary_raises_fail_closed() -> None:
    assert (
        await allow_opening_fill(portfolio_summary=_VetoSummary(), **_kwargs())  # type: ignore[arg-type]
        is False
    )


@pytest.mark.asyncio
async def test_allow_opening_fill_empty_book_allows() -> None:
    assert (
        await allow_opening_fill(portfolio_summary=_AllowSummary(), **_kwargs())  # type: ignore[arg-type]
        is True
    )


@pytest.mark.asyncio
async def test_allow_opening_fill_no_open_mandate_vetoes() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        mandates=_FakeMandatesNoOpen(),
        **_kwargs(),
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_allow_opening_fill_open_mandate_allows() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        mandates=_FakeMandatesOpen(),
        **_kwargs(),
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_allow_opening_fill_stale_bar_vetoes() -> None:
    stale = (
        datetime.now(UTC) - timedelta(seconds=DATA_FRESHNESS_MAX_AGE_SECONDS + 3600)
    ).date().isoformat()
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        ohlcv=_FakeOhlcv(stale),
        **_kwargs(),
    )
    assert allowed is False


class _FakePortfolioRecon:
    def __init__(self, status: str) -> None:
        self.status = status

    async def portfolio_recon_status(self, account_id: str) -> str:
        return self.status


class _FakeLiveRecon:
    def __init__(self, status: str) -> None:
        self.status = status

    async def live_recon_status(self, account_id: str) -> str:
        return self.status


@pytest.mark.asyncio
async def test_allow_opening_fill_portfolio_drift_vetoes() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=_FakePortfolioRecon("drift"),  # type: ignore[arg-type]
        **_kwargs(),
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_allow_opening_fill_portfolio_clean_allows() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=_FakePortfolioRecon("clean"),  # type: ignore[arg-type]
        **_kwargs(),
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_allow_opening_fill_live_unavailable_vetoes_on_live() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        live_recon=_FakeLiveRecon("unavailable"),  # type: ignore[arg-type]
        broker_venue="live",
        **_kwargs(),
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_allow_opening_fill_live_unavailable_ignored_on_paper() -> None:
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        live_recon=_FakeLiveRecon("unavailable"),  # type: ignore[arg-type]
        broker_venue="paper",
        **_kwargs(),
    )
    assert allowed is True


@pytest.mark.asyncio
async def test_allow_opening_fill_unresolved_incident_vetoes() -> None:
    store = InMemoryOperationalIncidentStore()
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=_FakePortfolioRecon("drift"),  # type: ignore[arg-type]
        incident_store=store,
        **_kwargs(),
    )
    assert allowed is False
    assert len(await store.list_active("acc-1")) == 1
