"""V1.88 — Lifecycle integrated golden: JWT trail + recon + API restart + isolation.

Requires PostgreSQL (same gate as lifecycle-pg: LIFECYCLE_PG_REQUIRED=1 fails hard).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.auth.session import SESSION_COOKIE_NAME
from bolsa_api.main import create_app, lifespan
from bolsa_application.operational_incident_store import (
    PostgresOperationalIncidentStore,
    sync_opening_incidents,
)
from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import InvestmentAccountRow, UserRow


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
    account_id = f"lc-g-{uuid4().hex[:14]}"
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


async def _jwt(factory: async_sessionmaker[AsyncSession], user_id: str) -> str:
    settings = get_settings()
    async with factory() as session:
        user = await session.get(UserRow, user_id)
        assert user is not None
        return encode_access_token(
            settings, sub=user.id, sv=user.session_version, role=user.role
        )


async def _post_event(
    client: AsyncClient, *, account_id: str, position_id: str, kind: str
) -> dict:
    response = await client.post(
        "/api/lifecycle/events",
        json={
            "kind": kind,
            "accountId": account_id,
            "positionId": position_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["ok"] is True
    return body


@pytest.fixture
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # APP_PASSWORD ON so AuthMiddleware attaches JWT principal (accounts HTTP).
    monkeypatch.setenv("APP_PASSWORD", "lifecycle-golden-test-password")
    monkeypatch.setenv("APP_AUTH_SECRET", "lifecycle-golden-test-secret-key-32b")
    monkeypatch.setenv("JWT_SIGNING_KEY", "lifecycle-golden-test-secret-key-32b")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_v188_golden_trail_recon_restart_isolation(
    auth_secret: None,
) -> None:
    pos = f"pos-g188-{uuid4().hex[:10]}"
    user_a = f"user-a-{uuid4().hex[:8]}"
    user_b = f"user-b-{uuid4().hex[:8]}"

    try:
        app1 = create_app()
    except Exception as exc:  # noqa: BLE001
        _require_or_skip(exc)
        raise

    snap_before_restart: dict
    acc_a: str
    token_a: str
    token_b: str

    async with lifespan(app1):
        factory = app1.state.session_factory
        await _insert_user(factory, user_id=user_a)
        await _insert_user(factory, user_id=user_b)
        acc_a = await _insert_account(factory, user_id=user_a, name="Golden A")
        await _insert_account(factory, user_id=user_b, name="Golden B")
        token_a = await _jwt(factory, user_a)
        token_b = await _jwt(factory, user_b)

        transport = ASGITransport(app=app1)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, token_a)

            await _post_event(
                client, account_id=acc_a, position_id=pos, kind="POSITION_OPENED"
            )
            await _post_event(
                client, account_id=acc_a, position_id=pos, kind="T1_EXECUTED"
            )

            # RECON DRIFT mid-journey (DEX-3): open portfolio_drift incident
            async with factory() as session:
                store = PostgresOperationalIncidentStore(session)
                status = await sync_opening_incidents(
                    store,
                    account_id=acc_a,
                    portfolio_recon_status="drift",
                    broker_venue="paper",
                )
                assert status == "unresolved"
                active = await store.list_active(acc_a)
                assert len(active) == 1
                incident_id = active[0].incident_id

            mid = await client.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert mid.status_code == 200
            assert mid.json()["data"]["stage"] == "t1_executed"

            # RECOVERY via HTTP (V1.89): resolve + clear uses recon_status_for_incident_clear
            # Books are clean → clear succeeds through server lookup (no store bypass).
            resolved = await client.post(
                f"/api/accounts/{acc_a}/operational-incidents/{incident_id}/resolve",
                json={
                    "resolutionNote": "v188-golden-manual-recon-clean",
                    "resolvedBy": user_a,
                },
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["data"]["status"] == "resolved"

            cleared = await client.post(
                f"/api/accounts/{acc_a}/operational-incidents/{incident_id}/clear",
            )
            assert cleared.status_code == 200, cleared.text
            assert cleared.json()["data"]["status"] == "cleared"

            active_after = await client.get(
                f"/api/accounts/{acc_a}/operational-incidents/active",
            )
            assert active_after.status_code == 200
            assert active_after.json()["data"]["total"] == 0

            for kind in ("TRAIL_APPLIED", "EXIT_REQUIRED", "POSITION_CLOSED"):
                await _post_event(
                    client, account_id=acc_a, position_id=pos, kind=kind
                )

            closed = await client.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert closed.status_code == 200
            snap_before_restart = closed.json()["data"]
            assert snap_before_restart["stage"] == "closed"
            assert snap_before_restart["accounting"]["cash"] == 100_055
            assert snap_before_restart["accounting"]["totalEquity"] == 100_055
            seqs = [e["sequenceNo"] for e in snap_before_restart["events"]]
            assert seqs == list(range(1, len(seqs) + 1))

            client.cookies.set(SESSION_COOKIE_NAME, token_b)
            foreign = await client.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert foreign.status_code == 403

    # STOP API / START API — new process semantics via new create_app + lifespan
    app2 = create_app()
    async with lifespan(app2):
        transport2 = ASGITransport(app=app2)
        async with AsyncClient(transport=transport2, base_url="http://test") as client2:
            client2.cookies.set(SESSION_COOKIE_NAME, token_a)
            after = await client2.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert after.status_code == 200
            snap2 = after.json()["data"]
            assert snap2["stage"] == snap_before_restart["stage"]
            assert snap2["accounting"] == snap_before_restart["accounting"]
            assert [e["sequenceNo"] for e in snap2["events"]] == [
                e["sequenceNo"] for e in snap_before_restart["events"]
            ]
            assert len(snap2["events"]) == len(snap_before_restart["events"])

            client2.cookies.set(SESSION_COOKIE_NAME, token_b)
            foreign2 = await client2.get(f"/api/lifecycle/positions/{pos}/snapshot")
            assert foreign2.status_code == 403
