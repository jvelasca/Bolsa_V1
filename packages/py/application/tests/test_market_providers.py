"""Configuración y verificación de proveedores — casos puros (sin BD).

Cubre ``PRV-1``, ``PRV-4``…``PRV-10`` del documento
``docs/engineering/seguimiento-ui-proveedores-2026-10-29.md``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from bolsa_domain.entities.market_provider import (
    CAPABILITY_OHLCV,
    PROVIDER_XTB,
    PROVIDER_YAHOO,
    MarketProviderConfig,
    ProviderCheckPolicy,
    ProviderConfigError,
    capability_provider_candidates,
    normalize_base_url,
    normalize_min_interval_seconds,
    normalize_priority,
    provider_spec,
)
from bolsa_domain.value_objects.market import MarketProviderStatus
from bolsa_infrastructure.database.repositories.market_provider_settings_repository import (
    MarketProviderSettingsRecord,
)

from bolsa_application.market import GetMarketStatus
from bolsa_application.market_providers import (
    MarketProviderConfigResolver,
    ProviderHealthMonitor,
    TestProviderConnection,
    UnknownProviderError,
    UpdateMarketProviderConfig,
    invalidate_provider_config_cache,
    summarize_provider_health,
)


def _record(provider_id: str, **overrides: Any) -> MarketProviderSettingsRecord:
    spec = provider_spec(provider_id)
    assert spec is not None
    base: dict[str, Any] = {
        "id": spec.id,
        "enabled": spec.default_enabled,
        "priority": spec.default_priority,
        "min_interval_seconds": spec.default_min_interval_seconds,
        "base_url": None,
        "options": {},
        "last_check_at": None,
        "last_check_ok": None,
        "last_check_message": None,
        "updated_at": "2026-10-29T09:00:00+00:00",
    }
    base.update(overrides)
    return MarketProviderSettingsRecord(**base)


class FakeRepo:
    """Repositorio en memoria con la misma superficie que el SQLAlchemy."""

    def __init__(self, records: list[MarketProviderSettingsRecord] | None = None) -> None:
        self.records = {record.id: record for record in records or []}
        self.list_calls = 0
        self.checks: list[tuple[str, bool, str]] = []

    async def list_all(self) -> list[MarketProviderSettingsRecord]:
        self.list_calls += 1
        return list(self.records.values())

    async def get(self, provider_id: str) -> MarketProviderSettingsRecord | None:
        return self.records.get(provider_id)

    async def update(
        self,
        provider_id: str,
        *,
        enabled: bool | None = None,
        priority: int | None = None,
        min_interval_seconds: int | None = None,
        base_url: str | None = None,
    ) -> MarketProviderSettingsRecord | None:
        record = self.records.get(provider_id)
        if record is None:
            return None
        updated = MarketProviderSettingsRecord(
            id=record.id,
            enabled=record.enabled if enabled is None else enabled,
            priority=record.priority if priority is None else priority,
            min_interval_seconds=(
                record.min_interval_seconds
                if min_interval_seconds is None
                else min_interval_seconds
            ),
            base_url=record.base_url if base_url is None else (base_url or None),
            options=record.options,
            last_check_at=record.last_check_at,
            last_check_ok=record.last_check_ok,
            last_check_message=record.last_check_message,
            updated_at="2026-10-29T10:00:00+00:00",
        )
        self.records[provider_id] = updated
        return updated

    async def record_check(
        self, provider_id: str, *, ok: bool, message: str, at: Any = None
    ) -> MarketProviderSettingsRecord | None:
        self.checks.append((provider_id, ok, message))
        record = self.records.get(provider_id)
        if record is None:
            return None
        updated = MarketProviderSettingsRecord(
            id=record.id,
            enabled=record.enabled,
            priority=record.priority,
            min_interval_seconds=record.min_interval_seconds,
            base_url=record.base_url,
            options=record.options,
            last_check_at="2026-10-29T10:05:00+00:00",
            last_check_ok=ok,
            last_check_message=message,
            updated_at="2026-10-29T10:05:00+00:00",
        )
        self.records[provider_id] = updated
        return updated


def _resolver(repo: FakeRepo, *, env_url: str | None = None, clock: Any = None) -> Any:
    kwargs: dict[str, Any] = {"xtb_bridge_url": env_url}
    if clock is not None:
        kwargs["clock"] = clock
    return MarketProviderConfigResolver(repo, **kwargs)


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    invalidate_provider_config_cache()
    yield
    invalidate_provider_config_cache()


# ── PRV-1 · defaults del registro ────────────────────────────────────────────


def test_registry_defaults_and_env_fallback() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB)])

    configs = asyncio.run(_resolver(repo, env_url="http://127.0.0.1:3002").list_configs())

    yahoo = next(config for config in configs if config.id == PROVIDER_YAHOO)
    xtb = next(config for config in configs if config.id == PROVIDER_XTB)
    assert yahoo.enabled is True and yahoo.priority == 10
    assert yahoo.base_url is None and yahoo.base_url_source is None
    # La URL del entorno se declara como tal y no se copia a la BD.
    assert xtb.base_url == "http://127.0.0.1:3002"
    assert xtb.base_url_source == "env"
    assert repo.records[PROVIDER_XTB].base_url is None


def test_configured_base_url_wins_over_environment() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB, base_url="http://cfg:9000")])
    configs = asyncio.run(_resolver(repo, env_url="http://env:3002").list_configs())
    xtb = next(config for config in configs if config.id == PROVIDER_XTB)
    assert xtb.base_url == "http://cfg:9000"
    assert xtb.base_url_source == "config"


# ── PRV-5 · resolución por capacidad y prioridad ─────────────────────────────


def _config(
    provider_id: str,
    *,
    enabled: bool,
    priority: int,
    base_url: str | None = None,
) -> MarketProviderConfig:
    spec = provider_spec(provider_id)
    assert spec is not None
    return MarketProviderConfig(
        id=spec.id,
        label=spec.label,
        enabled=enabled,
        priority=priority,
        min_interval_seconds=spec.default_min_interval_seconds,
        base_url=base_url,
        capabilities=spec.capabilities,
    )


def test_capability_candidates_are_limited_by_capability() -> None:
    candidates = capability_provider_candidates(
        [
            _config(PROVIDER_YAHOO, enabled=True, priority=40),
            _config(PROVIDER_XTB, enabled=True, priority=10, base_url="http://b"),
        ],
        CAPABILITY_OHLCV,
    )
    # XTB no cubre OHLCV: el orden por prioridad no lo cuela donde no sirve.
    assert [candidate.id for candidate in candidates] == [PROVIDER_YAHOO]


def test_capability_candidates_skip_unusable() -> None:
    candidates = capability_provider_candidates(
        [
            _config(PROVIDER_YAHOO, enabled=False, priority=1),
            _config(PROVIDER_XTB, enabled=True, priority=2, base_url=None),
        ],
        "live_quote",
    )
    # XTB habilitado pero sin URL no es usable: no se ofrece como alternativa.
    assert candidates == []


# ── PRV-6 · proveedor deshabilitado no resuelve ─────────────────────────────


@pytest.mark.asyncio
async def test_disabled_provider_does_not_resolve() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO, enabled=False), _record(PROVIDER_XTB)])
    resolution = await _resolver(repo).resolve_capability(CAPABILITY_OHLCV)
    assert resolution.provider is None
    assert resolution.reason == "provider_disabled:yahoo"


@pytest.mark.asyncio
async def test_unknown_capability_declares_no_provider() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB)])
    resolution = await _resolver(repo).resolve_capability("sentiment")
    assert resolution.provider is None
    assert resolution.reason == "no_provider_declared"


# ── PRV-9 · caché de resolución ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_caches_until_ttl_or_invalidation() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB)])
    now = {"value": 0.0}
    resolver = _resolver(repo, clock=lambda: now["value"])

    await resolver.list_configs()
    await resolver.list_configs()
    assert repo.list_calls == 1

    now["value"] = 31.0  # supera el TTL de 30 s
    await resolver.list_configs()
    assert repo.list_calls == 2

    invalidate_provider_config_cache()
    await resolver.list_configs()
    assert repo.list_calls == 3


# ── PRV-4 · validación de PATCH ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_rejects_unknown_provider() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO)])
    with pytest.raises(UnknownProviderError):
        await UpdateMarketProviderConfig(  # type: ignore[arg-type]
            repo, on_change=lambda: None
        ).execute("nasdaq")


@pytest.mark.asyncio
async def test_update_rejects_invalid_url_and_ranges() -> None:
    repo = FakeRepo([_record(PROVIDER_XTB, base_url="http://127.0.0.1:3002")])
    use_case = UpdateMarketProviderConfig(repo, on_change=lambda: None)  # type: ignore[arg-type]

    with pytest.raises(ProviderConfigError):
        await use_case.execute(PROVIDER_XTB, base_url="ftp://bridge", base_url_provided=True)
    with pytest.raises(ProviderConfigError):
        await use_case.execute(PROVIDER_XTB, base_url="127.0.0.1:3002", base_url_provided=True)
    with pytest.raises(ProviderConfigError):
        await use_case.execute(PROVIDER_YAHOO, base_url="http://yahoo", base_url_provided=True)
    with pytest.raises(ProviderConfigError):
        await use_case.execute(PROVIDER_YAHOO, priority=101)
    with pytest.raises(ProviderConfigError):
        await use_case.execute(PROVIDER_YAHOO, min_interval_seconds=-1)


@pytest.mark.asyncio
async def test_update_only_applies_declared_fields() -> None:
    repo = FakeRepo(
        [
            _record(PROVIDER_YAHOO),
            _record(PROVIDER_XTB, base_url="http://127.0.0.1:3002", priority=20),
        ]
    )
    updated = await UpdateMarketProviderConfig(  # type: ignore[arg-type]
        repo, on_change=lambda: None
    ).execute(PROVIDER_XTB, enabled=False)
    assert updated.enabled is False
    assert updated.priority == 20  # no declarado ⇒ intacto
    assert updated.base_url == "http://127.0.0.1:3002"


@pytest.mark.asyncio
async def test_update_can_clear_base_url_explicitly() -> None:
    repo = FakeRepo([_record(PROVIDER_XTB, base_url="http://127.0.0.1:3002")])
    updated = await UpdateMarketProviderConfig(  # type: ignore[arg-type]
        repo, on_change=lambda: None
    ).execute(PROVIDER_XTB, base_url=None, base_url_provided=True)
    assert updated.base_url is None
    assert updated.missing_configuration is True


def test_normalizers_are_explicit() -> None:
    assert normalize_base_url("http://127.0.0.1:3002/") == "http://127.0.0.1:3002"
    assert normalize_base_url("  ") is None
    assert normalize_priority(None) is None
    assert normalize_min_interval_seconds(0) == 0
    with pytest.raises(ProviderConfigError):
        normalize_base_url("javascript:alert(1)")


# ── PRV-7/8 · test de conexión ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connection_probe_ok_persists_result() -> None:
    repo = FakeRepo([_record(PROVIDER_XTB, base_url="http://127.0.0.1:3002")])

    class _Health:
        status = "ok"
        mode = "mock"
        message = "Bridge mock listo"

    async def _health(url: str) -> _Health:
        assert url == "http://127.0.0.1:3002"
        return _Health()

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, xtb_health=_health, on_change=lambda: None
    ).execute(PROVIDER_XTB)

    assert result.ok is True
    assert "Bridge mock listo" in result.message
    assert repo.checks == [(PROVIDER_XTB, True, "Bridge mock listo")]
    assert repo.records[PROVIDER_XTB].last_check_ok is True


@pytest.mark.asyncio
async def test_connection_probe_failure_is_a_result_not_a_crash() -> None:
    repo = FakeRepo([_record(PROVIDER_XTB, base_url="http://127.0.0.1:3999")])

    async def _health(_url: str) -> Any:
        raise ConnectionError("connection refused")

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, xtb_health=_health, on_change=lambda: None
    ).execute(PROVIDER_XTB)

    assert result.ok is False
    assert "connection refused" in result.message.lower()
    assert repo.records[PROVIDER_XTB].last_check_ok is False


@pytest.mark.asyncio
async def test_connection_probe_without_url_does_not_call_bridge() -> None:
    repo = FakeRepo([_record(PROVIDER_XTB)])
    called = False

    async def _health(_url: str) -> Any:
        nonlocal called
        called = True
        raise AssertionError("no debería llamarse sin URL")

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, xtb_health=_health, on_change=lambda: None
    ).execute(PROVIDER_XTB)

    assert called is False
    assert result.ok is False
    assert "URL" in result.message


@pytest.mark.asyncio
async def test_yahoo_probe_disabled_does_not_measure() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO, enabled=False)])

    async def _probe() -> Any:
        raise AssertionError("no se debe medir un proveedor deshabilitado")

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, yahoo_probe=_probe, on_change=lambda: None
    ).execute(PROVIDER_YAHOO)

    assert result.ok is False
    assert "deshabilitado" in result.message.lower()


@pytest.mark.asyncio
async def test_yahoo_probe_reports_price_on_success() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO)])

    async def _probe() -> tuple[float, str]:
        return 11.2345, "2026-10-29T09:00:00Z"

    result = await TestProviderConnection(  # type: ignore[arg-type]
        repo, yahoo_probe=_probe, on_change=lambda: None
    ).execute(PROVIDER_YAHOO)

    assert result.ok is True
    assert "11.2345" in result.message
    assert repo.records[PROVIDER_YAHOO].last_check_ok is True


# ── PRV-10 · estado honesto ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_market_status_never_claims_health_without_measurement() -> None:
    configs = [
        MarketProviderConfig(
            id=PROVIDER_YAHOO,
            label="Yahoo Finance",
            enabled=True,
            priority=10,
            min_interval_seconds=2,
            base_url=None,
            capabilities=("ohlcv",),
        ),
        MarketProviderConfig(
            id=PROVIDER_XTB,
            label="XTB Bridge",
            enabled=True,
            priority=20,
            min_interval_seconds=0,
            base_url=None,
            capabilities=("live_quote",),
        ),
    ]
    statuses = await GetMarketStatus(configs).execute()

    yahoo = next(status for status in statuses if status.id == PROVIDER_YAHOO)
    xtb = next(status for status in statuses if status.id == PROVIDER_XTB)
    assert yahoo.healthy is False and yahoo.verified is False
    assert "Sin verificar" in yahoo.message
    assert xtb.healthy is False and xtb.verified is False
    assert "URL" in xtb.message


@pytest.mark.asyncio
async def test_market_status_uses_persisted_verification_for_yahoo() -> None:
    repo = FakeRepo(
        [
            _record(
                PROVIDER_YAHOO,
                last_check_at="2026-10-29T10:05:00+00:00",
                last_check_ok=True,
                last_check_message="Yahoo respondió 11.2345",
            ),
            _record(PROVIDER_XTB),
        ]
    )
    configs = await _resolver(repo).list_configs()
    statuses = await GetMarketStatus(configs).execute()
    yahoo = next(status for status in statuses if status.id == PROVIDER_YAHOO)
    assert yahoo.healthy is True
    assert yahoo.verified is True
    assert yahoo.last_check_at == "2026-10-29T10:05:00+00:00"


@pytest.mark.asyncio
async def test_market_status_measures_xtb_live_when_configured() -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB, base_url="http://b")])

    class _Health:
        status = "ok"
        mode = "mock"
        message = "Bridge mock"

    async def _health(_url: str) -> _Health:
        return _Health()

    configs = await _resolver(repo).list_configs()
    statuses = await GetMarketStatus(configs, xtb_health=_health).execute()
    xtb = next(status for status in statuses if status.id == PROVIDER_XTB)
    assert xtb.healthy is True
    assert xtb.verified is True
    assert xtb.message == "Bridge mock"


@pytest.mark.asyncio
async def test_market_status_non_live_reads_only_persisted_state() -> None:
    """El GET de salud no mide: con ``live=False`` no se llama al bridge."""
    repo = FakeRepo(
        [
            _record(PROVIDER_YAHOO),
            _record(
                PROVIDER_XTB,
                base_url="http://b",
                last_check_at="2026-10-29T10:05:00+00:00",
                last_check_ok=False,
                last_check_message="Bridge no responde",
            ),
        ]
    )
    calls = {"n": 0}

    async def _health(_url: str) -> Any:
        calls["n"] += 1
        return None

    configs = await _resolver(repo).list_configs()
    statuses = await GetMarketStatus(configs, xtb_health=_health, live=False).execute()
    xtb = next(status for status in statuses if status.id == PROVIDER_XTB)
    assert calls["n"] == 0
    assert xtb.verified is True
    assert xtb.healthy is False
    assert xtb.message == "Bridge no responde"



# ── PRV-11/12 · salud agregada para la barra de estado ──────────────────────


def _status(
    provider_id: str,
    *,
    enabled: bool = True,
    healthy: bool = True,
    verified: bool = True,
    message: str = "Verificado correctamente",
    last_check_at: str | None = "2026-10-29T10:05:00+00:00",
) -> MarketProviderStatus:
    spec = provider_spec(provider_id)
    assert spec is not None
    return MarketProviderStatus(
        id=spec.id,
        label=spec.label,
        enabled=enabled,
        healthy=healthy,
        message=message,
        capabilities=spec.capabilities,
        verified=verified,
        last_check_at=last_check_at if verified else None,
        last_check_ok=healthy if verified else None,
    )


#: Instante de referencia de los tests de salud: 5 s después de la medición por defecto.
_NOW = datetime(2026, 10, 29, 10, 5, 5, tzinfo=UTC)


def test_summary_ok_when_every_enabled_provider_is_measured_and_healthy() -> None:
    summary = summarize_provider_health(
        [_status(PROVIDER_YAHOO), _status(PROVIDER_XTB)], now=_NOW
    )
    assert summary.status == "ok"
    assert summary.ok is True
    assert summary.measured_at == "2026-10-29T10:05:00+00:00"
    assert summary.auto_check_enabled is True
    assert summary.check_interval_seconds == 60
    assert summary.next_check_at == "2026-10-29T10:06:00+00:00"


def test_summary_stale_when_measurement_aged_past_policy() -> None:
    """ON + medición más vieja que 2×intervalo ⇒ ámbar `stale`, nunca verde."""
    summary = summarize_provider_health(
        [_status(PROVIDER_YAHOO)],
        policy=ProviderCheckPolicy(enabled=True, interval_seconds=60),
        now=datetime(2026, 10, 29, 10, 7, 1, tzinfo=UTC),
    )
    assert summary.status == "stale"
    assert summary.ok is False
    assert summary.stale is True


def test_summary_off_never_reports_stale() -> None:
    """OFF no es «bucle caído»: sin cadencia declarada no hay nada que refrescar."""
    summary = summarize_provider_health(
        [_status(PROVIDER_YAHOO)],
        policy=ProviderCheckPolicy(enabled=False, interval_seconds=60),
        now=datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
    )
    assert summary.status == "ok"
    assert summary.auto_check_enabled is False
    assert summary.next_check_at is None


def test_summary_degraded_wins_over_unverified() -> None:
    summary = summarize_provider_health(
        [
            _status(PROVIDER_YAHOO, healthy=False, message="Yahoo sin respuesta"),
            _status(PROVIDER_XTB, verified=False),
        ]
    )
    assert summary.status == "degraded"
    assert summary.ok is False


def test_summary_unverified_when_nothing_failed_but_something_is_unmeasured() -> None:
    summary = summarize_provider_health([_status(PROVIDER_YAHOO, verified=False)])
    assert summary.status == "unverified"
    assert summary.ok is False


def test_summary_none_when_no_provider_is_enabled() -> None:
    summary = summarize_provider_health([_status(PROVIDER_YAHOO, enabled=False)])
    assert summary.status == "none"
    assert summary.ok is False


def test_summary_ignores_disabled_provider_even_if_it_failed() -> None:
    summary = summarize_provider_health(
        [
            _status(PROVIDER_YAHOO),
            _status(
                PROVIDER_XTB,
                enabled=False,
                healthy=False,
                verified=True,
                message="Deshabilitado en Configuración",
            ),
        ],
        now=_NOW,
    )
    # Apagar un proveedor es una decisión del operador, no una caída.
    assert summary.status == "ok"
    assert summary.ok is True

class _DummySession:
    def __init__(self) -> None:
        self.committed = 0

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, *_exc: Any) -> bool:
        return False

    async def commit(self) -> None:
        self.committed += 1


def _monitor(
    monkeypatch: pytest.MonkeyPatch,
    repo: FakeRepo,
    *,
    policy: ProviderCheckPolicy | None = None,
    clock: Any = None,
    probe_factory: Any = None,
) -> tuple[ProviderHealthMonitor, _DummySession]:
    import bolsa_application.market_providers as module

    monkeypatch.setattr(
        module, "SqlAlchemyMarketProviderSettingsRepository", lambda _session: repo
    )
    session = _DummySession()
    kwargs: dict[str, Any] = {"policy": policy or ProviderCheckPolicy()}
    if clock is not None:
        kwargs["clock"] = clock
    if probe_factory is not None:
        kwargs["probe_factory"] = probe_factory
    return ProviderHealthMonitor(lambda: session, **kwargs), session


@pytest.mark.asyncio
async def test_monitor_probes_only_enabled_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO), _record(PROVIDER_XTB, enabled=False)])
    monitor, session = _monitor(monkeypatch, repo)

    async def _probe() -> tuple[float, str]:
        return 11.2345, "2026-10-29T09:00:00Z"

    monkeypatch.setattr(
        "bolsa_application.market_providers._default_yahoo_probe", _probe
    )
    results = await monitor.probe_now()

    assert set(results) == {PROVIDER_YAHOO}
    assert results[PROVIDER_YAHOO].ok is True
    assert repo.checks == [(PROVIDER_YAHOO, True, results[PROVIDER_YAHOO].message)]
    assert session.committed == 1
    # El deshabilitado no se mide: no se escribe un fallo engañoso en last_check_*.
    assert all(check[0] != PROVIDER_XTB for check in repo.checks)


@pytest.mark.asyncio
async def test_monitor_probe_if_due_respects_persisted_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La cadencia sale de la política + ``last_check_at``, no de un contador en memoria."""
    repo = FakeRepo([_record(PROVIDER_YAHOO)])
    calls = {"n": 0}

    async def _probe() -> tuple[float, str]:
        calls["n"] += 1
        return 11.2345, "2026-10-29T09:00:00Z"

    monkeypatch.setattr("bolsa_application.market_providers._default_yahoo_probe", _probe)
    moment = {"value": datetime(2026, 10, 29, 10, 5, 30, tzinfo=UTC)}
    policy = ProviderCheckPolicy(enabled=True, interval_seconds=60)
    monitor, _session = _monitor(
        monkeypatch, repo, policy=policy, clock=lambda: moment["value"]
    )

    # FakeRepo.record_check fija last_check_at = 10:05:00; a las 10:05:30 aún no toca.
    repo.records[PROVIDER_YAHOO] = _record(
        PROVIDER_YAHOO, last_check_at="2026-10-29T10:05:00+00:00", last_check_ok=True
    )
    assert await monitor.probe_if_due() is None
    assert calls["n"] == 0

    # A las 10:06:00 la edad iguala el intervalo configurado: toca.
    moment["value"] = datetime(2026, 10, 29, 10, 6, 0, tzinfo=UTC)
    results = await monitor.probe_if_due()
    assert results is not None
    assert PROVIDER_YAHOO in results
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_monitor_does_not_probe_when_automatic_check_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OFF detiene la cadencia, pero no impide un diagnóstico manual (force)."""
    repo = FakeRepo([_record(PROVIDER_YAHOO)])

    async def _probe() -> tuple[float, str]:
        return 11.2345, "2026-10-29T09:00:00Z"

    monkeypatch.setattr("bolsa_application.market_providers._default_yahoo_probe", _probe)
    monitor, _session = _monitor(
        monkeypatch, repo, policy=ProviderCheckPolicy(enabled=False, interval_seconds=60)
    )

    assert await monitor.probe_if_due() is None
    assert repo.checks == []

    forced = await monitor.probe_if_due(force=True)
    assert forced is not None and forced[PROVIDER_YAHOO].ok is True
    assert len(repo.checks) == 1


@pytest.mark.asyncio
async def test_monitor_survives_provider_probe_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeRepo([_record(PROVIDER_YAHOO)])
    session = _DummySession()

    class _ExplodingProbe:
        async def execute(self, provider_id: str) -> Any:
            raise RuntimeError(f"boom {provider_id}")

    import bolsa_application.market_providers as module

    monkeypatch.setattr(
        module, "SqlAlchemyMarketProviderSettingsRepository", lambda _session: repo
    )
    monitor = ProviderHealthMonitor(lambda: session, probe_factory=lambda _r: _ExplodingProbe())

    results = await monitor.probe_now()
    assert results == {}
    assert session.committed == 1


@pytest.mark.asyncio
async def test_monitor_aclose_cancels_in_flight_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    repo = FakeRepo([_record(PROVIDER_YAHOO)])
    started = threading.Event()
    release = asyncio.Event()

    async def _probe() -> tuple[float, str]:
        started.set()
        await release.wait()
        return 1.0, "2026-10-29T09:00:00Z"

    monkeypatch.setattr("bolsa_application.market_providers._default_yahoo_probe", _probe)
    monitor, _session = _monitor(monkeypatch, repo)

    assert monitor.ensure_fresh() is True
    while not started.is_set():
        await asyncio.sleep(0.01)
    assert monitor.probing is True

    await monitor.aclose()
    assert monitor.probing is False
