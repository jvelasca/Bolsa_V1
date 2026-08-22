"""R12-AUTH F8c: platform events scoped by JWT principal."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bolsa_infrastructure.database.models import PlatformEventRow
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.auth.principal import DEFAULT_APP_PRINCIPAL
from bolsa_api.main import create_app, lifespan


def _now() -> datetime:
    return datetime.now(UTC)


def _patch_request_principal(monkeypatch: pytest.MonkeyPatch, principal: str) -> None:
    def fake(_request: object) -> str:
        return principal

    for target in (
        "bolsa_api.auth.request_principal.get_request_principal",
        "bolsa_api.api.dependencies.get_request_principal",
        "bolsa_api.api.v1.routes.platform_events.get_request_principal",
    ):
        monkeypatch.setattr(target, fake)


async def _insert_raw_platform_event(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    event_type: str = "test.isolation",
) -> str:
    event_id = f"evt-{uuid4().hex[:12]}"
    async with factory() as session:
        session.add(
            PlatformEventRow(
                id=event_id,
                type=event_type,
                payload={"source": "isolation-test"},
                correlation_id=None,
                user_id=user_id,
                created_at=_now(),
            )
        )
        await session.commit()
    return event_id


async def _delete_raw_platform_event(
    factory: async_sessionmaker[AsyncSession],
    event_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(PlatformEventRow, event_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_platform_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8c G6: platform events scoped al principal JWT."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        event_a = await _insert_raw_platform_event(factory, user_id="user-a")
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/platform-events")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert event_a not in ids
        finally:
            await _delete_raw_platform_event(factory, event_a)


@pytest.mark.asyncio
async def test_user_a_sees_own_platform_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_principal(monkeypatch, "user-a")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        event_a = await _insert_raw_platform_event(factory, user_id="user-a")
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/platform-events")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert event_a in ids
        finally:
            await _delete_raw_platform_event(factory, event_a)


@pytest.mark.asyncio
async def test_legacy_null_user_id_event_hidden_from_non_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8c F7c: legacy ``user_id is None`` invisible también para no-bootstrap."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_platform_event(factory, user_id=None)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/platform-events")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_platform_event(factory, legacy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_event_hidden_from_bootstrap() -> None:
    """F8c F7c: bootstrap no ve events legacy ``user_id is None``."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_platform_event(factory, user_id=None)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                listed = await client.get("/api/platform-events")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_platform_event(factory, legacy_id)


@pytest.mark.asyncio
async def test_bootstrap_principal_constant_matches_default() -> None:
    assert DEFAULT_APP_PRINCIPAL == "app"
