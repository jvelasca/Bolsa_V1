import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


@pytest.mark.asyncio
async def test_workspaces_crud() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            default_resp = await client.get("/api/workspaces/default")
            assert default_resp.status_code == 200
            default_id = default_resp.json()["data"]["id"]

            create_resp = await client.post(
                "/api/workspaces",
                json={"name": "Swing IBEX", "isDefault": False},
            )
            assert create_resp.status_code == 201
            created_id = create_resp.json()["data"]["id"]

            list_resp = await client.get("/api/workspaces")
            assert list_resp.status_code == 200
            assert len(list_resp.json()["data"]) >= 2

            update_resp = await client.put(
                f"/api/workspaces/{created_id}",
                json={"name": "Swing IBEX v2"},
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["data"]["name"] == "Swing IBEX v2"

            delete_resp = await client.delete(f"/api/workspaces/{created_id}")
            assert delete_resp.status_code == 204

            guard_resp = await client.delete(f"/api/workspaces/{default_id}")
            assert guard_resp.status_code == 400
