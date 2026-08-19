"""F-SEG-3 — CORS mínimo privilegio.

Verifica que el CORSMiddleware expone métodos y cabeceras explícitos (nunca `*`)
y que un origen no permitido no recibe los encabezados CORS correspondientes.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient, Headers

from bolsa_api.main import _CORS_ALLOW_HEADERS, _CORS_ALLOW_METHODS, create_app

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "http://evil.example.com"


@pytest.fixture
def app():
    # create_app() construye la app; el test de CORS sólo toca preflight/headers,
    # no el lifespan (no requiere BD). Se usa un transport ASGI sin levantar `app`.
    return create_app()


async def _preflight(
    app: object,
    *,
    origin: str,
    request_method: str = "POST",
    request_headers: str = "content-type,authorization",
) -> dict[str, str]:
    headers = Headers(
        {
            "Origin": origin,
            "Access-Control-Request-Method": request_method,
            "Access-Control-Request-Headers": request_headers,
        }
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request("OPTIONS", "/api/accounts", headers=headers)
    return dict(response.headers)


def test_cors_allow_methods_are_explicit_not_star() -> None:
    assert "*" not in _CORS_ALLOW_METHODS
    assert set(_CORS_ALLOW_METHODS) >= {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}


def test_cors_allow_headers_are_explicit_not_star() -> None:
    assert "*" not in _CORS_ALLOW_HEADERS
    assert set(_CORS_ALLOW_HEADERS) >= {
        "Content-Type",
        "Authorization",
        "X-Account-Id",
    }


@pytest.mark.asyncio
async def test_cors_credentialed_preflight_from_allowed_origin_has_explicit_methods_and_headers(
    app,
) -> None:
    headers = await _preflight(app, origin=ALLOWED_ORIGIN)
    # Origen permitido (credentialed) debe devolver el origen eco, no `*`.
    assert headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert headers.get("access-control-allow-credentials") == "true"
    allow_methods = headers.get("access-control-allow-methods", "")
    allow_headers = headers.get("access-control-allow-headers", "")
    # No puede haber wildcard en métodos ni cabeceras.
    assert "*" not in allow_methods
    assert "*" not in allow_headers
    # El FE (openapi-fetch/lib/api.ts) usa estos métodos y cabeceras.
    assert {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} <= set(
        m.strip() for m in allow_methods.split(",") if m.strip()
    )
    assert {
        header.strip().lower() for header in allow_headers.split(",") if header.strip()
    } >= {"content-type", "authorization", "x-account-id"}


@pytest.mark.asyncio
async def test_cors_preflight_from_disallowed_origin_omits_allow_origin(app) -> None:
    # Preflight OPTIONS es gestionado íntegramente por CORSMiddleware (no llega a la
    # ruta /router), por lo que no requiere el lifespan ni la BD.
    transport = ASGITransport(app=app)
    hdrs = Headers(
        {
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request("OPTIONS", "/api/accounts", headers=hdrs)

    # Invariante de seguridad: el navegador bloquea cualquier respuesta sin
    # `access-control-allow-origin`. Un origen no permitido no debe recibirlo.
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None
    # Vary: Origin fuerza al navegador a revalidar CORS por request.
    assert "origin" in (response.headers.get("vary") or "").lower()
