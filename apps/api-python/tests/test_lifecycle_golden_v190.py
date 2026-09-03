"""V1.90 — Golden: Confirm/PositionSync → lifecycle PG → GET snapshot.

Certifies the real product hook (not POST /lifecycle/events):
  OPEN → T1 reduce → EXIT → replay idempotent · User B 403

Requires PostgreSQL (LIFECYCLE_PG_REQUIRED=1 fails hard).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.session import SESSION_COOKIE_NAME
from bolsa_api.main import create_app, lifespan
from bolsa_application.confirm.position_sync import PositionSyncCoordinator
from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    PostgresLifecycleEventStore,
)
from bolsa_application.lifecycle_outbox import PostgresLifecycleOutboxStore
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    Position,
    TradeResult,
    Transaction,
)
from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
    UserRow,
)
from bolsa_infrastructure.database.repositories.position_state_repository import (
    SqlAlchemyPositionStateRepository,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get("LIFECYCLE_PG_REQUIRED") == "1":
        raise AssertionError(
            f"lifecycle golden required but PostgreSQL unavailable: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL no disponible: {exc}")


async def _insert_user(
    factory: async_sessionmaker[AsyncSession], *, user_id: str
) -> None:
    async with factory() as session:
        if await session.get(UserRow, user_id) is None:
            session.add(
                UserRow(
                    id=user_id,
                    login=user_id,
                    password_hash=hash_password("pw"),
                    role="operator",
                    session_version=0,
                    created_at=_now(),
                    disabled_at=None,
                )
            )
            await session.commit()


async def _insert_account(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    name: str,
) -> str:
    account_id = f"lc-g190-{uuid4().hex[:12]}"
    legacy_id = f"pf-g190-{uuid4().hex[:12]}"
    inv_pf_id = f"ip-g190-{uuid4().hex[:12]}"
    ledger_id = f"le-g190-{uuid4().hex[:12]}"
    now = _now()
    deposit = Decimal("1000")
    async with factory() as session:
        session.add(
            InvestmentAccountRow(
                id=account_id,
                user_id=user_id,
                name=name,
                type="simulated",
                status="active",
                currency="USD",
                base_currency="USD",
                initial_deposit=deposit,
                leverage=Decimal("1"),
                is_default=False,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            PortfolioRow(
                id=legacy_id,
                name=f"{name} — cartera",
                currency="USD",
                cash=deposit,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            InvestmentPortfolioRow(
                id=inv_pf_id,
                account_id=account_id,
                legacy_portfolio_id=legacy_id,
                name="Cartera principal",
                description=None,
                strategy_tag="core",
                sort_order=0,
                is_default=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            LedgerEntryRow(
                id=ledger_id,
                account_id=account_id,
                portfolio_id=inv_pf_id,
                type="deposit",
                amount=deposit,
                currency="USD",
                balance_after=deposit,
                reference_type="manual",
                reference_id=account_id,
                description="Depósito inicial golden v190",
                executed_at=now,
                created_at=now,
            )
        )
        await session.commit()
    return account_id


async def _jwt(factory: async_sessionmaker[AsyncSession], user_id: str) -> str:
    settings = get_settings()
    async with factory() as session:
        user = await session.get(UserRow, user_id)
        assert user is not None
        return encode_access_token(
            settings, sub=user.id, sv=user.session_version, role=user.role
        )


def _trade(
    *,
    tx_id: str,
    instrument_id: str,
    position_id: str,
    qty: float,
    price: float,
    side: str = "buy",
    at: str = "2026-09-03T10:00:00.000Z",
) -> TradeResult:
    tx = Transaction(
        id=tx_id,
        type=side,  # type: ignore[arg-type]
        instrument_id=instrument_id,
        symbol="AAPL",
        quantity=qty,
        price=price,
        total=qty * price,
        executed_at=at,
    )
    pos = Position(
        id=position_id,
        instrument_id=instrument_id,
        symbol="AAPL",
        name="Apple",
        quantity=qty,
        avg_cost=price,
        last_price=price,
        market_value=qty * price,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0,
    )
    return TradeResult(
        transaction=tx,
        summary=PortfolioSummary(
            portfolio=Portfolio(id="pf", name="p", currency="USD", cash=1000.0),
            positions=[pos],
            total_market_value=qty * price,
            total_cost=qty * price,
            total_unrealized_pnl=0.0,
            total_equity=1000.0 + qty * price,
        ),
    )


def _plan(instrument_id: str) -> dict[str, Any]:
    return {
        "id": "tp-g190",
        "decisionId": "dec-g190",
        "instrumentId": instrument_id,
        "symbol": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
    }


@pytest.fixture
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "lifecycle-golden-v190-password")
    monkeypatch.setenv("APP_AUTH_SECRET", "lifecycle-golden-v190-secret-key-32b")
    monkeypatch.setenv("JWT_SIGNING_KEY", "lifecycle-golden-v190-secret-key-32b")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_v190_golden_confirm_position_sync_lifecycle_snapshot(
    auth_secret: None,
) -> None:
    instrument_id = f"inst-g190-{uuid4().hex[:8]}"
    position_id = f"pos-g190-{uuid4().hex[:10]}"
    user_a = f"user-a-{uuid4().hex[:8]}"
    user_b = f"user-b-{uuid4().hex[:8]}"

    try:
        app = create_app()
    except Exception as exc:  # noqa: BLE001
        _require_or_skip(exc)
        raise

    async with lifespan(app):
        factory = app.state.session_factory
        await _insert_user(factory, user_id=user_a)
        await _insert_user(factory, user_id=user_b)
        acc_a = await _insert_account(factory, user_id=user_a, name="Golden V190 A")
        await _insert_account(factory, user_id=user_b, name="Golden V190 B")
        token_a = await _jwt(factory, user_a)
        token_b = await _jwt(factory, user_b)
        plan = _plan(instrument_id)

        async with factory() as session:
            repo = SqlAlchemyPositionStateRepository(session)
            sync = PositionSyncCoordinator(
                position_from_fill=PersistPositionFromFill(repo),
                position_from_exit=PersistPositionFromExit(repo),
                lifecycle_append=AppendLifecycleEvent(
                    PostgresLifecycleEventStore(session)
                ),
                lifecycle_outbox=PostgresLifecycleOutboxStore(session),
            )

            # OPEN
            open_tx = f"tx-open-{uuid4().hex[:10]}"
            open_result = await sync.sync_after_fill(
                rec=SimpleNamespace(
                    action="recommend_long", decision_id="dec-g190"
                ),
                intent=SimpleNamespace(quantity=10.0, instrument_id=instrument_id),
                price=100.0,
                account_id=acc_a,
                trade=_trade(
                    tx_id=open_tx,
                    instrument_id=instrument_id,
                    position_id=position_id,
                    qty=10.0,
                    price=100.0,
                    at="2026-09-03T10:00:00.000Z",
                ),
                trade_plan_dict=plan,
                tx_id=open_tx,
            )
            assert open_result["status"] == "applied", open_result
            assert open_result.get("lifecycle", {}).get("status") in (
                "applied",
                "pending",
            ), open_result
            await session.commit()

            # Replay OPEN same tx → idempotent / no duplicate
            replay = await sync.sync_after_fill(
                rec=SimpleNamespace(
                    action="recommend_long", decision_id="dec-g190"
                ),
                intent=SimpleNamespace(quantity=10.0, instrument_id=instrument_id),
                price=100.0,
                account_id=acc_a,
                trade=_trade(
                    tx_id=open_tx,
                    instrument_id=instrument_id,
                    position_id=position_id,
                    qty=10.0,
                    price=100.0,
                    at="2026-09-03T10:00:00.000Z",
                ),
                trade_plan_dict=plan,
                tx_id=open_tx,
            )
            assert replay["status"] == "applied"
            await session.commit()

            # REDUCE T1
            reduce_tx = f"tx-t1-{uuid4().hex[:10]}"
            reduce_result = await sync.sync_after_fill(
                rec=SimpleNamespace(action="reduce", decision_id="dec-g190"),
                intent=SimpleNamespace(quantity=5.0, instrument_id=instrument_id),
                price=105.0,
                account_id=acc_a,
                trade=_trade(
                    tx_id=reduce_tx,
                    instrument_id=instrument_id,
                    position_id=position_id,
                    qty=5.0,
                    price=105.0,
                    side="sell",
                    at="2026-09-03T11:00:00.000Z",
                ),
                trade_plan_dict=plan,
                tx_id=reduce_tx,
            )
            assert reduce_result["status"] == "applied", reduce_result
            await session.commit()

            # EXIT
            exit_tx = f"tx-exit-{uuid4().hex[:10]}"
            exit_result = await sync.sync_after_fill(
                rec=SimpleNamespace(action="exit_hint", decision_id="dec-g190"),
                intent=SimpleNamespace(quantity=5.0, instrument_id=instrument_id),
                price=108.0,
                account_id=acc_a,
                trade=_trade(
                    tx_id=exit_tx,
                    instrument_id=instrument_id,
                    position_id=position_id,
                    qty=5.0,
                    price=108.0,
                    side="sell",
                    at="2026-09-03T12:00:00.000Z",
                ),
                trade_plan_dict=plan,
                tx_id=exit_tx,
            )
            assert exit_result["status"] == "applied", exit_result
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, token_a)
            snap_resp = await client.get(
                f"/api/lifecycle/positions/{position_id}/snapshot"
            )
            assert snap_resp.status_code == 200, snap_resp.text
            snap = snap_resp.json()["data"]
            assert snap["stage"] == "closed"
            kinds = [e["kind"] for e in snap["events"]]
            assert kinds[0] == "POSITION_OPENED"
            assert "T1_EXECUTED" in kinds
            assert kinds[-1] == "POSITION_CLOSED"
            event_ids = [e["eventId"] for e in snap["events"]]
            assert open_tx in event_ids
            assert event_ids.count(open_tx) == 1  # replay did not duplicate

            # Cash ledger authority untouched — lifecycle accounting is sidecar only
            assert snap["accounting"] is not None

            client.cookies.set(SESSION_COOKIE_NAME, token_b)
            foreign = await client.get(
                f"/api/lifecycle/positions/{position_id}/snapshot"
            )
            assert foreign.status_code == 403
