"""Fallo cerrado de proveedor en sync/cola y ventana post-cierre.

Cubre ``SYN-3``, ``SYN-4``, ``SYN-6`` y ``SYN-9`` del documento
``docs/engineering/seguimiento-ui-proveedores-2026-10-29.md``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from bolsa_application.market_providers import ProviderResolution
from bolsa_application.sync_scheduler import (
    EnqueueStaleInstruments,
    ProcessNextSyncQueueItem,
    ProcessQueueResult,
    is_post_market_window,
)

MADRID = ZoneInfo("Europe/Madrid")


class _DisabledResolver:
    def __init__(self, reason: str = "provider_disabled:yahoo") -> None:
        self.reason = reason
        self.calls: list[str] = []

    async def resolve_capability(self, capability: str, **_kwargs: Any) -> ProviderResolution:
        self.calls.append(capability)
        return ProviderResolution(capability=capability, provider=None, reason=self.reason)


class _Untouchable:
    """Repositorio que falla si el caso de uso lo consulta: prueba el cortocircuito."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"no debería usarse {name} con el proveedor deshabilitado")


@pytest.mark.asyncio
async def test_enqueue_is_skipped_when_provider_is_disabled() -> None:
    resolver = _DisabledResolver()
    use_case = EnqueueStaleInstruments(
        _Untouchable(),  # type: ignore[arg-type]
        _Untouchable(),  # type: ignore[arg-type]
        _Untouchable(),  # type: ignore[arg-type]
        provider_resolver=resolver,  # type: ignore[arg-type]
    )

    result = await use_case.execute()

    assert result.scanned == 0
    assert result.enqueued == 0
    assert result.skipped_reason == "provider_disabled:yahoo"
    assert resolver.calls == ["ohlcv"]


@pytest.mark.asyncio
async def test_queue_item_is_not_claimed_when_provider_is_disabled() -> None:
    use_case = ProcessNextSyncQueueItem(
        _Untouchable(),  # type: ignore[arg-type]
        _Untouchable(),  # type: ignore[arg-type]
        provider_resolver=_DisabledResolver(),  # type: ignore[arg-type]
    )

    result = await use_case.execute()

    assert result.processed is False
    assert result.skipped_reason == "provider_disabled:yahoo"


class _Settings:
    post_market_only = True


class _Scheduler:
    def __init__(self, *, post_market_only: bool) -> None:
        self._settings = _Settings()
        self._settings.post_market_only = post_market_only
        self.claimed = 0

    async def get_settings(self) -> _Settings:
        return self._settings

    async def claim_next(self) -> Any:
        self.claimed += 1
        raise AssertionError("no debería reclamarse un ítem fuera de ventana")


@pytest.mark.asyncio
async def test_queue_item_waits_outside_post_market_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("bolsa_application.sync_scheduler.is_post_market_window", lambda: False)
    scheduler = _Scheduler(post_market_only=True)
    use_case = ProcessNextSyncQueueItem(scheduler, _Untouchable())  # type: ignore[arg-type]

    result = await use_case.execute()

    assert result == ProcessQueueResult(processed=False)
    assert scheduler.claimed == 0


def test_post_market_window_boundaries() -> None:
    # Miércoles 2026-10-28.
    assert is_post_market_window(datetime(2026, 10, 28, 17, 34, tzinfo=MADRID)) is False
    assert is_post_market_window(datetime(2026, 10, 28, 17, 35, tzinfo=MADRID)) is True
    assert is_post_market_window(datetime(2026, 10, 28, 21, 0, tzinfo=MADRID)) is True
    assert is_post_market_window(datetime(2026, 10, 28, 9, 0, tzinfo=MADRID)) is False
    # Sábado y domingo: mercado cerrado, pero la ventana no aplica.
    assert is_post_market_window(datetime(2026, 10, 31, 18, 0, tzinfo=MADRID)) is False
    assert is_post_market_window(datetime(2026, 11, 1, 18, 0, tzinfo=MADRID)) is False


def test_worker_applies_yahoo_throttle_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """SYN-10: el throttle del cliente Yahoo sale de la configuración persistida."""
    from bolsa_api.background import auto_sync_worker
    from bolsa_market import yahoo_client

    class _Client:
        min_interval_sec = 2.0

    fake = _Client()
    monkeypatch.setattr(yahoo_client, "get_yahoo_finance_client", lambda: fake)

    auto_sync_worker._apply_yahoo_throttle(
        [
            _config_for_throttle("yahoo", seconds=7),
            _config_for_throttle("xtb", seconds=0),
        ]
    )

    assert fake.min_interval_sec == 7.0


def _config_for_throttle(provider_id: str, *, seconds: int) -> Any:
    from bolsa_domain.entities.market_provider import MarketProviderConfig, provider_spec

    spec = provider_spec(provider_id)
    assert spec is not None
    return MarketProviderConfig(
        id=spec.id,
        label=spec.label,
        enabled=True,
        priority=spec.default_priority,
        min_interval_seconds=seconds,
        base_url="http://127.0.0.1:3002" if provider_id == "xtb" else None,
        capabilities=spec.capabilities,
    )


def test_note_provider_state_transitions_are_declared_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from bolsa_api.background import auto_sync_worker

    auto_sync_worker._last_provider_note = None
    with caplog.at_level("INFO"):
        auto_sync_worker._note_provider_state("provider_disabled:yahoo")
        auto_sync_worker._note_provider_state("provider_disabled:yahoo")
        auto_sync_worker._note_provider_state(None)

    messages = [record.getMessage() for record in caplog.records]
    assert sum("Auto-sync detenido por configuración" in message for message in messages) == 1
    assert sum("de nuevo disponible" in message for message in messages) == 1
