"""API de proveedores y validación de ``scope`` — sin PostgreSQL real.

La ruta se monta sola (sin ``lifespan``) y se sustituyen los casos de uso por dobles:
lo que se prueba aquí es el CONTRATO HTTP (códigos, DTO y cableado de la validación),
no la persistencia — eso vive en ``test_market_providers_pg.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes import market as market_route
from bolsa_api.api.v1.routes import sync as sync_route
from bolsa_domain.value_objects.market import MarketProviderStatus

pytestmark = pytest.mark.asyncio


def _status(provider_id: str, **overrides: Any) -> MarketProviderStatus:
    base: dict[str, Any] = {
        "id": provider_id,
        "label": "Yahoo Finance" if provider_id == "yahoo" else "XTB Bridge",
        "enabled": True,
        "healthy": False,
        "message": "Sin verificar (usa «Probar conexión»)",
        "priority": 10 if provider_id == "yahoo" else 20,
        "min_interval_seconds": 2 if provider_id == "yahoo" else 0,
        "base_url": None,
        "capabilities": ("ohlcv",) if provider_id == "yahoo" else ("live_quote",),
        "verified": False,
    }
    base.update(overrides)
    return MarketProviderStatus(**base)


class _StatusUseCase:
    def __init__(self, statuses: list[MarketProviderStatus]) -> None:
        self._statuses = statuses

    async def execute(self) -> list[MarketProviderStatus]:
        return self._statuses


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(market_route.router, prefix="/api")
    application.include_router(sync_route.router, prefix="/api")

    async def _session() -> Any:
        yield None

    application.dependency_overrides[get_db_session] = _session
    return application


@pytest.fixture
def client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _status_stub(monkeypatch: pytest.MonkeyPatch, statuses: list[MarketProviderStatus]) -> None:
    async def _status_use_case(
        _session: Any, *, refresh: bool = False, live: bool = True
    ) -> Any:
        return _StatusUseCase(statuses)

    monkeypatch.setattr(market_route, "get_market_status_use_case", _status_use_case)


def _policy_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    interval_seconds: int = 60,
) -> None:
    from bolsa_domain.entities.market_provider import ProviderCheckPolicy

    class _Policy:
        async def execute(self) -> Any:
            return ProviderCheckPolicy(enabled=enabled, interval_seconds=interval_seconds)

    monkeypatch.setattr(
        market_route, "get_provider_check_policy_use_case", lambda _s: _Policy()
    )


async def test_get_providers_publishes_configuration(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _status_stub(monkeypatch, [_status("yahoo"), _status("xtb", verified=True)])

    response = await client.get("/api/market/providers")

    assert response.status_code == 200
    yahoo, xtb = response.json()["data"]
    assert yahoo["id"] == "yahoo"
    assert yahoo["minIntervalSeconds"] == 2
    assert yahoo["verified"] is False
    assert yahoo["capabilities"] == ["ohlcv"]
    assert xtb["priority"] == 20


async def test_patch_unknown_provider_is_404(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    from bolsa_application.market_providers import UnknownProviderError

    class _Update:
        async def execute(self, provider_id: str, **_kwargs: Any) -> Any:
            raise UnknownProviderError(provider_id)

    monkeypatch.setattr(market_route, "get_update_market_provider_use_case", lambda _s: _Update())
    response = await client.patch("/api/market/providers/nasdaq", json={"enabled": False})
    assert response.status_code == 404
    assert "nasdaq" in response.json()["detail"]


async def test_patch_invalid_url_is_422(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    from bolsa_application.market_providers import ProviderConfigError

    class _Update:
        async def execute(self, _provider_id: str, **_kwargs: Any) -> Any:
            raise ProviderConfigError("baseUrl inválida")

    monkeypatch.setattr(market_route, "get_update_market_provider_use_case", lambda _s: _Update())
    response = await client.patch("/api/market/providers/xtb", json={"baseUrl": "ftp://bridge"})
    assert response.status_code == 422
    assert "baseUrl" in response.json()["detail"]


async def test_patch_out_of_range_priority_is_422_by_dto(client: AsyncClient) -> None:
    response = await client.patch("/api/market/providers/yahoo", json={"priority": 1000})
    assert response.status_code == 422


async def test_patch_forwards_only_declared_fields(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    captured: dict[str, Any] = {}

    class _Update:
        async def execute(self, provider_id: str, **kwargs: Any) -> Any:
            captured["provider_id"] = provider_id
            captured.update(kwargs)
            return _status("xtb", enabled=False)

    monkeypatch.setattr(market_route, "get_update_market_provider_use_case", lambda _s: _Update())
    _status_stub(monkeypatch, [_status("yahoo"), _status("xtb", enabled=False)])

    response = await client.patch("/api/market/providers/xtb", json={"baseUrl": None})

    assert response.status_code == 200
    assert captured["provider_id"] == "xtb"
    assert captured["base_url_provided"] is True
    assert captured["base_url"] is None
    assert captured["enabled"] is None  # no declarado ⇒ no se toca
    assert captured["priority"] is None


async def test_provider_test_endpoint_returns_result(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    from bolsa_application.market_providers import ProviderProbeResult

    class _Test:
        async def execute(self, provider_id: str) -> Any:
            assert provider_id == "xtb"
            return ProviderProbeResult(ok=True, message="Bridge mock listo")

    monkeypatch.setattr(market_route, "get_test_provider_connection_use_case", lambda _s: _Test())
    response = await client.post("/api/market/providers/xtb/test")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["providerId"] == "xtb"
    assert data["ok"] is True
    assert data["message"] == "Bridge mock listo"
    assert data["checkedAt"]


async def test_sync_scope_is_a_closed_enum(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """``all`` (alias histórico de la UI) ya no se acepta: 422, no traducción opaca."""
    from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
        SyncSettingsRecord,
    )

    record = SyncSettingsRecord(
        auto_sync_enabled=True,
        scan_interval_minutes=30,
        min_delay_seconds=5,
        post_market_only=False,
        max_retries=3,
        retry_backoff_minutes=30,
        scope="stale",
        provider_check_enabled=True,
        provider_check_interval_seconds=60,
        updated_at="2026-10-29T09:00:00+00:00",
    )

    class _UpdateSettings:
        async def execute(self, **_kwargs: Any) -> Any:
            return record

    monkeypatch.setattr(
        sync_route, "get_update_sync_settings_use_case", lambda _s: _UpdateSettings()
    )

    rejected = await client.patch("/api/sync/settings", json={"scope": "all"})
    assert rejected.status_code == 422

    accepted = await client.patch("/api/sync/settings", json={"scope": "stale"})
    assert accepted.status_code == 200
    assert accepted.json()["data"]["scope"] == "stale"


async def test_sync_settings_publishes_and_updates_provider_check_policy(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """La política de servidores viaja en sync_settings y el PATCH la reenvía."""
    from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
        SyncSettingsRecord,
    )

    captured: dict[str, Any] = {}

    def _record(**overrides: Any) -> SyncSettingsRecord:
        base: dict[str, Any] = {
            "auto_sync_enabled": True,
            "scan_interval_minutes": 30,
            "min_delay_seconds": 5,
            "post_market_only": False,
            "max_retries": 3,
            "retry_backoff_minutes": 30,
            "scope": "lists",
            "provider_check_enabled": True,
            "provider_check_interval_seconds": 60,
            "updated_at": "2026-10-29T09:00:00+00:00",
        }
        base.update(overrides)
        return SyncSettingsRecord(**base)

    class _UpdateSettings:
        async def execute(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return _record(**{k: v for k, v in kwargs.items() if v is not None})

    monkeypatch.setattr(
        sync_route, "get_update_sync_settings_use_case", lambda _s: _UpdateSettings()
    )

    response = await client.patch(
        "/api/sync/settings",
        json={"providerCheckEnabled": False, "providerCheckIntervalSeconds": 300},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["providerCheckEnabled"] is False
    assert data["providerCheckIntervalSeconds"] == 300
    assert captured["provider_check_enabled"] is False
    assert captured["provider_check_interval_seconds"] == 300


async def test_sync_settings_rejects_out_of_range_check_interval(
    client: AsyncClient,
) -> None:
    """Fuera del rango del dominio es 422, no un valor acotado en silencio."""
    too_fast = await client.patch(
        "/api/sync/settings", json={"providerCheckIntervalSeconds": 10}
    )
    assert too_fast.status_code == 422

    too_slow = await client.patch(
        "/api/sync/settings", json={"providerCheckIntervalSeconds": 4000}
    )
    assert too_slow.status_code == 422


async def test_enqueue_stale_response_declares_skipped_reason(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    from bolsa_application.sync_scheduler import EnqueueStaleResult

    class _Enqueue:
        async def execute(self) -> Any:
            return EnqueueStaleResult(
                scanned=0, enqueued=0, skipped_reason="provider_disabled:yahoo"
            )

    monkeypatch.setattr(sync_route, "get_enqueue_stale_use_case", lambda _s: _Enqueue())
    response = await client.post("/api/sync/queue/enqueue-stale")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "scanned": 0,
        "enqueued": 0,
        "skippedReason": "provider_disabled:yahoo",
    }


async def test_provider_health_publishes_aggregate_verdict(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """El icono de la barra recibe UN veredicto medido, no una suposición."""
    from datetime import UTC, datetime

    measured = datetime.now(UTC).isoformat()
    _status_stub(
        monkeypatch,
        [
            _status(
                "yahoo",
                healthy=True,
                verified=True,
                last_check_at=measured,
                last_check_ok=True,
            ),
            _status(
                "xtb",
                healthy=True,
                verified=True,
                last_check_at=measured,
                last_check_ok=True,
            ),
        ],
    )
    _policy_stub(monkeypatch)

    response = await client.get("/api/market/providers/health")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["ok"] is True
    assert data["measuredAt"] == measured
    assert data["probing"] is False
    # La política viaja con el veredicto: la UI no duplica la cadencia.
    assert data["autoCheckEnabled"] is True
    assert data["checkIntervalSeconds"] == 60
    assert data["nextCheckAt"]
    assert [provider["id"] for provider in data["providers"]] == ["yahoo", "xtb"]
    assert data["providers"][1]["verified"] is True


async def test_provider_health_is_degraded_when_an_enabled_provider_fails(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    _status_stub(
        monkeypatch,
        [
            _status("yahoo", verified=False),
            _status(
                "xtb",
                healthy=False,
                verified=True,
                message="Bridge no responde",
                last_check_ok=False,
            ),
        ],
    )
    _policy_stub(monkeypatch)

    response = await client.get("/api/market/providers/health")

    data = response.json()["data"]
    assert data["status"] == "degraded"
    assert data["ok"] is False
    xtb = next(provider for provider in data["providers"] if provider["id"] == "xtb")
    assert xtb["message"] == "Bridge no responde"


async def test_provider_health_is_stale_when_measurement_aged_past_policy(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """Con la automática ON, una medición vieja no se pinta verde: es `stale` (ámbar)."""
    _status_stub(
        monkeypatch,
        [
            _status(
                "yahoo",
                verified=True,
                healthy=True,
                last_check_at="2020-01-01T00:00:00+00:00",
                last_check_ok=True,
            )
        ],
    )
    _policy_stub(monkeypatch, interval_seconds=60)

    response = await client.get("/api/market/providers/health")

    data = response.json()["data"]
    assert data["status"] == "stale"
    assert data["ok"] is False


async def test_provider_health_with_auto_check_off_does_not_report_stale(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """OFF no es «bucle caído»: la última medición se publica sin `nextCheckAt`."""
    _status_stub(
        monkeypatch,
        [
            _status(
                "yahoo",
                verified=True,
                healthy=True,
                last_check_at="2020-01-01T00:00:00+00:00",
                last_check_ok=True,
            )
        ],
    )
    _policy_stub(monkeypatch, enabled=False)

    response = await client.get("/api/market/providers/health")

    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["autoCheckEnabled"] is False
    assert data["nextCheckAt"] is None


async def test_provider_health_triggers_grouped_probe_when_data_is_stale(
    monkeypatch: pytest.MonkeyPatch, app: FastAPI, client: AsyncClient
) -> None:
    """El endpoint pide refresco SIN bloquear y lo declara con `probing`."""
    calls = {"n": 0}

    class _Monitor:
        probing = False

        def ensure_fresh(self) -> bool:
            calls["n"] += 1
            return True

    app.state.provider_health = _Monitor()
    _status_stub(monkeypatch, [_status("yahoo", verified=True, healthy=True)])
    _policy_stub(monkeypatch)

    response = await client.get("/api/market/providers/health")

    assert calls["n"] == 1
    assert response.json()["data"]["probing"] is True


async def test_provider_health_check_now_forces_a_measured_sweep(
    monkeypatch: pytest.MonkeyPatch, app: FastAPI, client: AsyncClient
) -> None:
    """«Comprobar ahora» mide aunque la automática esté OFF (diagnóstico explícito)."""
    from datetime import UTC, datetime

    from bolsa_application.market_providers import ProviderProbeResult

    measured = datetime.now(UTC).isoformat()
    forced: list[bool] = []

    class _Monitor:
        probing = False

        async def probe_if_due(self, *, force: bool = False) -> Any:
            forced.append(force)
            return {"yahoo": ProviderProbeResult(ok=True, message="ok")}

    app.state.provider_health = _Monitor()
    _status_stub(
        monkeypatch,
        [
            _status(
                "yahoo",
                verified=True,
                healthy=True,
                last_check_at=measured,
                last_check_ok=True,
            )
        ],
    )
    _policy_stub(monkeypatch, enabled=False)

    response = await client.post("/api/market/providers/health/check")

    assert response.status_code == 200
    assert forced == [True]
    assert response.json()["data"]["status"] == "ok"


async def test_provider_health_check_without_monitor_is_503(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    """Sin comprobador no se finge una medición: 503 declarado."""
    _status_stub(monkeypatch, [_status("yahoo")])
    _policy_stub(monkeypatch)

    response = await client.post("/api/market/providers/health/check")

    assert response.status_code == 503
    assert "Comprobador" in response.json()["detail"]
