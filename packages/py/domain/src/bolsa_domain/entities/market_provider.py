"""Registro y configuración de proveedores de datos financieros.

Fuente ÚNICA de verdad para backend, UI, pruebas y Ayuda: qué proveedores existen, qué
capacidades cubre cada uno y qué campos son configurables. La configuración efectiva vive
en ``market_provider_settings``; este módulo solo declara los valores por defecto y las
reglas de validación (puras, sin I/O).

Doctrina de honestidad: un proveedor **no** se declara disponible porque exista en el
registro. ``healthy`` solo es ``True`` cuando hay una verificación registrada y correcta
(``last_check_ok``); sin verificación el estado es «sin verificar», nunca «disponible».
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

PROVIDER_YAHOO = "yahoo"
PROVIDER_XTB = "xtb"

CAPABILITY_OHLCV = "ohlcv"
CAPABILITY_LIVE_QUOTE = "live_quote"
CAPABILITY_FUNDAMENTALS = "fundamentals"
CAPABILITY_FX = "fx"

PROVIDER_CAPABILITIES: tuple[str, ...] = (
    CAPABILITY_OHLCV,
    CAPABILITY_LIVE_QUOTE,
    CAPABILITY_FUNDAMENTALS,
    CAPABILITY_FX,
)

#: Rango aceptado para ``priority`` (menor = se intenta primero).
MIN_PRIORITY = 0
MAX_PRIORITY = 100
#: Rango aceptado para el intervalo mínimo entre peticiones (segundos).
MIN_INTERVAL_SECONDS_FLOOR = 0
MIN_INTERVAL_SECONDS_CEILING = 120

#: Política de la comprobación periódica de proveedores (tabla ``sync_settings``, 060).
#: Es una automatización DISTINTA de la sincronización de velas: aquí solo se mide
#: conectividad, no se descarga histórico. Los límites viven en el dominio para que la
#: BD (``CHECK``), el caso de uso y la UI publiquen el mismo rango.
MIN_PROVIDER_CHECK_INTERVAL_SECONDS = 15
MAX_PROVIDER_CHECK_INTERVAL_SECONDS = 3600
DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS = 60
#: Con la comprobación automática ON, una medición más vieja que ``intervalo × esto``
#: significa que el bucle no está corriendo: el veredicto pasa a ``stale`` (ámbar), no a
#: verde ni a rojo. Nunca se presenta como sana una medición que ya no se refresca.
PROVIDER_HEALTH_STALE_GRACE_FACTOR = 2.0


@dataclass(frozen=True, slots=True)
class ProviderCheckPolicy:
    """Cuándo se comprueban los proveedores, y si se comprueban solos."""

    enabled: bool = True
    interval_seconds: int = DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(
            self,
            "interval_seconds",
            normalize_provider_check_interval(self.interval_seconds),
        )

    @property
    def stale_after_seconds(self) -> float:
        return self.interval_seconds * PROVIDER_HEALTH_STALE_GRACE_FACTOR


def normalize_provider_check_interval(value: int | str | None) -> int:
    """Intervalo válido del contrato; un valor ausente o ilegible cae al defecto.

    Un valor fuera de rango se ACOTA (la UI valida antes; esto es la última defensa de
    los caminos que no pasan por la UI, nunca un valor que el bucle no sepa interpretar).
    """
    try:
        raw = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_PROVIDER_CHECK_INTERVAL_SECONDS
    return min(
        max(raw, MIN_PROVIDER_CHECK_INTERVAL_SECONDS),
        MAX_PROVIDER_CHECK_INTERVAL_SECONDS,
    )


@dataclass(frozen=True, slots=True)
class MarketProviderSpec:
    """Declaración estática de un proveedor (no configurable en runtime)."""

    id: str
    label: str
    capabilities: tuple[str, ...]
    configurable_base_url: bool
    configurable_throttle: bool
    default_enabled: bool
    default_priority: int
    default_min_interval_seconds: int
    description: str


MARKET_PROVIDER_SPECS: tuple[MarketProviderSpec, ...] = (
    MarketProviderSpec(
        id=PROVIDER_YAHOO,
        label="Yahoo Finance",
        capabilities=(CAPABILITY_OHLCV, CAPABILITY_FUNDAMENTALS, CAPABILITY_FX),
        configurable_base_url=False,
        configurable_throttle=True,
        default_enabled=True,
        default_priority=10,
        # Espejo del defecto de ``YAHOO_MIN_INTERVAL_SEC``: el throttle real vive en el
        # cliente HTTP y aquí solo se publica el valor con el que se configura.
        default_min_interval_seconds=2,
        description="Histórico diario, fundamentales y tipos de cambio.",
    ),
    MarketProviderSpec(
        id=PROVIDER_XTB,
        label="XTB Bridge",
        capabilities=(CAPABILITY_LIVE_QUOTE,),
        configurable_base_url=True,
        configurable_throttle=True,
        default_enabled=True,
        default_priority=20,
        default_min_interval_seconds=0,
        description="Cotización en vivo vía bridge HTTP local (opcional).",
    ),
)

_PROVIDER_BY_ID: dict[str, MarketProviderSpec] = {spec.id: spec for spec in MARKET_PROVIDER_SPECS}


def provider_spec(provider_id: str) -> MarketProviderSpec | None:
    """Especificación del proveedor o ``None`` si el ID no existe en el registro."""
    return _PROVIDER_BY_ID.get(str(provider_id or "").strip().lower())


def provider_ids() -> tuple[str, ...]:
    return tuple(spec.id for spec in MARKET_PROVIDER_SPECS)


@dataclass(frozen=True, slots=True)
class MarketProviderConfig:
    """Configuración efectiva de un proveedor (registro + fila persistida)."""

    id: str
    label: str
    enabled: bool
    priority: int
    min_interval_seconds: int
    base_url: str | None
    capabilities: tuple[str, ...]
    description: str = ""
    base_url_source: str | None = None
    last_check_at: str | None = None
    last_check_ok: bool | None = None
    last_check_message: str | None = None
    updated_at: str | None = None

    @property
    def verified(self) -> bool:
        """``True`` solo si existe una verificación registrada (con o sin éxito)."""
        return self.last_check_at is not None

    @property
    def healthy(self) -> bool:
        """``True`` solo con verificación correcta: nunca se afirma sin medir."""
        return self.last_check_ok is True

    @property
    def missing_configuration(self) -> bool:
        """Habilitado pero sin el dato imprescindible (URL del bridge)."""
        return bool(self.enabled and self.requires_base_url and not self.base_url)

    @property
    def requires_base_url(self) -> bool:
        return self.id == PROVIDER_XTB

    @property
    def usable(self) -> bool:
        """Puede usarse de verdad (habilitado y con su configuración mínima)."""
        return bool(self.enabled) and not self.missing_configuration

    @property
    def status_message(self) -> str:
        if not self.enabled:
            return "Deshabilitado en Configuración"
        if self.missing_configuration:
            return "Habilitado pero sin URL de bridge configurada"
        if not self.verified:
            return "Sin verificar (usa «Probar conexión»)"
        if self.last_check_ok is True:
            return self.last_check_message or "Verificado correctamente"
        return self.last_check_message or "La última verificación falló"

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


class ProviderConfigError(ValueError):
    """Valor de configuración inválido (se traduce a 422 en la API)."""


def normalize_priority(value: int | None) -> int | None:
    if value is None:
        return None
    priority = int(value)
    if priority < MIN_PRIORITY or priority > MAX_PRIORITY:
        raise ProviderConfigError(
            f"priority fuera de rango [{MIN_PRIORITY}, {MAX_PRIORITY}]: {priority}"
        )
    return priority


def normalize_min_interval_seconds(value: int | None) -> int | None:
    if value is None:
        return None
    seconds = int(value)
    if seconds < MIN_INTERVAL_SECONDS_FLOOR or seconds > MIN_INTERVAL_SECONDS_CEILING:
        raise ProviderConfigError(
            "minIntervalSeconds fuera de rango "
            f"[{MIN_INTERVAL_SECONDS_FLOOR}, {MIN_INTERVAL_SECONDS_CEILING}]: {seconds}"
        )
    return seconds


def normalize_base_url(value: str | None) -> str | None:
    """Valida y normaliza una URL de bridge.

    Cadena vacía o ``None`` significa «sin URL» (proveedor no configurado), no un error.
    Solo se aceptan ``http`` y ``https``: el cliente hace peticiones directas.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ProviderConfigError(f"baseUrl inválida (se espera http(s)://host[:puerto]): {raw}")
    return raw.rstrip("/")


def capability_provider_candidates(
    configs: list[MarketProviderConfig], capability: str
) -> list[MarketProviderConfig]:
    """Proveedores HABILITADOS que cubren la capacidad, ordenados por prioridad.

    El orden es estable: ``priority`` ascendente y, a igualdad, el orden del registro.
    """
    order = {spec.id: index for index, spec in enumerate(MARKET_PROVIDER_SPECS)}
    return sorted(
        (cfg for cfg in configs if cfg.usable and cfg.supports(capability)),
        key=lambda cfg: (cfg.priority, order.get(cfg.id, len(order))),
    )
