"""DEX-3 — OperationalIncident store + opening workflow (ADR-035).

drift → INC → review → resolve → clear. Sin auto-heal. Store fresco no reabre
duplicados. Clear exige recon clean.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_analytics.cognitive.operational_incident import (
    open_incident,
)
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.opening_permission import allow_opening_fill
from bolsa_application.operational_incident_store import (
    InMemoryOperationalIncidentStore,
    PostgresOperationalIncidentStore,
    clear_and_store,
    resolve_and_store,
    sync_opening_incidents,
)
from bolsa_application.risk_engine import check_opening
from bolsa_infrastructure.database.models.tables import OperationalIncidentRow


class _AllowSummary:
    async def execute(self, *, account_id: str) -> Any:
        return type("Sum", (), {"total_equity": 10_000.0, "positions": []})()


class _TogglePortfolioRecon:
    def __init__(self, status: str = "drift") -> None:
        self.status = status

    async def portfolio_recon_status(self, account_id: str) -> str:
        return self.status


def _open_kwargs(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "account_id": "acc-dex3",
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
async def test_inmemory_put_get_active_roundtrip() -> None:
    store = InMemoryOperationalIncidentStore()
    inc = open_incident(
        incident_id="inc-mem-1",
        account_id="acc-1",
        kind="portfolio_drift",
        snapshot="cash mismatch",
    )
    await store.put(inc)
    got = await store.get("inc-mem-1")
    assert got is not None
    assert got.status == "open"
    active = await store.get_active("acc-1", "portfolio_drift")
    assert active is not None
    assert active.incident_id == "inc-mem-1"


@pytest.mark.asyncio
async def test_sync_opens_one_incident_per_kind() -> None:
    store = InMemoryOperationalIncidentStore()
    first = await sync_opening_incidents(
        store,
        account_id="acc-1",
        portfolio_recon_status="drift",
        broker_venue="paper",
    )
    second = await sync_opening_incidents(
        store,
        account_id="acc-1",
        portfolio_recon_status="drift",
        broker_venue="paper",
    )
    assert first == "unresolved"
    assert second == "unresolved"
    active = await store.list_active("acc-1")
    assert len(active) == 1
    assert active[0].kind == "portfolio_drift"


@pytest.mark.asyncio
async def test_resolve_clear_requires_clean_recon() -> None:
    store = InMemoryOperationalIncidentStore()
    await sync_opening_incidents(
        store,
        account_id="acc-1",
        portfolio_recon_status="drift",
    )
    inc = (await store.list_active("acc-1"))[0]
    resolved = await resolve_and_store(
        store,
        incident_id=inc.incident_id,
        resolution_note="manual cash top-up",
        resolved_by="op",
    )
    assert resolved.status == "resolved"
    with pytest.raises(ValueError, match="recon_not_clean"):
        await clear_and_store(
            store,
            incident_id=inc.incident_id,
            recon_status="drift",
        )
    cleared = await clear_and_store(
        store,
        incident_id=inc.incident_id,
        recon_status="clean",
    )
    assert cleared.status == "cleared"
    assert await store.list_active("acc-1") == []


@pytest.mark.asyncio
async def test_new_drift_after_clear_opens_new_incident() -> None:
    store = InMemoryOperationalIncidentStore()
    await sync_opening_incidents(
        store, account_id="acc-1", portfolio_recon_status="drift"
    )
    inc = (await store.list_active("acc-1"))[0]
    await resolve_and_store(
        store, incident_id=inc.incident_id, resolution_note="fixed"
    )
    await clear_and_store(
        store, incident_id=inc.incident_id, recon_status="clean"
    )
    await sync_opening_incidents(
        store, account_id="acc-1", portfolio_recon_status="drift"
    )
    active = await store.list_active("acc-1")
    assert len(active) == 1
    assert active[0].incident_id != inc.incident_id


@pytest.mark.asyncio
async def test_opening_fill_drift_opens_incident_and_denies() -> None:
    store = InMemoryOperationalIncidentStore()
    recon = _TogglePortfolioRecon("drift")
    allowed = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=recon,  # type: ignore[arg-type]
        incident_store=store,
        **_open_kwargs(),
    )
    assert allowed is False
    assert len(await store.list_active("acc-dex3")) == 1

    recon.status = "clean"
    still = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=recon,  # type: ignore[arg-type]
        incident_store=store,
        **_open_kwargs(),
    )
    assert still is False
    inc = (await store.list_active("acc-dex3"))[0]
    await resolve_and_store(
        store, incident_id=inc.incident_id, resolution_note="books aligned"
    )
    await clear_and_store(
        store, incident_id=inc.incident_id, recon_status="clean"
    )
    allowed_after = await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=recon,  # type: ignore[arg-type]
        incident_store=store,
        **_open_kwargs(),
    )
    assert allowed_after is True


def test_exit_allows_with_unresolved_incident() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="sell",
        quantity=1,
        price=10,
        signal_kind="exit",
        incident_status="unresolved",
        require_incident_veto=True,
        equity=10_000.0,
    )
    assert d.verdict == "ALLOW"


def test_opening_denies_unresolved_incident() -> None:
    d = check_opening(
        profile=None,
        instrument_id="i1",
        symbol="SAN",
        trade_type="buy",
        quantity=1,
        price=10,
        signal_kind="entry_long",
        incident_status="unresolved",
        require_incident_veto=True,
        equity=10_000.0,
    )
    assert d.verdict == "DENY"
    assert d.reasons == ("incident:unresolved",)


@pytest.mark.asyncio
async def test_postgres_store_put_commits_and_maps_row() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty)

    store = PostgresOperationalIncidentStore(session)
    inc = open_incident(
        incident_id="inc-pg-1",
        account_id="acc-1",
        kind="live_unavailable",
        snapshot="bridge down",
    )
    await store.put(inc)
    session.add.assert_called_once()
    session.commit.assert_awaited()
    added = session.add.call_args.args[0]
    assert isinstance(added, OperationalIncidentRow)
    assert added.id == "inc-pg-1"
    assert added.kind == "live_unavailable"
    assert added.status == "open"

    row = MagicMock()
    row.id = "inc-pg-1"
    row.account_id = "acc-1"
    row.kind = "live_unavailable"
    row.status = "open"
    row.snapshot = "bridge down"
    row.opened_at = inc.opened_at
    row.reviewed_at = None
    row.reviewed_by = None
    row.resolved_at = None
    row.resolved_by = None
    row.resolution_note = None
    row.cleared_at = None
    found = MagicMock()
    found.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=found)
    got = await store.get("inc-pg-1")
    assert got is not None
    assert got.status == "open"
    assert got.kind == "live_unavailable"


@pytest.mark.asyncio
async def test_resolve_does_not_mutate_recon_status() -> None:
    """Sin auto-heal: resolve deja el informe de recon tal cual (el test no llama heal)."""
    store = InMemoryOperationalIncidentStore()
    recon = _TogglePortfolioRecon("drift")
    await allow_opening_fill(
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        portfolio_recon=recon,  # type: ignore[arg-type]
        incident_store=store,
        **_open_kwargs(),
    )
    inc = (await store.list_active("acc-dex3"))[0]
    await resolve_and_store(store, incident_id=inc.incident_id, resolution_note="ack")
    assert recon.status == "drift"
    assert (await store.get(inc.incident_id)).status == "resolved"  # type: ignore[union-attr]


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> Any:
        self.calls.append(kwargs)
        tx = type(
            "Tx",
            (),
            {
                "id": "tx-1",
                "type": "buy",
                "instrument_id": "inst-1",
                "symbol": "SAN",
                "quantity": 1.0,
                "price": 10.0,
                "total": 10.0,
                "executed_at": "2026-08-26T08:00:00Z",
            },
        )()
        return type("Trade", (), {"transaction": tx, "summary": None})()


def _opening_recommendation() -> dict[str, Any]:
    return {
        "decisionId": "DEC-DEX3-1",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": 4.0,
        "suggestedPrice": 10.0,
        "tradePlan": {
            "decisionId": "DEC-DEX3-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 10.0,
            "structuralStop": 9.0,
            "riskAmount": 500.0,
        },
    }


class _ConfirmSummary:
    """Cesta diversificada (mismo patrón OR-4 Confirm)."""

    def __init__(self) -> None:
        self.total_equity = 200.0
        self.positions = [
            type("P", (), {"instrument_id": "a", "market_value": 4.0, "sector": "tech"})(),
            type("P", (), {"instrument_id": "b", "market_value": 4.0, "sector": "health"})(),
            type("P", (), {"instrument_id": "c", "market_value": 4.0, "sector": "energy"})(),
            type("P", (), {"instrument_id": "d", "market_value": 4.0, "sector": "cons"})(),
        ]

    async def execute(self, *, account_id: str) -> Any:
        return self


@pytest.mark.asyncio
async def test_confirm_drift_opens_incident_zero_fill() -> None:
    store = InMemoryOperationalIncidentStore()
    fake_trade = _FakeExecuteTrade()
    use_case = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        portfolio_summary=_ConfirmSummary(),  # type: ignore[arg-type]
        portfolio_recon=_TogglePortfolioRecon("drift"),  # type: ignore[arg-type]
        incident_store=store,
    )
    result = await use_case.execute(
        recommendation_raw=_opening_recommendation(),
        account_id="acc-dex3",
        execute=True,
    )
    assert len(fake_trade.calls) == 0
    assert result["trade"]["status"] == "rejected_by_gate"
    assert result["trade"]["reason"] == "risk_veto"
    active = await store.list_active("acc-dex3")
    assert len(active) == 1
    assert active[0].kind == "portfolio_drift"
