import hashlib
import time

import jwt as pyjwt
import pytest
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import UserRow
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from bolsa_api.auth.jwt import decode_access_token, encode_access_token
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.auth.roles import require_role
from bolsa_api.auth.session import SESSION_COOKIE_NAME, cookie_secure
from bolsa_api.main import create_app, lifespan


async def _jwt_for_app_user(app) -> str:
    settings = get_settings()
    factory = app.state.session_factory
    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = await repo.get_by_id("app")
        assert user is not None
        return encode_access_token(
            settings, sub=user.id, sv=user.session_version, role=user.role
        )


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

    cookie = response.cookies.get(SESSION_COOKIE_NAME)
    assert cookie is not None
    claims = decode_access_token(get_settings(), cookie)
    assert claims is not None
    assert claims["sub"] == "app"
    assert not cookie.split(".")[0].isdigit()

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

            # Cookie JWT válida -> el middleware de auth deja pasar (distinto de 401).
            client.cookies.set(SESSION_COOKIE_NAME, await _jwt_for_app_user(app))
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

            # Cookie HMAC legacy (exp.token.sig) -> no autenticado.
            client.cookies.set(SESSION_COOKIE_NAME, "1700000000.deadbeef.deadbeef")
            hmac_status = await client.get("/api/auth/status")
            assert hmac_status.status_code == 200
            assert hmac_status.json()["data"]["authenticated"] is False

            # Cookie JWT válida -> authenticated true.
            client.cookies.set(SESSION_COOKIE_NAME, await _jwt_for_app_user(app))
            authed = await client.get("/api/auth/status")
            assert authed.status_code == 200
            assert authed.json()["data"]["authenticated"] is True

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_expired_jwt_cookie_rejected(monkeypatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()
    settings = get_settings()

    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        async with factory() as session:
            repo = SqlAlchemyUserRepository(session)
            user = await repo.get_by_id("app")
            assert user is not None
            sv = user.session_version

        now = int(time.time())
        expired_cookie = pyjwt.encode(
            {"sub": "app", "sv": sv, "iat": now - 100, "exp": now - 10, "role": "admin"},
            settings.jwt_signing_key_resolved(),
            algorithm="HS256",
        )
        assert decode_access_token(settings, expired_cookie) is None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, expired_cookie)
            response = await client.get("/api/accounts")
            assert response.status_code == 401

    get_settings.cache_clear()


def test_jwt_epoch_portability_and_expiry(monkeypatch) -> None:
    """El JWT usa Unix epoch UTC en ``exp``: portable y expirable sin reloj monotónico."""
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()
    settings = get_settings()

    now = int(time.time())
    valid = pyjwt.encode(
        {"sub": "app", "sv": 1, "iat": now, "exp": now + 3600, "role": "admin"},
        settings.jwt_signing_key_resolved(),
        algorithm="HS256",
    )
    expired = pyjwt.encode(
        {"sub": "app", "sv": 1, "iat": now - 100, "exp": now - 10, "role": "admin"},
        settings.jwt_signing_key_resolved(),
        algorithm="HS256",
    )

    assert decode_access_token(settings, valid) is not None
    assert decode_access_token(settings, expired) is None

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


@pytest.mark.asyncio
async def test_jwt_login_with_bootstrap_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "s3cret"})

    assert response.status_code == 200
    cookie = response.cookies.get(SESSION_COOKIE_NAME)
    assert cookie is not None
    claims = decode_access_token(get_settings(), cookie)
    assert claims is not None
    assert claims["sub"] == "app"
    assert isinstance(claims.get("sv"), int)
    assert "exp" in claims
    assert "iat" in claims

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_jwt_login_wrong_password_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "wrong"})

    assert response.status_code == 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_middleware_accepts_jwt_bearer_and_sets_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()
    settings = get_settings()

    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        async with factory() as session:
            repo = SqlAlchemyUserRepository(session)
            user = await repo.get_by_id("app")
            assert user is not None
            sv = user.session_version

        token = encode_access_token(settings, sub="app", sv=sv, role="admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/accounts",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code != 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_login_without_user_row_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        async with factory() as session:
            await session.execute(delete(UserRow))
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/login", json={"password": "s3cret"})

    assert response.status_code == 401
    assert SESSION_COOKIE_NAME not in (response.headers.get("set-cookie") or "")

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_legacy_hmac_cookie_does_not_authenticate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE_NAME, "1700000000.deadbeef.deadbeef")
            response = await client.get("/api/accounts")
            assert response.status_code == 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_legacy_sha256_bearer_does_not_authenticate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()
    settings = get_settings()
    legacy = hashlib.sha256(
        f"bolsa:{settings.app_password}:{settings.app_auth_secret}".encode()
    ).hexdigest()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/accounts",
                headers={"Authorization": f"Bearer {legacy}"},
            )
            assert response.status_code == 401

    get_settings.cache_clear()


def test_get_request_principal_reads_request_state() -> None:
    class FakeRequest:
        state = type("State", (), {"principal": "jwt-user-42"})()

    assert get_request_principal(FakeRequest()) == "jwt-user-42"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_refresh_reissues_jwt_with_new_exp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"password": "s3cret"})
            assert login.status_code == 200
            old_cookie = login.cookies.get(SESSION_COOKIE_NAME)
            assert old_cookie is not None
            old_claims = decode_access_token(get_settings(), old_cookie)
            assert old_claims is not None

            client.cookies.set(SESSION_COOKIE_NAME, old_cookie)
            refreshed = await client.post("/api/auth/refresh")
            assert refreshed.status_code == 200
            new_cookie = refreshed.cookies.get(SESSION_COOKIE_NAME)
            assert new_cookie is not None
            new_claims = decode_access_token(get_settings(), new_cookie)
            assert new_claims is not None
            assert new_claims["sub"] == old_claims["sub"]
            assert new_claims["sv"] == old_claims["sv"]
            assert new_claims["exp"] >= old_claims["exp"]

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_logout_bumps_session_version_and_invalidates_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()

    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"password": "s3cret"})
            token = login.cookies.get(SESSION_COOKIE_NAME)
            assert token is not None

            client.cookies.set(SESSION_COOKIE_NAME, token)
            authed = await client.get("/api/accounts")
            assert authed.status_code != 401

            client.cookies.set(SESSION_COOKIE_NAME, token)
            logout = await client.post("/api/auth/logout")
            assert logout.status_code == 200

            client.cookies.set(SESSION_COOKIE_NAME, token)
            rejected = await client.get("/api/accounts")
            assert rejected.status_code == 401

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_stale_session_version_jwt_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    get_settings.cache_clear()
    settings = get_settings()

    app = create_app()
    async with lifespan(app):
        factory = app.state.session_factory
        async with factory() as session:
            repo = SqlAlchemyUserRepository(session)
            user = await repo.get_by_id("app")
            assert user is not None
            stale_sv = user.session_version + 1

        stale_token = encode_access_token(settings, sub="app", sv=stale_sv, role="admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/accounts",
                headers={"Authorization": f"Bearer {stale_token}"},
            )
            assert response.status_code == 401

    get_settings.cache_clear()


def test_require_role_allows_matching_role() -> None:
    class FakeRequest:
        state = type("State", (), {"auth_role": "admin"})()

    require_role(FakeRequest(), "admin")  # type: ignore[arg-type]


def test_require_role_rejects_mismatch() -> None:
    class FakeRequest:
        state = type("State", (), {"auth_role": "operator"})()

    with pytest.raises(HTTPException) as exc_info:
        require_role(FakeRequest(), "admin")  # type: ignore[arg-type]
    assert exc_info.value.status_code == 403
