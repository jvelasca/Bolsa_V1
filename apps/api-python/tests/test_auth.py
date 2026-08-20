import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.auth import session as session_module
from bolsa_api.auth.session import (
    SESSION_COOKIE_NAME,
    cookie_secure,
    create_session_cookie_value,
    verify_session_cookie,
)
from bolsa_api.main import create_app, lifespan
from bolsa_infrastructure.config import get_settings


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
    assert response.json()["data"]["authEnabled"] is False
    assert "token" not in response.json()["data"]


@pytest.mark.asyncio
async def test_login_sets_session_cookie_and_omits_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "s3cret"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["authEnabled"] is True
    assert "token" not in payload

    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_login_wrong_password_rejects(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "wrong"})

    assert response.status_code == 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_protected_route_requires_auth_and_accepts_cookie(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Sin credenciales -> 401.
            anon = await client.get("/api/accounts")
            assert anon.status_code == 401

            # Con cookie válida -> el middleware de auth deja pasar (distinto de 401).
            client.cookies.set(SESSION_COOKIE_NAME, create_session_cookie_value(get_settings()))
            authed = await client.get("/api/accounts")
            assert authed.status_code != 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_status_reports_authenticated_from_cookie(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Sin cookie -> authEnabled true pero authenticated false.
            anon = await client.get("/api/auth/status")
            assert anon.status_code == 200
            assert anon.json()["data"]["authEnabled"] is True
            assert anon.json()["data"]["authenticated"] is False

            # Con cookie válida -> authenticated true.
            client.cookies.set(SESSION_COOKIE_NAME, create_session_cookie_value(get_settings()))
            authed = await client.get("/api/auth/status")
            assert authed.status_code == 200
            assert authed.json()["data"]["authenticated"] is True

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_expired_session_cookie_rejected(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        # Crear la cookie con un epoch congelado para fijar su deadline.
        fixed_epoch = 1_700_000_000.0
        monkeypatch.setattr(session_module.time, "time", lambda: fixed_epoch)
        expired_cookie = create_session_cookie_value(get_settings())

        # Avanzar el reloj mucho más allá del TTL para forzar el deadline ya pasado.
        monkeypatch.setattr(
            session_module.time, "time", lambda: fixed_epoch + 100_000 + 3600
        )

        assert verify_session_cookie(get_settings(), expired_cookie) is False

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, expired_cookie)
            response = await client.get("/api/accounts")
            assert response.status_code == 401

    get_settings.cache_clear()


def test_session_epoch_portability_and_expiry(monkeypatch) -> None:
    """La sesión usa Unix epoch UTC: portable y expirable sin reloj monotónico."""
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()
    settings = get_settings()

    fixed_epoch = 1_700_000_000.0

    # Reloj congelado para generar la cookie con un deadline determinista.
    monkeypatch.setattr(session_module.time, "time", lambda: fixed_epoch)
    cookie = create_session_cookie_value(settings)

    # Dentro del TTL (mismo epoch) -> válida.
    assert verify_session_cookie(settings, cookie) is True

    # Avanzar el reloj más allá del deadline -> expirada.
    monkeypatch.setattr(session_module.time, "time", lambda: fixed_epoch + 100_000)
    assert verify_session_cookie(settings, cookie) is False

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_logout_clears_cookie(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    # El logout debe expirar la cookie (Max-Age=0 / borrado).
    assert "set-cookie" in response.headers
    set_cookie = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_logout_works_when_auth_disabled() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/logout")

    assert response.status_code == 200


def test_cookie_secure_only_in_production() -> None:
    class FakeSettings:
        def __init__(self, environment: str) -> None:
            self.environment = environment

    assert cookie_secure(FakeSettings("development")) is False
    assert cookie_secure(FakeSettings("prod")) is True
    assert cookie_secure(FakeSettings("production")) is True
