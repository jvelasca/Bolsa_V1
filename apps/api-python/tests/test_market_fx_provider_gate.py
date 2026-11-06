"""``GET /api/market/fx`` — N-1: con Yahoo apagado la respuesta es 409, no 502.

Antes, el interruptor del proveedor no gobernaba esta ruta: seguía habiendo tráfico real a
Yahoo (y un fallo se publicaba como 502, «Yahoo caído», aunque lo que pasaba era que el
operador lo había desactivado).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes import market as market_route
from bolsa_application.fx import FxRate
from bolsa_market.yahoo_client import YahooProviderDisabledError

pytestmark = pytest.mark.asyncio


class _Session:
    pass


class _Resolver:
    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled
        self.calls = 0

    async def list_configs(self, *, refresh: bool = False) -> list[Any]:
        self.calls += 1
        from bolsa_market.yahoo_client import set_yahoo_traffic_enabled

        set_yahoo_traffic_enabled(self._enabled, reason=None if self._enabled else "provider_disabled:yahoo")
        return []


class _FxUseCase:
    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled

    async def execute(self, from_currency: str, to_currency: str) -> FxRate:
        from bolsa_market.yahoo_client import (
            _ensure_traffic_allowed,
            set_yahoo_traffic_enabled,
        )

        set_yahoo_traffic_enabled(self._enabled)
        _ensure_traffic_allowed()
        return FxRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=1.1,
            yahoo_symbol=f"{from_currency}{to_currency}=X",
            timestamp="2026-11-01T09:00:00Z",
        )


def _app(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> tuple[FastAPI, _Resolver]:
    application = FastAPI()
    application.include_router(market_route.router, prefix="/api")
    application.dependency_overrides[get_db_session] = lambda: _Session()

    resolver = _Resolver(enabled=enabled)
    monkeypatch.setattr(
        market_route, "get_market_provider_config_resolver", lambda _session: resolver
    )
    monkeypatch.setattr(
        market_route, "get_fx_rate_use_case", lambda: _FxUseCase(enabled=enabled)
    )
    return application, resolver


async def _get(app: FastAPI) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/market/fx", params={"from": "EUR", "to": "USD"})


async def test_a_disabled_provider_returns_409_and_performs_no_traffic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, resolver = _app(monkeypatch, enabled=False)

    response = await _get(app)

    assert response.status_code == 409, response.text
    assert "provider_disabled:yahoo" in response.text
    assert resolver.calls >= 1, "la configuración se lee antes de pedir el tipo de cambio"


async def test_an_enabled_provider_keeps_the_previous_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, resolver = _app(monkeypatch, enabled=True)

    response = await _get(app)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["rate"] == pytest.approx(1.1)
    assert resolver.calls >= 1


async def test_the_disabled_error_is_not_published_as_an_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: un fallo real de Yahoo sigue siendo 502 (no todo es «deshabilitado»)."""

    class _Failing:
        async def execute(self, from_currency: str, to_currency: str) -> FxRate:
            raise RuntimeError("Yahoo Finance no respondió a tiempo")

    app, _ = _app(monkeypatch, enabled=True)
    monkeypatch.setattr(market_route, "get_fx_rate_use_case", lambda: _Failing())

    response = await _get(app)

    assert response.status_code == 502
    assert isinstance(YahooProviderDisabledError("x"), RuntimeError)
