"""Casos de uso — configuración y verificación de proveedores de datos.

Separa tres responsabilidades que antes estaban mezcladas o no existían:

1. **Resolver** la configuración efectiva (BD + entorno) con una caché corta, para que
   workers y peticiones no consulten la tabla en cada llamada.
2. **Actualizar** la configuración con validación explícita (la API traduce los errores).
3. **Verificar** un proveedor («Probar conexión») con una llamada real acotada, y
   persistir el resultado para que el estado deje de ser una suposición.

Doctrina: un proveedor deshabilitado (o sin su configuración mínima) **no** se resuelve.
No hay caída silenciosa a otro proveedor ni estado «disponible» sin medición.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from bolsa_domain.entities.market_provider import (
    DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS,
    MARKET_PROVIDER_SPECS,
    MarketProviderConfig,
    MarketProviderSpec,
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
    SqlAlchemyMarketProviderSettingsRepository,
)
from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
    SqlAlchemySyncSchedulerRepository,
)
from bolsa_market.providers import (
    XtbBridgeClient,
    XtbBridgeHealth,
    format_xtb_bridge_connect_error,
)

__all__ = [
    "PROVIDER_CONFIG_CACHE_TTL_SECONDS",
    "PROVIDER_HEALTH_MAX_AGE_SECONDS",
    "ProviderCheckPolicy",
    "ProviderConfigError",
    "ProviderHealthEntry",
    "ProviderHealthMonitor",
    "ProviderHealthSummary",
    "ProviderProbeResult",
    "ProviderResolution",
    "MarketProviderConfigResolver",
    "ListMarketProviderConfigs",
    "UpdateMarketProviderConfig",
    "TestProviderConnection",
    "UnknownProviderError",
    "invalidate_provider_config_cache",
    "summarize_provider_health",
]

logger = logging.getLogger(__name__)

#: La caché existe para que el worker no consulte la BD cada 15 s. 30 s es el techo de
#: desfase aceptado entre «guardar en Configuración» y «el worker lo aplica»; un PATCH en
#: el MISMO proceso invalida de inmediato.
PROVIDER_CONFIG_CACHE_TTL_SECONDS = 30.0

#: Cadencia por defecto del sondeo agrupado. Se conserva el nombre histórico como alias
#: de la política del dominio (060); la cadencia efectiva es configurable y vive en
#: ``sync_settings``. La barra consulta cada ≤60 s: con 60 s se detecta una caída rápido
#: sin encadenar peticiones reales a Yahoo.
PROVIDER_HEALTH_MAX_AGE_SECONDS = float(DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS)

#: Tick del bucle del comprobador: comprueba si el dato persistido venció. No es la
#: cadencia (esa es configurable); solo acota el retraso máximo en detectar el vencimiento.
PROVIDER_HEALTH_TICK_SECONDS = 10.0

#: La distinción «baseUrl omitido» vs «baseUrl: null» se hace con ``base_url_provided``.


class UnknownProviderError(LookupError):
    """El ID de proveedor no existe en el registro (se traduce a 404)."""


@dataclass(frozen=True, slots=True)
class ProviderProbeResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ProviderResolution:
    """Resultado de resolver una capacidad: proveedor usable o motivo del fallo."""

    capability: str
    provider: MarketProviderConfig | None
    reason: str | None = None


def _effective_config(
    record: MarketProviderSettingsRecord,
    spec: MarketProviderSpec,
    *,
    xtb_bridge_url: str | None,
) -> MarketProviderConfig:
    base_url = record.base_url
    source = "config" if base_url else None
    if not base_url and spec.id == "xtb":
        env_url = str(xtb_bridge_url or "").strip()
        if env_url:
            # La URL del entorno se DECLARA como tal: no se copia a la BD para que el
            # operador sepa que cambiarla allí sigue teniendo efecto.
            base_url = env_url.rstrip("/")
            source = "env"
    return MarketProviderConfig(
        id=spec.id,
        label=spec.label,
        enabled=record.enabled,
        priority=record.priority,
        min_interval_seconds=record.min_interval_seconds,
        base_url=base_url,
        capabilities=spec.capabilities,
        description=spec.description,
        base_url_source=source,
        last_check_at=record.last_check_at,
        last_check_ok=record.last_check_ok,
        last_check_message=record.last_check_message,
        updated_at=record.updated_at,
    )


#: Caché de proceso (no por sesión): los workers crean una sesión por tick y no deben
#: pagar una consulta por tick. Se invalida al guardar y caduca por TTL.
_CACHE: dict[str, Any] = {"loaded_at": 0.0, "configs": ()}


def invalidate_provider_config_cache() -> None:
    """Fuerza la relectura en la próxima resolución (mismo proceso)."""
    _CACHE["loaded_at"] = 0.0
    _CACHE["configs"] = ()


class MarketProviderConfigResolver:
    """Configuración efectiva de proveedores, con caché corta y fallback de entorno."""

    def __init__(
        self,
        repository: SqlAlchemyMarketProviderSettingsRepository,
        *,
        xtb_bridge_url: str | None = None,
        cache_ttl_seconds: float = PROVIDER_CONFIG_CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repo = repository
        self._xtb_bridge_url = xtb_bridge_url
        self._ttl = max(0.0, float(cache_ttl_seconds))
        self._clock = clock

    async def list_configs(self, *, refresh: bool = False) -> list[MarketProviderConfig]:
        cached = _CACHE["configs"]
        fresh = (
            not refresh
            and bool(cached)
            and (self._clock() - float(_CACHE["loaded_at"])) < self._ttl
        )
        if fresh:
            return list(cached)
        records = await self._repo.list_all()
        by_id = {record.id: record for record in records}
        configs = tuple(
            _effective_config(by_id[spec.id], spec, xtb_bridge_url=self._xtb_bridge_url)
            for spec in MARKET_PROVIDER_SPECS
            if spec.id in by_id
        )
        _CACHE["configs"] = configs
        _CACHE["loaded_at"] = self._clock()
        return list(configs)

    async def get(self, provider_id: str, *, refresh: bool = False) -> MarketProviderConfig | None:
        spec = provider_spec(provider_id)
        if spec is None:
            return None
        for config in await self.list_configs(refresh=refresh):
            if config.id == spec.id:
                return config
        return None

    async def resolve_capability(
        self, capability: str, *, refresh: bool = False
    ) -> ProviderResolution:
        candidates = capability_provider_candidates(
            await self.list_configs(refresh=refresh), capability
        )
        if candidates:
            return ProviderResolution(capability=capability, provider=candidates[0])
        declared = [
            config.id
            for config in await self.list_configs(refresh=refresh)
            if config.supports(capability)
        ]
        if not declared:
            return ProviderResolution(
                capability=capability, provider=None, reason="no_provider_declared"
            )
        return ProviderResolution(
            capability=capability,
            provider=None,
            reason=f"provider_disabled:{declared[0]}",
        )


class ListMarketProviderConfigs:
    """Lista la configuración efectiva del registro completo."""

    def __init__(self, resolver: MarketProviderConfigResolver) -> None:
        self._resolver = resolver

    async def execute(self, *, refresh: bool = False) -> list[MarketProviderConfig]:
        return await self._resolver.list_configs(refresh=refresh)


class UpdateMarketProviderConfig:
    """Actualiza la configuración de un proveedor con validación explícita."""

    def __init__(
        self,
        repository: SqlAlchemyMarketProviderSettingsRepository,
        *,
        xtb_bridge_url: str | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._repo = repository
        self._xtb_bridge_url = xtb_bridge_url
        self._on_change = on_change or invalidate_provider_config_cache

    async def execute(
        self,
        provider_id: str,
        *,
        enabled: bool | None = None,
        priority: int | None = None,
        min_interval_seconds: int | None = None,
        base_url: str | None = None,
        base_url_provided: bool = False,
    ) -> MarketProviderConfig:
        spec = provider_spec(provider_id)
        if spec is None:
            raise UnknownProviderError(provider_id)
        if base_url_provided and not spec.configurable_base_url:
            raise ProviderConfigError(
                f"{spec.id} no admite baseUrl configurable (se resuelve por entorno)"
            )

        normalized_priority = normalize_priority(priority)
        normalized_interval = normalize_min_interval_seconds(min_interval_seconds)

        record = await self._repo.get(spec.id)
        if record is None:
            raise UnknownProviderError(provider_id)

        if not base_url_provided:
            updated = await self._repo.update(
                spec.id,
                enabled=enabled,
                priority=normalized_priority,
                min_interval_seconds=normalized_interval,
            )
        else:
            normalized_url = normalize_base_url(base_url)
            updated = await self._repo.update(
                spec.id,
                enabled=enabled,
                priority=normalized_priority,
                min_interval_seconds=normalized_interval,
                # Cadena vacía = «borrar la URL» (el repositorio la convierte en NULL).
                base_url=normalized_url if normalized_url is not None else "",
            )
        if updated is None:
            raise UnknownProviderError(provider_id)
        self._on_change()
        return _effective_config(updated, spec, xtb_bridge_url=self._xtb_bridge_url)


class TestProviderConnection:
    """Verifica un proveedor con una llamada real acotada y persiste el resultado.

    * ``xtb`` — ``GET /health`` del bridge configurado.
    * ``yahoo`` — petición de precio spot de un símbolo de referencia (una sola llamada).

    Nunca lanza por un fallo del proveedor: el fallo **es** el resultado y queda en
    ``last_check_*`` (la UI lo muestra). Solo se lanza por un ID desconocido.
    """

    #: El nombre empieza por «Test» por claridad del caso de uso; no es una clase de
    #: pytest (se evita que el colector la intente instanciar).
    __test__ = False

    def __init__(
        self,
        repository: SqlAlchemyMarketProviderSettingsRepository,
        *,
        xtb_bridge_url: str | None = None,
        xtb_health: Callable[[str], Any] | None = None,
        yahoo_probe: Callable[[], Any] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._repo = repository
        self._xtb_bridge_url = xtb_bridge_url
        self._xtb_health = xtb_health or _default_xtb_health
        self._yahoo_probe = yahoo_probe or _default_yahoo_probe
        self._on_change = on_change or invalidate_provider_config_cache

    async def execute(self, provider_id: str) -> ProviderProbeResult:
        spec = provider_spec(provider_id)
        if spec is None:
            raise UnknownProviderError(provider_id)
        record = await self._repo.get(spec.id)
        if record is None:
            raise UnknownProviderError(provider_id)
        config = _effective_config(record, spec, xtb_bridge_url=self._xtb_bridge_url)

        if spec.id == "xtb":
            result = await self._probe_xtb(config)
        else:
            result = await self._probe_yahoo(config)

        await self._repo.record_check(spec.id, ok=result.ok, message=result.message)
        self._on_change()
        return result

    async def _probe_xtb(self, config: MarketProviderConfig) -> ProviderProbeResult:
        if not config.base_url:
            return ProviderProbeResult(
                ok=False,
                message="Sin URL de bridge: configura baseUrl o XTB_BRIDGE_URL",
            )
        try:
            health: XtbBridgeHealth = await self._xtb_health(config.base_url)
        except Exception as exc:  # noqa: BLE001 — el fallo es el resultado
            return ProviderProbeResult(
                ok=False,
                message=format_xtb_bridge_connect_error(config.base_url, exc),
            )
        ok = getattr(health, "status", "") == "ok"
        message = getattr(health, "message", "") or (
            f"Bridge {getattr(health, 'mode', '')}".strip() or "Bridge sin mensaje"
        )
        return ProviderProbeResult(ok=ok, message=message)

    async def _probe_yahoo(self, config: MarketProviderConfig) -> ProviderProbeResult:
        if not config.enabled:
            return ProviderProbeResult(
                ok=False, message="Yahoo está deshabilitado: no se lanza la comprobación"
            )
        try:
            price, timestamp = await self._yahoo_probe()
        except Exception as exc:  # noqa: BLE001 — el fallo es el resultado
            return ProviderProbeResult(
                ok=False, message=f"Yahoo sin respuesta: {type(exc).__name__}: {exc}"
            )
        try:
            formatted = f"{float(price):.4f}"
        except (TypeError, ValueError):
            return ProviderProbeResult(
                ok=False, message=f"Yahoo devolvió un precio no numérico: {price!r}"
            )
        return ProviderProbeResult(
            ok=True,
            message=f"Yahoo respondió {formatted} (ref. ^IBEX, {timestamp})",
        )


async def _default_xtb_health(base_url: str) -> XtbBridgeHealth:
    return await XtbBridgeClient(base_url).check_health()


async def _default_yahoo_probe() -> tuple[float, str]:
    from bolsa_market.yahoo_client import get_yahoo_finance_client

    return await get_yahoo_finance_client().fetch_spot_price("^IBEX")


# ── Salud agregada de proveedores (barra de estado del terminal) ─────────────


@dataclass(frozen=True, slots=True)
class ProviderHealthEntry:
    """Un proveedor dentro del veredicto agregado (publicado tal cual a la UI)."""

    id: str
    label: str
    enabled: bool
    healthy: bool
    verified: bool
    message: str
    last_check_at: str | None = None
    last_check_ok: bool | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealthSummary:
    """Veredicto único para el icono: ``ok`` | ``degraded`` | ``stale`` | ``unverified``
    | ``none``.

    Regla de precedencia: un fallo medido (rojo) gana sobre una falta de medición
    (ámbar). Un proveedor **deshabilitado** no entra en el veredicto: apagarlo es una
    decisión del operador, no una caída. ``stale`` (ámbar) es distinto de ``unverified``:
    hay medición, pero es más vieja que la cadencia declarada y el bucle no la refresca.
    """

    status: str
    ok: bool
    measured_at: str | None
    providers: tuple[ProviderHealthEntry, ...]
    #: Política publicada junto al veredicto: la UI no inventa ni duplica la cadencia.
    auto_check_enabled: bool = True
    check_interval_seconds: int = DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS
    #: Instante en que toca la siguiente comprobación automática (``None`` si está OFF).
    next_check_at: str | None = None

    @property
    def degraded(self) -> bool:
        return self.status == "degraded"

    @property
    def stale(self) -> bool:
        return self.status == "stale"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def summarize_provider_health(
    statuses: Sequence[MarketProviderStatus],
    *,
    policy: ProviderCheckPolicy | None = None,
    now: datetime | None = None,
) -> ProviderHealthSummary:
    """Agrega el estado por proveedor en el veredicto de la barra.

    Acepta ``MarketProviderStatus`` (value object) porque el llamador ya resolvió la
    configuración efectiva; no se vuelve a leer la BD para construir el resumen.
    """
    effective_policy = policy or ProviderCheckPolicy()
    moment = now or datetime.now(UTC)

    entries = tuple(
        ProviderHealthEntry(
            id=str(status.id),
            label=str(status.label),
            enabled=bool(status.enabled),
            healthy=bool(status.healthy),
            verified=bool(status.verified),
            message=str(status.message),
            last_check_at=status.last_check_at,
            last_check_ok=status.last_check_ok,
        )
        for status in statuses
    )
    considered = [entry for entry in entries if entry.enabled]

    def _summary(status: str, measured: datetime | None) -> ProviderHealthSummary:
        return ProviderHealthSummary(
            status=status,
            ok=status == "ok",
            measured_at=measured.isoformat() if measured is not None else None,
            providers=entries,
            auto_check_enabled=effective_policy.enabled,
            check_interval_seconds=effective_policy.interval_seconds,
            next_check_at=(
                (measured + timedelta(seconds=effective_policy.interval_seconds)).isoformat()
                if measured is not None and effective_policy.enabled
                else None
            ),
        )

    if not considered:
        return _summary("none", None)

    failing = [entry for entry in considered if entry.verified and not entry.healthy]
    unmeasured = [entry for entry in considered if not entry.verified]
    measured = [parsed for parsed in (_parse_iso(entry.last_check_at) for entry in considered) if parsed]
    latest = max(measured) if measured else None

    if failing:
        status = "degraded"
    elif unmeasured:
        status = "unverified"
    elif (
        effective_policy.enabled
        and latest is not None
        and (moment - latest).total_seconds() > effective_policy.stale_after_seconds
    ):
        # Hay medición y era correcta, pero ya no se refresca al ritmo declarado: el bucle
        # no está corriendo. Verde aquí sería afirmar salud sin medirla ahora.
        status = "stale"
    else:
        status = "ok"

    return _summary(status, latest)


class ProviderHealthMonitor:
    """Comprobador de proveedores: al arranque y cuando el dato persistido vence.

    Dos piezas que antes estaban mezcladas:

    * ``probe_now()`` — mide los proveedores **habilitados** y persiste ``last_check_*``.
      Es lo único que produce estado; ningún GET mide por su cuenta.
    * ``run_forever()`` — bucle del proceso API que cada ``tick_seconds`` llama a
      ``probe_if_due()``. La cadencia NO vive en memoria: se lee de ``sync_settings``
      (``provider_check_enabled`` / ``provider_check_interval_seconds``) y se compara con
      el ``last_check_at`` persistido, así que configurar 300 s no deja un ``_last_probe``
      viejo gobernando el proceso hasta reiniciar.

    Los sondeos concurrentes se serializan con un ``asyncio.Lock`` (dos sondas a la vez
    duplicarían peticiones reales y podrían escribir un fallo por una carrera). El fallo
    de la sonda nunca se propaga: el fallo ES un dato que la barra debe poder pintar.
    """

    __test__ = False  # no es una clase de pytest

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        xtb_bridge_url: str | None = None,
        policy: ProviderCheckPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        tick_seconds: float = PROVIDER_HEALTH_TICK_SECONDS,
        sleep: Callable[[float], Any] | None = None,
        probe_factory: Callable[[Any], TestProviderConnection] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._xtb_bridge_url = xtb_bridge_url
        #: Política inyectada (tests o procesos sin BD). ``None`` ⇒ se lee de ``sync_settings``.
        self._policy = policy
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tick = max(1.0, float(tick_seconds))
        self._sleep = sleep or asyncio.sleep
        self._probe_factory = probe_factory
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[Any] | None = None
        self._loop_task: asyncio.Task[Any] | None = None

    @property
    def probing(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    async def policy(self) -> ProviderCheckPolicy:
        """Política vigente: la inyectada o la persistida en ``sync_settings``.

        Si la BD no responde se usa el defecto (ON cada 60 s) y se registra el motivo: el
        comprobador no debe quedarse mudo porque una consulta falló.
        """
        if self._policy is not None:
            return self._policy
        try:
            async with self._session_factory() as session:
                record = await SqlAlchemySyncSchedulerRepository(session).get_settings()
            return ProviderCheckPolicy(
                enabled=record.provider_check_enabled,
                interval_seconds=record.provider_check_interval_seconds,
            )
        except Exception:  # noqa: BLE001 — best-effort: el defecto es honesto y conocido
            logger.warning("no se pudo leer la política de comprobación de proveedores", exc_info=True)
            return ProviderCheckPolicy()

    async def last_measured_at(self) -> datetime | None:
        """Medición más reciente entre los proveedores habilitados (persistida)."""
        async with self._session_factory() as session:
            repository = SqlAlchemyMarketProviderSettingsRepository(session)
            resolver = MarketProviderConfigResolver(
                repository, xtb_bridge_url=self._xtb_bridge_url
            )
            configs = await resolver.list_configs(refresh=True)
        measured = [
            parsed
            for parsed in (
                _parse_iso(config.last_check_at)
                for config in configs
                if config.enabled and config.last_check_at
            )
            if parsed is not None
        ]
        return max(measured) if measured else None

    def is_due(self, policy: ProviderCheckPolicy, last: datetime | None) -> bool:
        """¿Toca comprobar? ON y (nunca medido o edad ≥ intervalo configurado)."""
        if not policy.enabled:
            return False
        if last is None:
            return True
        return (self._clock() - last).total_seconds() >= policy.interval_seconds

    def ensure_fresh(self) -> bool:
        """Red de seguridad del GET: programa ``probe_if_due()`` si no hay una en curso.

        No bloquea. ``True`` significa «hay una tarea de comprobación viva»; esa tarea
        puede decidir que no toca (OFF o dato fresco) y terminar sin medir, así que el
        campo ``probing`` de la API es informativo y nunca una promesa de medición.
        """
        if self.probing:
            return True
        try:
            self._task = asyncio.create_task(self.probe_if_due(), name="provider-health-probe")
        except RuntimeError:  # sin loop activo (p. ej. tests síncronos)
            return False
        return True

    async def probe_if_due(
        self, *, force: bool = False
    ) -> dict[str, ProviderProbeResult] | None:
        """Comprueba solo si la política lo permite y el dato venció.

        ``force=True`` es la comprobación manual («Comprobar ahora»): mide aunque la
        automática esté OFF, porque apagar la cadencia no debe impedir un diagnóstico
        puntual del operador.
        """
        async with self._lock:
            policy = await self.policy()
            if not force:
                if not policy.enabled:
                    return None
                if not self.is_due(policy, await self.last_measured_at()):
                    return None
            return await self.probe_now()

    async def probe_now(self) -> dict[str, ProviderProbeResult]:
        """Sondea los proveedores habilitados y persiste ``last_check_*``."""
        results: dict[str, ProviderProbeResult] = {}
        try:
            async with self._session_factory() as session:
                repository = SqlAlchemyMarketProviderSettingsRepository(session)
                resolver = MarketProviderConfigResolver(
                    repository, xtb_bridge_url=self._xtb_bridge_url
                )
                probe = (
                    self._probe_factory(repository)
                    if self._probe_factory is not None
                    else TestProviderConnection(repository, xtb_bridge_url=self._xtb_bridge_url)
                )
                for config in await resolver.list_configs(refresh=True):
                    if not config.enabled:
                        continue
                    try:
                        results[config.id] = await probe.execute(config.id)
                    except Exception:  # noqa: BLE001 — un proveedor no tumba la sonda
                        logger.warning(
                            "provider health probe failed for %s", config.id, exc_info=True
                        )
                await session.commit()
            invalidate_provider_config_cache()
            if results:
                failed = [pid for pid, result in results.items() if not result.ok]
                logger.info(
                    "provider health probe: %d measured, %d failing%s",
                    len(results),
                    len(failed),
                    f" ({', '.join(failed)})" if failed else "",
                )
        except Exception:  # noqa: BLE001 — best-effort: el arranque no se bloquea
            logger.warning("provider health probe skipped", exc_info=True)
        return results

    def start(self) -> None:
        """Arranca el bucle periódico en el proceso API (idempotente)."""
        if self.running:
            return
        try:
            self._loop_task = asyncio.create_task(
                self.run_forever(), name="provider-health-loop"
            )
        except RuntimeError:  # pragma: no cover — sin loop activo no hay bucle que arrancar
            logger.warning("sin event loop: el comprobador de proveedores no arranca")
            self._loop_task = None

    async def run_forever(self) -> None:
        """Late cada ``tick_seconds`` y comprueba cuando el dato persistido vence."""
        logger.info(
            "Comprobador de proveedores iniciado (tick %.0f s; cadencia en sync_settings)",
            self._tick,
        )
        while True:
            try:
                await self.probe_if_due()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — un tick fallido no mata el bucle
                logger.warning("comprobación periódica de proveedores falló", exc_info=True)
            await self._sleep(self._tick)

    async def aclose(self) -> None:
        """Cancela el bucle y una sonda en vuelo al apagar la API (sin tareas huérfanas)."""
        tasks = [task for task in (self._loop_task, self._task) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._loop_task = None
        self._task = None

