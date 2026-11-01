"""N-1 — «Deshabilitar Yahoo» detiene TODO el tráfico, no solo el histórico.

El interruptor de Configuración se evaluaba únicamente vía
``resolve_capability(CAPABILITY_OHLCV)``. Fundamentales, FX, índices, búsqueda, macro y
noticias seguían llamando al cliente Yahoo aunque la UI mostrase «deshabilitado»: estado
declarado ≠ comportamiento.

La corrección gatea el CLIENTE (``_ensure_traffic_allowed``), porque es el único punto por
el que pasan todas las rutas —presentes y futuras— y porque un proveedor apagado debe
comportarse igual que uno caído, que es lo que cada consumidor ya sabe degradar.
"""

from __future__ import annotations

from typing import Any

import pytest

import bolsa_market.yahoo_client as yahoo_client
from bolsa_application.market_providers import (
    MarketProviderConfigResolver,
    TestProviderConnection,
    invalidate_provider_config_cache,
)
from bolsa_domain.entities.market_provider import PROVIDER_XTB, PROVIDER_YAHOO
from bolsa_infrastructure.database.repositories.market_provider_settings_repository import (
    MarketProviderSettingsRecord,
)
from bolsa_market.yahoo_client import (
    YahooFinanceClient,
    YahooProviderDisabledError,
    set_yahoo_traffic_enabled,
    yahoo_traffic_enabled,
)

#: Rutas públicas del cliente que hoy existen (el gate tiene que cubrirlas TODAS: es
#: precisamente el fallo que se está cerrando que una ruta se olvide).
_FETCH_PATHS: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...] = (
    ("fetch_spot_price", ("^IBEX",), {}),
    ("fetch_chart_payload", ("^IBEX",), {"period1": 0, "period2": 2_000_000_000, "interval": "1d"}),
    ("search_quotes", ("inditex",), {}),
    ("fetch_news", ("inditex",), {}),
    ("fetch_isin", ("ITX.MC",), {}),
    ("fetch_quote_summary", ("ITX.MC",), {}),
    ("fetch_fundamentals_timeseries", ("ITX.MC",), {"types": ["annualTotalRevenue"]}),
    ("fetch_dividend_history", ("ITX.MC",), {}),
)


@pytest.fixture(autouse=True)
def _reset_gate() -> Any:
    """Cada test deja el semáforo como lo encontró (es estado de PROCESO)."""
    previous = yahoo_traffic_enabled()
    yield
    set_yahoo_traffic_enabled(previous)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Cualquier intento de crear un cliente HTTP se registra y falla."""
    attempts: list[str] = []

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        attempts.append("httpx.AsyncClient")
        raise AssertionError("con Yahoo deshabilitado no se puede tocar la red")

    monkeypatch.setattr(yahoo_client.httpx, "AsyncClient", _forbidden)
    return attempts


def _record(provider_id: str, *, enabled: bool) -> MarketProviderSettingsRecord:
    return MarketProviderSettingsRecord(
        id=provider_id,
        enabled=enabled,
        priority=10,
        min_interval_seconds=0,
        base_url=None,
        options={},
        last_check_at=None,
        last_check_ok=None,
        last_check_message=None,
        updated_at="2026-11-01T09:00:00+00:00",
    )


class _Repo:
    def __init__(self, records: list[MarketProviderSettingsRecord]) -> None:
        self._records = {record.id: record for record in records}

    async def list_all(self) -> list[MarketProviderSettingsRecord]:
        return list(self._records.values())

    async def get(self, provider_id: str) -> MarketProviderSettingsRecord | None:
        return self._records.get(provider_id)

    async def record_check(
        self, provider_id: str, *, ok: bool, message: str, at: Any = None
    ) -> MarketProviderSettingsRecord | None:
        record = self._records.get(provider_id)
        if record is None:
            return None
        updated = MarketProviderSettingsRecord(
            id=record.id,
            enabled=record.enabled,
            priority=record.priority,
            min_interval_seconds=record.min_interval_seconds,
            base_url=record.base_url,
            options=record.options,
            last_check_at="2026-11-01T09:05:00+00:00",
            last_check_ok=ok,
            last_check_message=message,
            updated_at="2026-11-01T09:05:00+00:00",
        )
        self._records[provider_id] = updated
        return updated


def _resolver(enabled: bool) -> MarketProviderConfigResolver:
    return MarketProviderConfigResolver(
        _Repo([_record(PROVIDER_YAHOO, enabled=enabled), _record(PROVIDER_XTB, enabled=True)]),  # type: ignore[arg-type]
        cache_ttl_seconds=0.0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    _FETCH_PATHS,
    ids=[case[0] for case in _FETCH_PATHS],
)
async def test_every_yahoo_route_is_blocked_when_the_provider_is_disabled(
    method: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    no_network: list[str],
) -> None:
    """Ninguna ruta sale a la red con el proveedor deshabilitado."""
    set_yahoo_traffic_enabled(False, reason="provider_disabled:yahoo")
    client = YahooFinanceClient(min_interval_sec=0.0)

    with pytest.raises(YahooProviderDisabledError) as excinfo:
        await getattr(client, method)(*args, **kwargs)

    assert "deshabilitado" in str(excinfo.value).lower()
    assert "provider_disabled:yahoo" in str(excinfo.value)
    assert no_network == [], "no se debe construir ni un cliente HTTP"
    assert client._client is None  # noqa: SLF001 — ni siquiera se abrió el transporte


@pytest.mark.asyncio
async def test_the_gate_follows_the_persisted_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El resolver es el único lector: apagar en Configuración apaga el cliente."""
    invalidate_provider_config_cache()
    set_yahoo_traffic_enabled(True)

    await _resolver(enabled=False).list_configs(refresh=True)
    assert yahoo_traffic_enabled() is False

    await _resolver(enabled=True).list_configs(refresh=True)
    assert yahoo_traffic_enabled() is True


@pytest.mark.asyncio
async def test_a_disabled_provider_does_not_measure_and_does_not_send_traffic(
    no_network: list[str],
) -> None:
    """La sonda respeta el interruptor: «deshabilitado» no es «sin respuesta»."""
    set_yahoo_traffic_enabled(False, reason="provider_disabled:yahoo")
    repo = _Repo([_record(PROVIDER_YAHOO, enabled=False)])

    async def _probe() -> tuple[float, str]:
        raise AssertionError("no se debe sondear un proveedor deshabilitado")

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, yahoo_probe=_probe, on_change=lambda: None
    ).execute(PROVIDER_YAHOO)

    assert result.ok is False
    assert "deshabilitado" in result.message.lower()
    assert no_network == []


@pytest.mark.asyncio
async def test_the_error_is_declared_as_configuration_not_as_an_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El mensaje normalizado no finge una caída: nombra la configuración."""
    set_yahoo_traffic_enabled(False, reason="provider_disabled:yahoo")
    client = YahooFinanceClient(min_interval_sec=0.0)

    with pytest.raises(YahooProviderDisabledError) as excinfo:
        await client.fetch_spot_price("^IBEX")

    assert yahoo_client.normalize_yahoo_error(excinfo.value) == str(excinfo.value)
