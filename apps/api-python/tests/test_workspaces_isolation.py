"""R12-AUTH F8d: workspaces scoped by JWT principal."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bolsa_infrastructure.database.models import WorkspaceRow
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
        "bolsa_api.api.v1.routes.workspaces.get_request_principal",
    ):
        monkeypatch.setattr(target, fake)


async def _insert_raw_workspace(
    factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str | None,
    name: str,
    is_default: bool = False,
) -> str:
    workspace_id = f"ws-{uuid4().hex[:12]}"
    now = _now()
    async with factory() as session:
        session.add(
            WorkspaceRow(
                id=workspace_id,
                user_id=user_id,
                name=name,
                document={"version": 1, "id": workspace_id, "name": name},
                dock_layout=None,
                is_default=is_default,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return workspace_id


async def _delete_raw_workspace(
    factory: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> None:
    async with factory() as session:
        row = await session.get(WorkspaceRow, workspace_id)
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_user_b_cannot_see_user_a_workspaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8d: workspaces scoped al principal JWT."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        workspace_a = await _insert_raw_workspace(
            factory,
            user_id="user-a",
            name="Workspace A isolation",
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/workspaces/{workspace_a}")
                assert response.status_code == 404

                listed = await client.get("/api/workspaces")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert workspace_a not in ids
        finally:
            await _delete_raw_workspace(factory, workspace_a)


@pytest.mark.asyncio
async def test_user_b_cannot_update_or_delete_user_a_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        workspace_a = await _insert_raw_workspace(
            factory,
            user_id="user-a",
            name="Workspace A mutate guard",
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                update_resp = await client.put(
                    f"/api/workspaces/{workspace_a}",
                    json={"name": "Hijacked"},
                )
                assert update_resp.status_code == 404

                delete_resp = await client.delete(f"/api/workspaces/{workspace_a}")
                assert delete_resp.status_code == 404
        finally:
            await _delete_raw_workspace(factory, workspace_a)


@pytest.mark.asyncio
async def test_legacy_null_user_id_workspace_hidden_from_non_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8d F7c: legacy workspace ``user_id is None`` invisible también para no-bootstrap."""
    _patch_request_principal(monkeypatch, "user-b")
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_workspace(
            factory,
            user_id=None,
            name="Legacy workspace isolation",
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/workspaces/{legacy_id}")
                assert response.status_code == 404

                listed = await client.get("/api/workspaces")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_workspace(factory, legacy_id)


@pytest.mark.asyncio
async def test_legacy_null_user_id_workspace_hidden_from_bootstrap() -> None:
    """F8d F7c: bootstrap no ve workspaces legacy ``user_id is None``."""
    app = create_app()
    async with lifespan(app):
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        legacy_id = await _insert_raw_workspace(
            factory,
            user_id=None,
            name="Legacy workspace bootstrap",
        )
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/workspaces/{legacy_id}")
                assert response.status_code == 404

                listed = await client.get("/api/workspaces")
                assert listed.status_code == 200
                ids = {row["id"] for row in listed.json()["data"]}
                assert legacy_id not in ids
        finally:
            await _delete_raw_workspace(factory, legacy_id)


@pytest.mark.asyncio
async def test_get_default_workspace_is_per_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada principal obtiene o crea su propio default sin ver el de otros."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            _patch_request_principal(monkeypatch, "user-a")
            default_a = await client.get("/api/workspaces/default")
            assert default_a.status_code == 200
            id_a = default_a.json()["data"]["id"]

            _patch_request_principal(monkeypatch, "user-b")
            default_b = await client.get("/api/workspaces/default")
            assert default_b.status_code == 200
            id_b = default_b.json()["data"]["id"]
            assert id_a != id_b


@pytest.mark.asyncio
async def test_bootstrap_principal_constant_matches_default() -> None:
    assert DEFAULT_APP_PRINCIPAL == "app"
