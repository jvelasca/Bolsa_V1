"""R12-AUTH fase 1: stamp ``user_id`` and hide foreign accounts (404, not 500)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
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
from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import (
    DecisionMemoryRow,
    DecisionSessionRow,
    InvestmentAccountRow,
    InvestorProfileRow,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository


def _now() -> datetime:
    return datetime.now(UTC)


async def _ensure_app_user(factory: async_sessionmaker[AsyncSession]) -> None:
    """Idempotente: crea el user bootstrap ``app`` (login ``app``, password
    ``s3cret``) si no existe. Los tests auth-ON necesitan un user real para
    emitir su JWT; NO deben depender del estado previo de seeding de la BD
    del job (CI puede arrancar sin ``app``). Reutiliza el hash del password
    del test (``monkeypatch.setenv APP_PASSWORD=s3cret``)."""
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        existing = await repo.get_by_id("app")
        if existing is not None:
            return
        if await repo.get_by_login("app") is not None:
            return
        await repo.create_bootstrap_user(
            user_id="app",
            login="app",
            password_hash=hash_password("s3cret"),
            role="admin",
        )


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


async def _insert_raw_decision_session(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str | None,
    kind: str = "propose",
) -> str:
    session_id = f"DS-{uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            DecisionSessionRow(
                id=session_id,
                kind=kind,
                status="open",
                instrument_id="IB.ANY",
                account_id=account_id,
                symbol="XXX",
                payload={"probe": "v2154"},
                created_at=_now(),
            )
        )
        await session.commit()
    return session_id


async def _insert_raw_decision_memory(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str | None,
    outcome: str = "accepted",
    decision_id: str | None = None,
) -> str:
    mem_id = f"DM-{uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            DecisionMemoryRow(
                id=mem_id,
                decision_id=decision_id or f"DEC-{uuid4().hex[:8]}",
                instrument_id="IB.ANY",
                account_id=account_id,
                outcome=outcome,
                reasons=["Policy PASS"],
                policy_rule_ids=[],
                reevaluate_when=[],
                opportunity_intact=True,
                payload={"probe": "v2154"},
                created_at=_now(),
            )
        )
        await session.commit()
    return mem_id


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
    try:
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                factory = app.state.session_factory
                await _ensure_app_user(factory)
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
    finally:
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
    try:
        async with lifespan(app):
            factory: async_sessionmaker[AsyncSession] = app.state.session_factory
            await _ensure_app_user(factory)
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
    finally:
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


@pytest.mark.asyncio
async def test_reading_study_effectiveness_foreign_account_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A1 residual (lectura/estudio): /ai/effectiveness de cuenta ajena → 404."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        owner_id = await _insert_raw_account(
            factory, user_id="user-a", name="Owner A5"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/ai/effectiveness",
                    params={"accountId": owner_id},
                )
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, owner_id)


@pytest.mark.asyncio
async def test_reading_study_decision_sessions_foreign_account_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A1 residual: /ai/decision-sessions de cuenta ajena → 404."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        owner_id = await _insert_raw_account(
            factory, user_id="user-a", name="Owner A6"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/ai/decision-sessions",
                    params={"accountId": owner_id},
                )
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, owner_id)


@pytest.mark.asyncio
async def test_risk_ops_self_eval_foreign_account_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A1 residual: /risk/ops-self-eval de cuenta ajena → 404."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        owner_id = await _insert_raw_account(
            factory, user_id="user-a", name="Owner A7"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/risk/ops-self-eval",
                    params={"accountId": owner_id},
                )
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, owner_id)


@pytest.mark.asyncio
async def test_paper_desk_daily_report_foreign_account_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A1 residual: /paper-desk/daily-report de cuenta ajena → 404."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        owner_id = await _insert_raw_account(
            factory, user_id="user-a", name="Owner A8"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/paper-desk/daily-report",
                    params={"accountId": owner_id},
                )
                assert response.status_code == 404
        finally:
            await _delete_raw_account(factory, owner_id)


@pytest.mark.asyncio
async def test_accountless_decision_sessions_scoped_to_principal_default_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2.15.4 A1: /ai/decision-sessions SIN accountId NO es global.

    Principal user-a con su cuenta default: la lista acount-less debe devolver solo
    las sesiones de la cuenta default de user-a, excluyendo las de la cuenta ajena
    (user-b) y las huérfanas (account_id=None).
    """
    _patch_request_principal(monkeypatch, "user-a")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        acc_a = await _insert_raw_account(
            factory, user_id="user-a", name="A default"
        )
        acc_b = await _insert_raw_account(
            factory, user_id="user-b", name="B account"
        )
        session_a = await _insert_raw_decision_session(factory, account_id=acc_a)
        session_b = await _insert_raw_decision_session(factory, account_id=acc_b)
        session_orphan = await _insert_raw_decision_session(factory, account_id=None)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/ai/decision-sessions")
                assert listed.status_code == 200
                ids = {row["sessionId"] for row in listed.json()["data"]}
                assert session_a in ids
                assert session_b not in ids
                assert session_orphan not in ids
        finally:
            await _delete_raw_account(factory, acc_a)
            await _delete_raw_account(factory, acc_b)


@pytest.mark.asyncio
async def test_accountless_scoped_by_principal_default_not_a_when_b_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2.15.4 A1: user-b acount-less ve su default, nunca las sesiones de user-a."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        acc_a = await _insert_raw_account(
            factory, user_id="user-a", name="A default"
        )
        acc_b = await _insert_raw_account(
            factory, user_id="user-b", name="B default"
        )
        session_a = await _insert_raw_decision_session(factory, account_id=acc_a)
        session_b = await _insert_raw_decision_session(factory, account_id=acc_b)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/ai/decision-sessions")
                assert listed.status_code == 200
                ids = {row["sessionId"] for row in listed.json()["data"]}
                assert session_a not in ids
                assert session_b in ids
        finally:
            await _delete_raw_account(factory, acc_a)
            await _delete_raw_account(factory, acc_b)


@pytest.mark.asyncio
async def test_accountless_effectiveness_scoped_to_principal_default_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2.15.4 A1: /ai/effectiveness SIN accountId NO es global.

    user-a principal sin memorias propias; user-b y datos huérfanos existen en el
    store. Account-less debe acotarse a la default de user-a y NO contarlas.
    """
    _patch_request_principal(monkeypatch, "user-a")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        acc_a = await _insert_raw_account(factory, user_id="user-a", name="Eff A")
        acc_b = await _insert_raw_account(factory, user_id="user-b", name="Eff B")
        _mem_b = await _insert_raw_decision_memory(
            factory, account_id=acc_b, outcome="rejected"
        )
        _mem_or = await _insert_raw_decision_memory(
            factory, account_id=None, outcome="rejected"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/ai/effectiveness")
                assert resp.status_code == 200
                body = resp.json()["data"]
                assert body.get("source") == "postgres"
                # Scope a acc_a (default de user-a): NO ve memorias de user-b ni huérfanas.
                assert body["persistence"]["decisionMemoryCount"] == 0
        finally:
            await _delete_raw_account(factory, acc_a)
            await _delete_raw_account(factory, acc_b)


@pytest.mark.asyncio
async def test_refresh_observed_accountless_does_not_read_foreign_or_orphan_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V2.15.4 A1: refresh-observed account-less NO lee memorias ajenas/huérfanas.

    Principal user-b sin cuenta propia activa → al omitir accountId (account-less)
    debe ser fail-closed (404), nunca degradar a memoria global ajena; y si viene un
    accountId ajeno (cuenta de user-a) también debe ser 404.
    """
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        acc_a = await _insert_raw_account(factory, user_id="user-a", name="Pfx A")
        _mem_a = await _insert_raw_decision_memory(factory, account_id=acc_a)
        _mem_or_global = await _insert_raw_decision_memory(factory, account_id=None)
        profile_b = await _insert_raw_profile(
            factory, user_id="user-b", name="Profile B"
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                foreign = await client.post(
                    f"/api/investor-profiles/{profile_b}/refresh-observed",
                    params={"accountId": acc_a},
                )
                assert foreign.status_code == 404
                accountless = await client.post(
                    f"/api/investor-profiles/{profile_b}/refresh-observed",
                )
                assert accountless.status_code == 404
        finally:
            await _delete_raw_profile(factory, profile_b)
            await _delete_raw_account(factory, acc_a)


async def _account_is_default(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> bool:
    async with factory() as session:
        row = await session.get(InvestmentAccountRow, account_id)
        assert row is not None
        return bool(row.is_default)


@pytest.mark.asyncio
async def test_set_default_account_is_owner_scoped() -> None:
    """P1-02: ``set_default_account`` en user-a NO desmarca el default de user-b.

    Escenario repo-level (frente al repo real, no al guard HTTP): user-a marca su
    default con dos cuentas propias (A1 default actual, A2), mientras user-b tiene
    B1 marcada default. Al promocionar A2 a default, A1 debe perder el flag pero
    B1 de user-b DEBE seguir ``is_default`` — el UPDATE debe ser owner-scoped.
    """
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        a1 = await _insert_raw_account(factory, user_id="user-a", name="A1 default")
        a2 = await _insert_raw_account(factory, user_id="user-a", name="A2 candidate")
        b1 = await _insert_raw_account(factory, user_id="user-b", name="B1 default")
        try:
            async with factory() as session:
                repo = SqlAlchemyAccountRepository(session)
                # Estado inicial: A1 default de user-a; B1 default de user-b.
                await repo.set_default_account(a1, owner_user_id="user-a")
                await repo.set_default_account(b1, owner_user_id="user-b")
                # Promoción dentro de user-a: A2 deja de ser default de B1.
                await repo.set_default_account(a2, owner_user_id="user-a")
                await session.commit()

            assert await _account_is_default(factory, a2) is True
            assert await _account_is_default(factory, a1) is False
            # B1 (otro tenant) NO debe haberse tocado.
            assert await _account_is_default(factory, b1) is True
        finally:
            await _delete_raw_account(factory, a1)
            await _delete_raw_account(factory, a2)
            await _delete_raw_account(factory, b1)


@pytest.mark.asyncio
async def test_delete_default_promotion_is_owner_local() -> None:
    """P1-03: eliminar un default promueve el siguiente default del MISMO owner.

    Se dispone el escenario para que la promoción GLOBAL (el bug) eligiera un
    default AJENO: B1 (de user-b) se inserta PRIMERO → es la 'activa' más antigua
    global entre las supervivientes. Al borrar el default A1 de user-a, la
    promoción owner-scoped DEBE elegir A2 (candidata del propio user-a) y NO B1.
    """
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        # B1 PRIMERO ⇒ created_at más antiguo ⇒ la promoción global caería sobre B1.
        b1 = await _insert_raw_account(factory, user_id="user-b", name="B1 active foreign")
        a1 = await _insert_raw_account(factory, user_id="user-a", name="A1 default")
        a2 = await _insert_raw_account(factory, user_id="user-a", name="A2 candidate")
        try:
            async with factory() as session:
                repo = SqlAlchemyAccountRepository(session)
                await repo.set_default_account(a1, owner_user_id="user-a")
                await repo.set_default_account(b1, owner_user_id="user-b")
                await session.commit()

            # user-a cierra su cuenta default para poder eliminarla.
            async with factory() as session:
                repo = SqlAlchemyAccountRepository(session)
                await repo.close_account(a1)
                await session.commit()
            # Elimina la cuenta default de user-a (close previo ya hecho).
            async with factory() as session:
                repo = SqlAlchemyAccountRepository(session)
                await repo.delete_simulated_account(a1, owner_user_id="user-a")
                await session.commit()

            # A2 se promueve como default de user-a (owner-local), NO B1 a pesar de
            # que B1 era la 'activa' más antigua del conjunto global.
            assert await _account_is_default(factory, a2) is True
            assert await _account_is_default(factory, b1) is True  # default legítimo de user-b
        finally:
            await _delete_raw_account(factory, a2)
            await _delete_raw_account(factory, b1)
