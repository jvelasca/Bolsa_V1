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

    # schema = cabecera Alembic real (single source), no un prefijo fijo a una
    # revisión concreta: avanzar la head (023→024…) no debe romper este test.
    assert isinstance(pro.get("schema_revision"), str) and len(pro["schema_revision"]) > 0
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


@pytest.mark.asyncio
async def test_health_live_returns_200_no_db(app) -> None:
    """/api/health/live (V2.15) — liveness sin tocar BD: proceso vivo + provenance."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "live"
    assert body["service"] == "bolsa-api-python"
    assert "timestamp" in body
    assert "provenance" in body


@pytest.mark.asyncio
async def test_health_ready_ok_when_db_up(app) -> None:
    """/api/health/ready (V2.15) — 200/ready si PostgreSQL responde (dependencia requerida)."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/ready")

    # En esta suite se ejecuta con la BD local real arriba (test_health = RBAC real-PG).
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["required"]["status"] == "ok"
    assert "optional" in body


@pytest.mark.asyncio
async def test_health_ready_503_when_db_down(app, monkeypatch) -> None:
    """/api/health/ready — si PostgreSQL cae, readiness=503 (no ready) sin detalle crudo."""
    import bolsa_api.api.v1.routes.health as health_mod

    async def fake_check(_engine) -> tuple[bool, str]:
        return False, "PostgreSQL inaccesible"

    monkeypatch.setattr(health_mod, "check_database", fake_check)
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["required"]["message"] == "PostgreSQL inaccesible"


@pytest.mark.asyncio
async def test_health_ready_200_when_db_up_and_schema_at_head(app) -> None:
    """/api/health/ready — 200/ready sólo si PostgreSQL Y esquema coinciden con el head."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/ready")

    # En esta suite (RBAC real-PG) `bolsa_v1` está migrada a head → 200/ready.
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["required"]["status"] == "ok"
    assert body["schema_status"]["status"] == "ok"
    assert "esquema en head" in body["schema_status"]["message"]


@pytest.mark.asyncio
async def test_health_ready_503_when_schema_mismatch(app, monkeypatch) -> None:
    """/api/health/ready — BD responde pero schema != head esperado ⇒ 503 not_ready (V2.15-03)."""
    import bolsa_api.api.v1.routes.health as health_mod

    # Simula una BD en una revisión anterior a la que el binario actual espera.
    async def fake_schema(_engine):
        return "022_live_orders_exec", "ok"

    monkeypatch.setattr(health_mod, "read_db_schema_current", fake_schema)
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["required"]["status"] == "ok"  # PostgreSQL sigue listo
    assert body["schema_status"]["status"] == "error"
    assert "esperado" in body["schema_status"]["message"]


@pytest.mark.asyncio
async def test_health_ready_503_when_db_not_migrated(app, monkeypatch) -> None:
    """/api/health/ready — BD arriba sin esquema migrado ⇒ 503 not_ready (nunca "ready" ante DB vieja)."""
    import bolsa_api.api.v1.routes.health as health_mod

    async def fake_schema(_engine):
        return None, "unmigrated"

    monkeypatch.setattr(health_mod, "read_db_schema_current", fake_schema)
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["schema_status"]["status"] == "error"

