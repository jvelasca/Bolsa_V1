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
from bolsa_application.lifecycle_outbox import (
    PostgresLifecycleOutboxStore,
    drain_lifecycle_outbox,
)
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
    InstrumentRow,
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
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
) -> tuple[str, str]:
    """Returns (account_id, legacy_portfolio_id) for ledger FK seeding."""
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
    return account_id, legacy_id


async def _insert_instrument(
    factory: async_sessionmaker[AsyncSession],
    *,
    instrument_id: str,
    symbol: str | None = None,
) -> None:
    now = _now()
    sym = symbol or f"G190{instrument_id[-6:].upper()}"
    async with factory() as session:
        if await session.get(InstrumentRow, instrument_id) is None:
            session.add(
                InstrumentRow(
                    id=instrument_id,
                    symbol=sym,
                    yahoo_symbol=f"{sym}-{instrument_id}",
                    isin=None,
                    name=sym,
                    exchange="TEST",
                    country="US",
                    currency="USD",
                    sector=None,
                    type="stock",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()


async def _seed_open_ledger_fks(
    factory: async_sessionmaker[AsyncSession],
    *,
    portfolio_id: str,
    instrument_id: str,
    position_id: str,
    tx_id: str,
    qty: float = 10.0,
    price: float = 100.0,
) -> None:
    """Seed positions + transactions rows required by position_states FKs."""
    now = _now()
    q = Decimal(str(qty))
    p = Decimal(str(price))
    async with factory() as session:
        if await session.get(PositionRow, position_id) is None:
            session.add(
                PositionRow(
                    id=position_id,
                    portfolio_id=portfolio_id,
                    instrument_id=instrument_id,
                    quantity=q,
                    avg_cost=p,
                    updated_at=now,
                )
            )
        if await session.get(TransactionRow, tx_id) is None:
            session.add(
                TransactionRow(
                    id=tx_id,
                    portfolio_id=portfolio_id,
                    instrument_id=instrument_id,
                    type="buy",
                    quantity=q,
                    price=p,
                    total=q * p,
                    executed_at=now,
                    idempotency_key=None,
                )
            )
        await session.commit()


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
        await _insert_instrument(factory, instrument_id=instrument_id)
        acc_a, pf_a = await _insert_account(
            factory, user_id=user_a, name="Golden V190 A"
        )
        await _insert_account(factory, user_id=user_b, name="Golden V190 B")
        token_a = await _jwt(factory, user_a)
        token_b = await _jwt(factory, user_b)
        plan = _plan(instrument_id)

        # OPEN
        open_tx = f"tx-open-{uuid4().hex[:10]}"
        await _seed_open_ledger_fks(
            factory,
            portfolio_id=pf_a,
            instrument_id=instrument_id,
            position_id=position_id,
            tx_id=open_tx,
        )

        async def _sync_and_drain(
            *,
            action: str,
            qty: float,
            price: float,
            tx_id: str,
            at: str,
            side: str = "buy",
        ) -> dict[str, Any]:
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
                result = await sync.sync_after_fill(
                    rec=SimpleNamespace(action=action, decision_id="dec-g190"),
                    intent=SimpleNamespace(
                        quantity=qty, instrument_id=instrument_id
                    ),
                    price=price,
                    account_id=acc_a,
                    trade=_trade(
                        tx_id=tx_id,
                        instrument_id=instrument_id,
                        position_id=position_id,
                        qty=qty,
                        price=price,
                        side=side,
                        at=at,
                    ),
                    trade_plan_dict=plan,
                    tx_id=tx_id,
                )
                await session.commit()
            async with factory() as drain_session:
                await drain_lifecycle_outbox(
                    PostgresLifecycleOutboxStore(drain_session),
                    AppendLifecycleEvent(
                        PostgresLifecycleEventStore(drain_session)
                    ),
                )
                await drain_session.commit()
            return result

        open_result = await _sync_and_drain(
            action="recommend_long",
            qty=10.0,
            price=100.0,
            tx_id=open_tx,
            at="2026-09-03T10:00:00.000Z",
        )
        assert open_result["status"] == "applied", open_result
        assert open_result.get("lifecycle", {}).get("status") == "pending", open_result

        # Replay OPEN same tx → idempotent / no duplicate
        replay = await _sync_and_drain(
            action="recommend_long",
            qty=10.0,
            price=100.0,
            tx_id=open_tx,
            at="2026-09-03T10:00:00.000Z",
        )
        assert replay["status"] == "applied"

        # REDUCE T1
        reduce_tx = f"tx-t1-{uuid4().hex[:10]}"
        reduce_result = await _sync_and_drain(
            action="reduce",
            qty=5.0,
            price=105.0,
            tx_id=reduce_tx,
            at="2026-09-03T11:00:00.000Z",
            side="sell",
        )
        assert reduce_result["status"] == "applied", reduce_result

        # EXIT
        exit_tx = f"tx-exit-{uuid4().hex[:10]}"
        exit_result = await _sync_and_drain(
            action="exit_hint",
            qty=5.0,
            price=108.0,
            tx_id=exit_tx,
            at="2026-09-03T12:00:00.000Z",
            side="sell",
        )
        assert exit_result["status"] == "applied", exit_result

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
