"""V1.59 — harness pytest + AsyncClient + PostgreSQL (GP-V159-*)."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from tests.opening_gate_seed import seed_http_opening_allow

from bolsa_api.main import FastAPI, create_app, lifespan

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


async def _postgres_available() -> bool:
    _load_env()
    from sqlalchemy import select

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        await engine.dispose()


@asynccontextmanager
async def integration_client() -> AsyncIterator[tuple[FastAPI, AsyncClient]]:
    """App FastAPI + cliente ASGI; skip si PostgreSQL no responde."""
    if not await _postgres_available():
        pytest.skip("PostgreSQL no disponible para integration V1.59")
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


async def first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


async def create_funded_account(
    client: AsyncClient,
    *,
    name_prefix: str = "v159",
    initial_deposit: float = 100_000,
) -> str:
    create = await client.post(
        "/api/accounts",
        json={
            "name": f"{name_prefix}-{uuid4().hex[:8]}",
            "currency": "EUR",
            "initialDeposit": initial_deposit,
        },
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def seed_buy_trade(
    app: FastAPI,
    client: AsyncClient,
    account_id: str,
    instrument_id: str,
    *,
    quantity: float = 5,
    price: float = 50,
) -> None:
    await seed_http_opening_allow(app, client, account_id, instrument_id)
    trade = await client.post(
        "/api/portfolio/trade",
        headers={"X-Account-Id": account_id},
        json={
            "instrumentId": instrument_id,
            "type": "buy",
            "quantity": quantity,
            "price": price,
            "idempotencyKey": f"v159-{uuid4().hex[:20]}",
        },
    )
    assert trade.status_code == 200, trade.text


async def seed_portfolio_cash_drift(
    app: FastAPI,
    account_id: str,
    *,
    drift_amount: float = 500.0,
) -> None:
    """M-2 escotilla documentada: cash ≠ Σ ledger → recon drift."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    factory = app.state.session_factory
    async with factory() as session:
        scope = await SqlAlchemyAccountRepository(session).resolve_scope(account_id)
        await SqlAlchemyPortfolioRepository(session).add_cash(
            scope.legacy_portfolio_id,
            drift_amount,
        )
        await session.commit()


async def heal_portfolio_cash_drift(
    app: FastAPI,
    account_id: str,
    *,
    drift_amount: float = 500.0,
) -> None:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    factory = app.state.session_factory
    async with factory() as session:
        scope = await SqlAlchemyAccountRepository(session).resolve_scope(account_id)
        await SqlAlchemyPortfolioRepository(session).deduct_cash(
            scope.legacy_portfolio_id,
            drift_amount,
        )
        await session.commit()


async def open_portfolio_drift_incident(app: FastAPI, account_id: str) -> None:
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
        sync_opening_incidents,
    )

    factory = app.state.session_factory
    async with factory() as session:
        store = PostgresOperationalIncidentStore(session)
        status = await sync_opening_incidents(
            store,
            account_id=account_id,
            portfolio_recon_status="drift",
            broker_venue="paper",
        )
        assert status == "unresolved"
        await session.commit()
