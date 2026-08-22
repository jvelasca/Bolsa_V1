"""R12-AUTH fase 1: stamp ``user_id`` and hide foreign accounts (404, not 500)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import InvestmentAccountRow, InvestorProfileRow
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.principal import (
    DEFAULT_APP_PRINCIPAL,
    account_visible_to_principal,
    resolve_app_principal,
)
from bolsa_api.auth.session import SESSION_COOKIE_NAME
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


async def _insert_raw_profile(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
) -> str:
    profile_id = f"PROF-{uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            InvestorProfileRow(
                id=profile_id,
                name=name,
                version="1.0.0",
                user_id=user_id,
                horizon="swing",
                objectives=["growth"],
                risk_tolerance="moderate",
                experience="intermediate",
                suggested_policy_template_id="moderate",
                selected_policy_template_id="moderate",
                updated_by="user",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()
    return profile_id


async def _delete_raw_profile(
    factory: async_sessionmaker[AsyncSession],
    profile_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(InvestorProfileRow, profile_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


def test_resolve_app_principal_defaults_to_app() -> None:
    get_settings.cache_clear()
    assert resolve_app_principal(get_settings()) == DEFAULT_APP_PRINCIPAL
    get_settings.cache_clear()


def test_account_visible_to_principal_f7c_strict() -> None:
    get_settings.cache_clear()
    bootstrap = resolve_app_principal(get_settings())
    assert account_visible_to_principal(None, bootstrap) is False
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
        "bolsa_api.api.v1.routes.investor_profiles.get_request_principal",
        "bolsa_api.api.v1.routes.trackers.get_request_principal",
        "bolsa_api.api.v1.routes.execution_policies.get_request_principal",
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
    """F7c: legacy ``user_id is None`` invisible también para no-bootstrap."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_account(
            factory, user_id=None, name="Legacy F7c isolation"
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
async def test_list_active_accounts_filters_by_owner_user_id() -> None:
    """F8 G4: list_active_accounts con owner_user_id aplica visibilidad F7c."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        user_a_id = await _insert_raw_account(
            factory, user_id="user-a", name="Active A"
        )
        user_b_id = await _insert_raw_account(
            factory, user_id="user-b", name="Active B"
        )
        try:
            async with factory() as session:
                repo = SqlAlchemyAccountRepository(session)
                scoped = await repo.list_active_accounts(owner_user_id="user-a")
                ids = {a.id for a in scoped}
                assert user_a_id in ids
                assert user_b_id not in ids

                system = await repo.list_active_accounts(for_custody_job=True)
                system_ids = {a.id for a in system}
                assert user_a_id in system_ids
                assert user_b_id in system_ids
        finally:
            await _delete_raw_account(factory, user_a_id)
            await _delete_raw_account(factory, user_b_id)


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_investor_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8 G6: perfiles inversor scoped al principal JWT."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        profile_a = await _insert_raw_profile(
            factory, user_id="user-a", name="Profile A isolation"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/investor-profiles/{profile_a}")
                assert response.status_code == 404

                listed = await client.get("/api/investor-profiles")
                assert listed.status_code == 200
                ids = {row["profileId"] for row in listed.json()["data"]}
                assert profile_a not in ids
        finally:
            await _delete_raw_profile(factory, profile_a)


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
            factory = app.state.session_factory
            async with factory() as session:
                repo = SqlAlchemyUserRepository(session)
                user = await repo.get_by_id("app")
                assert user is not None
                token = encode_access_token(
                    get_settings(),
                    sub=user.id,
                    sv=user.session_version,
                    role=user.role,
                )
            client.cookies.set(SESSION_COOKIE_NAME, token)
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
async def test_legacy_null_user_id_account_hidden_from_bootstrap() -> None:
    """F7c: bootstrap no ve cuentas legacy ``user_id is None`` (404 / no list)."""
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
                assert response.status_code == 404

                listed = await client.get("/api/accounts")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
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
                async with factory() as session:
                    repo = SqlAlchemyUserRepository(session)
                    user = await repo.get_by_id("app")
                    assert user is not None
                    token = encode_access_token(
                        get_settings(),
                        sub=user.id,
                        sv=user.session_version,
                        role=user.role,
                    )
                client.cookies.set(SESSION_COOKIE_NAME, token)
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
    """F7c: deposit sobre cuenta legacy NULL es 404 (huérfano invisible)."""
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
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, legacy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_core_r_hidden_from_bootstrap() -> None:
    """F7c: core-r sobre cuenta legacy NULL es 404 para bootstrap."""
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
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, legacy_id)
