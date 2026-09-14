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

            # La lista borrada no debe reaparecer en el catálogo.
            after_response = await client.get("/api/lists")
            assert after_response.status_code == 200
            ids_after = {item["id"] for item in after_response.json()["data"]}
            assert created_id not in ids_after


@pytest.mark.asyncio
async def test_delete_list_with_items_does_not_violate_fk() -> None:
    """Regresión: borrar una lista CON instrumentos debe funcionar (204), no 500.

    ``instrument_list_items.list_id`` no es ``ON DELETE CASCADE``. El repositorio
    borraba la fila de ``instrument_lists`` directamente, así que cualquier lista con
    items violaba la FK y la API devolvía 500. Este test fija el contrato: se crea una
    lista con un instrumento real, se verifica que tiene items y se borra.
    """
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            lists_body = (await client.get("/api/lists")).json()["data"]
            assert lists_body, "premisa: hay listas sembradas"
            list_id = lists_body[0]["id"]
            quotes = (await client.get(f"/api/lists/{list_id}/quotes")).json()["data"]
            assert quotes, "premisa: la lista tiene instrumentos"

            created = await client.post(
                "/api/lists",
                json={
                    "name": f"Lista con items {list_id}",
                    "instrumentIds": [quotes[0]["id"]],
                },
            )
            assert created.status_code == 201
            created_id = created.json()["data"]["id"]

            detail = await client.get(f"/api/lists/{created_id}/quotes")
            assert detail.status_code == 200
            assert len(detail.json()["data"]) >= 1, "la lista debe tener items que la referencien"

            deleted = await client.delete(f"/api/lists/{created_id}")
            assert deleted.status_code == 204, (
                f"borrar una lista con items debe dar 204, no {deleted.status_code}"
            )
            assert (await client.get(f"/api/lists/{created_id}/quotes")).status_code == 404
