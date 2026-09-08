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
async def test_health_reports_provenance(app) -> None:
    """/api/health → bloque provenance (identidad V2.14 inequívoca, P-alta)."""
    import json
    from pathlib import Path

    from bolsa_api.provenance import build_provenance

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    pro = (response.json().get("provenance") or {})

    # package proviene del package.json raíz (single source), no de una constante.
    pkg = json.loads(
        (Path(__file__).resolve().parents[3] / "package.json").read_text(encoding="utf-8")
    )
    assert pro.get("package") == pkg.get("version")

    # Paquete del SDK debe coincidir con la fuente real leída internamente (no drift).
    assert pro.get("package") == build_provenance().package

    # schema deseado = cabecera Alembic (emisora/única) — hoy 023_ohlcv_bars_unique_reconcile.
    assert isinstance(pro.get("schema_revision"), str) and pro["schema_revision"].startswith("023")
    assert pro["schema_revision"] == build_provenance().schema_revision

    # Los campos no estrictamente derivables se reportan como clave (nunca se inventan).
    for key in ("git_sha", "schema_revision"):
        assert key in pro


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
