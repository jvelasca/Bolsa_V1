"""Fija la AUTH de las rutas de control de riesgo (auditoria G5, P3).

El auditor de ``docs/engineering/auditoria-aislamiento-ejecucion-xtb-2026-10-14.md``
declaró NO haber verificado la auth de estas rutas. Este fichero lo convierte en una
propiedad FALSABLE: con ``APP_PASSWORD`` puesto, las rutas de control de riesgo exigen
JWT (401 sin credencial) porque NINGUNA vive en ``PUBLIC_PREFIXES``.

Hermético/offline a propósito (sin PG ni red):

* ``REDIS_URL=""`` ⇒ el runtime best-effort de kill-switch / broker-venue queda no-op.
* El middleware (``AuthMiddleware._principal_from_jwt``) es lo único que tocaría la BD;
  su única lectura (``SqlAlchemyUserRepository.get_by_id``) se sustituye por un doble.

No se cambia el middleware ni se añade auth: solo se verifica y se fija.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.middleware.auth as auth_middleware
from bolsa_api.auth.jwt import encode_access_token
from bolsa_api.main import create_app
from bolsa_api.middleware.auth import PUBLIC_PREFIXES
from bolsa_infrastructure.config import get_settings

#: Rutas de control de riesgo bajo ``/api`` (router ``prefix="/risk"`` + global ``/api``).
_CONTROL_PATHS = (
    "/api/risk/kill-switch",
    "/api/risk/broker-venue",
    "/api/risk/kill-switch/durable-release",
)

#: ``session_version`` del usuario doble; debe casar con el ``sv`` del JWT emitido.
_SESSION_VERSION = 1


class _FakeUser:
    """Usuario activo mínimo: el middleware solo lee ``disabled_at`` y ``session_version``."""

    disabled_at: None = None

    def __init__(self, session_version: int) -> None:
        self.session_version = session_version


class _FakeUserRepository:
    """Doble de ``SqlAlchemyUserRepository``: devuelve siempre un usuario activo."""

    def __init__(self, _session: object) -> None:
        self._session = _session

    async def get_by_id(self, _user_id: str) -> _FakeUser:
        return _FakeUser(session_version=_SESSION_VERSION)


class _FakeSession:
    """Context manager mínimo que satisface ``async with factory() as session``."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_exc: object) -> bool:
        return False


def _fake_session_factory() -> _FakeSession:
    return _FakeSession()


def _arm_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Activa auth (APP_PASSWORD) en entorno test y sin Redis (hermético)."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("JWT_SIGNING_KEY", "jwt-test-key")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()


def test_risk_control_paths_are_not_public() -> None:
    """Guarda barata y explícita: ninguna ruta de control está en ``PUBLIC_PREFIXES``."""
    assert not any(path.startswith("/api/risk") for path in PUBLIC_PREFIXES), (
        f"PUBLIC_PREFIXES no debe contener /api/risk: {PUBLIC_PREFIXES}"
    )
    for path in _CONTROL_PATHS:
        assert not any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES), (
            f"{path} NO debe ser público: PUBLIC_PREFIXES={PUBLIC_PREFIXES}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _CONTROL_PATHS)
async def test_post_control_requires_jwt_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """Sin token, con auth ON ⇒ 401 (el middleware corta antes de la ruta)."""
    _arm_auth(monkeypatch)
    app = create_app()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path, json={})
        assert response.status_code == 401, response.text
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/risk/kill-switch", {"enabled": False}),
        ("/api/risk/broker-venue", {"venue": "paper"}),
    ],
)
async def test_post_control_accepts_valid_jwt(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, object],
) -> None:
    """Con JWT válido (Bearer) ⇒ NO 401 (el middleware deja pasar al handler)."""
    _arm_auth(monkeypatch)
    monkeypatch.setattr(auth_middleware, "SqlAlchemyUserRepository", _FakeUserRepository)
    app = create_app()
    app.state.session_factory = _fake_session_factory
    try:
        token = encode_access_token(
            get_settings(), sub="app", sv=_SESSION_VERSION, role="admin"
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                path,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code != 401, response.text
        assert response.status_code == 200, response.text
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/risk/kill-switch", {"enabled": False}),
        ("/api/risk/broker-venue", {"venue": "paper"}),
    ],
)
async def test_post_control_open_when_app_password_empty(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, object],
) -> None:
    """Dev: sin ``APP_PASSWORD`` la auth está OFF (por diseño; prod fail-closed en config).

    ``Settings`` exige ``APP_PASSWORD`` cuando ``ENVIRONMENT`` es productivo
    (``config.py:243-248``), así que "abierto en dev" no es un agujero: es un modo
    declarado. Se fija aquí para que un cambio silencioso lo rompa.
    """
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("APP_PASSWORD", "")
    monkeypatch.setenv("APP_AUTH_SECRET", "")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    app = create_app()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path, json=payload)
        assert response.status_code != 401, response.text
    finally:
        get_settings.cache_clear()
