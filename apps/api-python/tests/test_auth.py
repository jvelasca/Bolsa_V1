import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


@pytest.mark.asyncio
async def test_auth_status_without_password() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json()["data"]["authEnabled"] is False


@pytest.mark.asyncio
async def test_login_when_auth_disabled() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "anything"})

    assert response.status_code == 200
    assert "token" in response.json()["data"]
