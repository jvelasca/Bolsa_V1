"""R12-AUTH fase 1: stamp ``user_id`` and hide foreign accounts (404, not 500)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import InvestmentAccountRow
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.principal import (
    DEFAULT_APP_PRINCIPAL,
    account_visible_to_principal,
    resolve_app_principal,
)
from bolsa_api.auth.session import SESSION_COOKIE_NAME, create_session_cookie_value
from bolsa_api.main import create_app, lifespan


def _now() -> datetime:
    return datetime.now(UTC)


async def _insert_raw_account(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
) -> str:
    account_id = f"iso-{uuid4().hex[:16]}"
    async with factory() as session:
        session.add(
            InvestmentAccountRow(
                id=account_id,
                user_id=user_id,
                name=name,
                type="simulated",
                status="active",
                currency="EUR",
                base_currency="EUR",
                initial_deposit=Decimal("1000"),
                leverage=Decimal("1"),
                is_default=False,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()
    return account_id


async def _delete_raw_account(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(InvestmentAccountRow, account_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


def test_resolve_app_principal_defaults_to_app() -> None:
    get_settings.cache_clear()
    assert resolve_app_principal(get_settings()) == DEFAULT_APP_PRINCIPAL
    get_settings.cache_clear()


def test_account_visible_to_principal_f7a_soft_legacy() -> None:
    get_settings.cache_clear()
    bootstrap = resolve_app_principal(get_settings())
    assert account_visible_to_principal(None, bootstrap) is True
    assert account_visible_to_principal(None, "user-b") is False
    assert account_visible_to_principal("user-a", "user-a") is True
    assert account_visible_to_principal("user-a", "user-b") is False
    get_settings.cache_clear()


def _patch_request_principal(
    monkeypatch: pytest.MonkeyPatch, principal: str
) -> None:
    def fake(_request: object) -> str:
        return principal

    for target in (
        "bolsa_api.auth.request_principal.get_request_principal",
        "bolsa_api.api.dependencies.get_request_principal",
        "bolsa_api.api.v1.routes.accounts.get_request_principal",
    ):
        monkeypatch.setattr(target, fake)


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_account_list_and_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F6: JWT principal distinto no ve cuentas ajenas en list/get (404)."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        user_a_id = await _insert_raw_account(
            factory, user_id="user-a", name="User A isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/accounts/{user_a_id}")
                assert response.status_code == 404

                listed = await client.get("/api/accounts")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert user_a_id not in ids
        finally:
            await _delete_raw_account(factory, user_a_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_hidden_from_non_bootstrap_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F7a: legacy ``user_id is None`` invisible salvo principal bootstrap."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_account(
            factory, user_id=None, name="Legacy F7a isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/accounts/{legacy_id}")
                assert response.status_code == 404

                listed = await client.get("/api/accounts")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_account(factory, legacy_id)


@pytest.mark.asyncio
async def test_new_account_stamps_user_id_when_auth_disabled() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/accounts",
                json={
                    "name": f"Stamp auth-off {uuid4().hex[:8]}",
                    "currency": "EUR",
                    "initialDeposit": 1_000,
                },
            )
            assert created.status_code == 201
            body = created.json()["data"]
            assert body["userId"] == DEFAULT_APP_PRINCIPAL

            fetched = await client.get(f"/api/accounts/{body['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["data"]["userId"] == DEFAULT_APP_PRINCIPAL


@pytest.mark.asyncio
async def test_new_account_stamps_user_id_when_auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, create_session_cookie_value(get_settings()))
            created = await client.post(
                "/api/accounts",
                json={
                    "name": f"Stamp auth-on {uuid4().hex[:8]}",
                    "currency": "EUR",
                    "initialDeposit": 1_000,
                },
            )
            assert created.status_code == 201
            assert created.json()["data"]["userId"] == DEFAULT_APP_PRINCIPAL

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_foreign_user_id_account_returns_404() -> None:
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        foreign_id = await _insert_raw_account(
            factory, user_id="other", name="Foreign isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/accounts/{foreign_id}")
                assert response.status_code == 404

                listed = await client.get("/api/accounts")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert foreign_id not in ids
        finally:
            await _delete_raw_account(factory, foreign_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_account_still_gettable() -> None:
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_account(
            factory, user_id=None, name="Legacy isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/accounts/{legacy_id}")
                assert response.status_code == 200
                assert response.json()["data"]["id"] == legacy_id
                assert response.json()["data"]["userId"] is None

                listed = await client.get("/api/accounts")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id in ids
        finally:
            await _delete_raw_account(factory, legacy_id)


@pytest.mark.asyncio
async def test_foreign_account_404_with_session_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        foreign_id = await _insert_raw_account(
            factory, user_id="other", name="Foreign cookie isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set(
                    SESSION_COOKIE_NAME, create_session_cookie_value(get_settings())
                )
                response = await client.get(f"/api/accounts/{foreign_id}")
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, foreign_id)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_foreign_account_nested_and_header_routes_return_404() -> None:
    """R12-AUTH fase 2: core-r/mandates path + portfolio X-Account-Id."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        foreign_id = await _insert_raw_account(
            factory, user_id="other", name="Foreign nested isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                core_r = await client.get(f"/api/accounts/{foreign_id}/core-r")
                assert core_r.status_code == 404

                mandates = await client.get(f"/api/accounts/{foreign_id}/mandates")
                assert mandates.status_code == 404

                portfolio = await client.get(
                    "/api/portfolio",
                    headers={"X-Account-Id": foreign_id},
                )
                assert portfolio.status_code == 404
        finally:
            await _delete_raw_account(factory, foreign_id)


@pytest.mark.asyncio
async def test_foreign_account_cash_and_trade_routes_return_404() -> None:
    """R12-AUTH fase 3: deposit path + trade X-Account-Id (Depends before use-case)."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        foreign_id = await _insert_raw_account(
            factory, user_id="other", name="Foreign cash isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                deposit = await client.post(
                    f"/api/accounts/{foreign_id}/deposits",
                    json={
                        "amount": 10,
                        "idempotencyKey": "iso-deposit-key-01",
                    },
                )
                assert deposit.status_code == 404

                trade = await client.post(
                    "/api/portfolio/trade",
                    headers={"X-Account-Id": foreign_id},
                    json={"dummy": True},
                )
                assert trade.status_code == 404
        finally:
            await _delete_raw_account(factory, foreign_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_deposit_not_owner_404() -> None:
    """Legacy ``user_id is None`` deposit is not hidden; 404 would be owner isolation."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_account(
            factory, user_id=None, name="Legacy cash isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/accounts/{legacy_id}/deposits",
                    json={
                        "amount": 10,
                        "idempotencyKey": "iso-legacy-dep-001",
                    },
                )
                assert response.status_code != 404
                assert response.status_code in {201, 400, 422}
        finally:
            await _delete_raw_account(factory, legacy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_core_r_still_gettable() -> None:
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_account(
            factory, user_id=None, name="Legacy core-r isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/accounts/{legacy_id}/core-r")
                assert response.status_code == 200
                assert response.json()["data"]["accountId"] == legacy_id
        finally:
            await _delete_raw_account(factory, legacy_id)
