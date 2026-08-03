import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_json(app) -> None:
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "bolsa-api-python"
    assert body["stack"] == "python-fastapi"
    assert "database" in body
    assert "yahoo" in body["components"]
    assert "redis" in body["components"]
    assert "circuit" in body["components"]["yahoo"].get("details", {})
