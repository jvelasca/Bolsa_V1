"""V1.87 — lifecycle HTTP: JWT required, account isolation, extra=forbid."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.session import SESSION_COOKIE_NAME
from bolsa_api.main import create_app, lifespan
from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import InvestmentAccountRow, UserRow


def _now() -> datetime:
    return datetime.now(UTC)


def _load_env() -> None:
    """Carga el ``.env`` de la raíz (convención del resto de tests PG de ``api-python``).

    ``test_lifecycle_auth`` ejercita el lifespan real de la API, que abre conexión a
    PostgreSQL; sin esto dependía de que las variables ya estuvieran exportadas en el
    shell y fallaba con ``fe_sendauth: no password supplied`` en ejecución aislada.
    """
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — dep opcional
        return
    load_dotenv(env_path, override=False)


async def _insert_user(
    factory: async_sessionmaker[AsyncSession], *, user_id: str
) -> None:
    async with factory() as session:
        existing = await session.get(UserRow, user_id)
        if existing is None:
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
    account_id = f"lc-{uuid4().hex[:16]}"
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
                initial_deposit=Decimal("1000"),
                leverage=Decimal("1"),
                is_default=False,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await session.commit()
    return account_id


async def _jwt(
    factory: async_sessionmaker[AsyncSession], user_id: str
) -> str:
    settings = get_settings()
    async with factory() as session:
        user = await session.get(UserRow, user_id)
        assert user is not None
        return encode_access_token(
            settings, sub=user.id, sv=user.session_version, role=user.role
        )


async def _cleanup_tenant(
    factory: async_sessionmaker[AsyncSession], *, user_ids: list[str]
) -> None:
    """Borra las cuentas y usuarios creados por el test (no deja residuo en la BD).

    Sin esto, cada ejecución dejaba cuentas ``is_default=True`` con ``user_id`` ajeno al
    owner de la app. Eso rompía el arranque de la API (``_load_default_scope`` lanzaba
    ``MultipleResultsFound``), y el residuo se volvía indistinguible de datos reales.
    El borrado respeta el orden de claves foráneas y nunca toca la cuenta demo.
    """
    async with factory() as session:
        for user_id in user_ids:
            account_ids = (
                await session.execute(
                    text(
                        "SELECT id FROM investment_accounts "
                        "WHERE user_id = :uid AND id <> 'default-account-seed'"
                    ),
                    {"uid": user_id},
                )
            ).scalars().all()
            for account_id in account_ids:
                portfolio_ids = (
                    await session.execute(
                        text(
                            "SELECT id FROM investment_portfolios "
                            "WHERE account_id = :aid"
                        ),
                        {"aid": account_id},
                    )
                ).scalars().all()
                for table in (
                    "core_r_account_state",
                    "supervised_f3_account_state",
                    "custody_obligation",
                    "custody_obligations",
                    "execution_policies",
                    "position_policies",
                    "pending_orders",
                    "mandate_tenures",
                    "position_states",
                    "ledger_entries",
                ):
                    await session.execute(
                        text(f"DELETE FROM {table} WHERE account_id = :aid"),
                        {"aid": account_id},
                    )
                for portfolio_id in portfolio_ids:
                    await session.execute(
                        text("DELETE FROM ledger_entries WHERE portfolio_id = :pid"),
                        {"pid": portfolio_id},
                    )
                await session.execute(
                    text("DELETE FROM investment_portfolios WHERE account_id = :aid"),
                    {"aid": account_id},
                )
                await session.execute(
                    text("DELETE FROM investment_accounts WHERE id = :aid"),
                    {"aid": account_id},
                )
            await session.execute(
                text("DELETE FROM users WHERE id = :uid"), {"uid": user_id}
            )
        await session.commit()


@pytest.fixture
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _load_env()
    monkeypatch.setenv("APP_AUTH_SECRET", "lifecycle-auth-test-secret-key-32b")
    monkeypatch.setenv("JWT_SIGNING_KEY", "lifecycle-auth-test-secret-key-32b")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifecycle_unauthenticated_is_401(auth_secret: None) -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post = await client.post(
                "/api/lifecycle/events",
                json={"kind": "POSITION_OPENED", "accountId": "x", "positionId": "p"},
            )
            assert post.status_code == 401
            get = await client.get("/api/lifecycle/positions/p/snapshot")
            assert get.status_code == 401
            stats = await client.get(
                "/api/lifecycle/outbox/stats",
                params={"accountId": "x"},
            )
            assert stats.status_code == 401
            recon = await client.get(
                "/api/lifecycle/reconciliation",
                params={"accountId": "x"},
            )
            assert recon.status_code == 401
            integrity = await client.get(
                "/api/lifecycle/integrity",
                params={"accountId": "x"},
            )
            assert integrity.status_code == 401


@pytest.mark.asyncio
async def test_lifecycle_unknown_field_is_422(auth_secret: None) -> None:
    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        await _insert_user(factory, user_id="user-a")
        token = await _jwt(factory, "user-a")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, token)
            response = await client.post(
                "/api/lifecycle/events",
                json={
                    "kind": "POSITION_OPENED",
                    "accountId": "acc-a",
                    "positionId": "pos-typo",
                    "quanity": 5,
                },
            )
            assert response.status_code == 422
        await _cleanup_tenant(factory, user_ids=["user-a"])


@pytest.mark.asyncio
async def test_lifecycle_owner_ok_foreign_403(auth_secret: None) -> None:
    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        await _insert_user(factory, user_id="user-a")
        await _insert_user(factory, user_id="user-b")
        acc_a = await _insert_account(factory, user_id="user-a", name="A")
        await _insert_account(factory, user_id="user-b", name="B")
        pos = f"pos-iso-{uuid4().hex[:10]}"
        token_a = await _jwt(factory, "user-a")
        token_b = await _jwt(factory, "user-b")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, token_a)
            opened = await client.post(
                "/api/lifecycle/events",
                json={
                    "kind": "POSITION_OPENED",
                    "accountId": acc_a,
                    "positionId": pos,
                },
            )
            assert opened.status_code == 200, opened.text
            own = await client.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert own.status_code == 200
            assert own.json()["data"]["stage"] == "open"
            assert own.json()["data"]["events"][0]["sequenceNo"] == 1

            client.cookies.set(SESSION_COOKIE_NAME, token_b)
            foreign_get = await client.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert foreign_get.status_code == 403
            foreign_post = await client.post(
                "/api/lifecycle/events",
                json={
                    "kind": "T1_EXECUTED",
                    "accountId": acc_a,
                    "positionId": pos,
                },
            )
            assert foreign_post.status_code == 403
        await _cleanup_tenant(factory, user_ids=["user-a", "user-b"])
