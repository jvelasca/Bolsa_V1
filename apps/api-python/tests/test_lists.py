import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


@pytest.mark.asyncio
async def test_lists_crud_flow() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            lists_response = await client.get("/api/lists")
            assert lists_response.status_code == 200
            lists_body = lists_response.json()["data"]
            assert len(lists_body) >= 1
            ibex = next((item for item in lists_body if item["name"] == "IBEX 35"), lists_body[0])
            list_id = ibex["id"]

            quotes_response = await client.get(f"/api/lists/{list_id}/quotes")
            assert quotes_response.status_code == 200
            assert len(quotes_response.json()["data"]) >= 1

            create_response = await client.post(
                "/api/lists",
                json={
                    "name": "Test lista",
                    "instrumentIds": [quotes_response.json()["data"][0]["id"]],
                },
            )
            assert create_response.status_code == 201
            created_id = create_response.json()["data"]["id"]

            patch_response = await client.patch(
                f"/api/lists/{created_id}",
                json={"name": "Test lista renombrada"},
            )
            assert patch_response.status_code == 200
            assert patch_response.json()["data"]["name"] == "Test lista renombrada"

            delete_response = await client.delete(f"/api/lists/{created_id}")
            assert delete_response.status_code == 204
