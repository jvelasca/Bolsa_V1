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


@pytest.mark.asyncio
async def test_health_redacts_internal_details(app) -> None:
    """P2.5 — /api/health no debe filtrar URLs, hosts, claves internas ni DSNs."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    # DB: en fallo el mensaje debe ser genérico, nunca una excepción cruda.
    if (body.get("database") or {}).get("status") != "ok":
        assert body["database"]["message"] == "PostgreSQL inaccesible"
    # Ningún componente debe colar un DSN ni una excepción cruda.
    for component in body["components"].values():
        message = (component.get("message") or "").lower()
        assert "connection refused" not in message
        assert "psycopg" not in message
        assert "redis://" not in message
        assert "password" not in message
        assert "postgresql://" not in message
    # XTB configurado: estado sin exponer la URL real.
    xtb = body["components"].get("xtb") or {}
    if xtb.get("status") == "configured":
        assert "http" not in (xtb.get("message") or "").lower()
