"""TradeContext — contexto de decisión con estado explícito (AUTO 2.0 · V2.40.1 P0).

Cierra el agujero *fail-open* detectado en la auditoría de ``v2.40-beta``: los gates de
cartera (sector, correlación, liquidez) trataban la **ausencia de dato** como "sin
problema" (``None`` ⇒ no veta) y el motor podía abrir una posición sobre estado opaco.

Aquí la ausencia de dato deja de ser un booleano implícito y pasa a ser un **estado
explícito** que el motor puede vetar:

* ``SectorResolutionStatus`` — ``KNOWN`` / ``UNKNOWN`` / ``CONFLICTING`` / ``STALE``.
* ``LiquidityStatus``        — ``KNOWN`` / ``UNKNOWN`` / ``STALE``.
* ``CorrelationStatus``      — ``CALCULATED`` / ``STALE`` / ``UNAVAILABLE`` / ``CONFLICTING``.

Regla única (fail-closed): **solo** ``KNOWN`` (sector/liquidez) y ``CALCULATED``
(correlación) permiten entrada. Cualquier otro estado es un veto con motivo auditable;
no se asume "exento" ni "sin exposición".

``CONFLICTING`` (sector) es la discrepancia entre lo que declara la estrategia y lo que
dice el catálogo de instrumentos: no se elige una fuente "ganadora", se declara el
conflicto y se veta (ninguna de las dos es verificable por sí sola).

``STALE`` es antigüedad verificable: solo se afirma cuando el ``observed_at`` del dato y
el ``as_of`` de la decisión son parseables y la edad supera ``max_age_days``. Sin
``max_age_days`` (> 0) la frescura no está bajo política y solo se evalúa la presencia.

Función pura, determinista y sin I/O (contrato ``analytics-market-independence``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

SectorResolutionStatus = Literal["KNOWN", "UNKNOWN", "CONFLICTING", "STALE"]
LiquidityStatus = Literal["KNOWN", "UNKNOWN", "STALE"]
CorrelationStatus = Literal["CALCULATED", "STALE", "UNAVAILABLE", "CONFLICTING"]

SECTOR_KNOWN: SectorResolutionStatus = "KNOWN"
SECTOR_UNKNOWN: SectorResolutionStatus = "UNKNOWN"
SECTOR_CONFLICTING: SectorResolutionStatus = "CONFLICTING"
SECTOR_STALE: SectorResolutionStatus = "STALE"

LIQUIDITY_KNOWN: LiquidityStatus = "KNOWN"
LIQUIDITY_UNKNOWN: LiquidityStatus = "UNKNOWN"
LIQUIDITY_STALE: LiquidityStatus = "STALE"

CORRELATION_CALCULATED: CorrelationStatus = "CALCULATED"
CORRELATION_STALE: CorrelationStatus = "STALE"
CORRELATION_UNAVAILABLE: CorrelationStatus = "UNAVAILABLE"
CORRELATION_CONFLICTING: CorrelationStatus = "CONFLICTING"

# Sentinel de sector no resoluble: se comparte con ``portfolio_fit``/``auto_portfolio_snapshot``
# para que "sin sector" signifique lo mismo en todo el pipeline.
UNKNOWN_SECTOR_VALUE = "<unknown>"

DEFAULT_MAX_AGE_DAYS = 30


def normalize_sector(value: Any) -> str | None:
    """Sector normalizado (trim + casefold) o ``None`` si vacío/no textual.

    La normalización permite comparar lo declarado por la estrategia con el catálogo
    sin que un cambio de mayúsculas o de espacios se lea como un conflicto real.
    """
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    folded = cleaned.casefold()
    if folded == UNKNOWN_SECTOR_VALUE:
        return None
    return folded


def _parse_moment(value: Any) -> datetime | None:
    """Instante UTC parseable desde ISO-8601 (``Z`` incluido) o ``None``."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def is_stale(
    *,
    observed_at: Any,
    as_of: Any,
    max_age_days: int,
) -> bool:
    """True solo si la antigüedad es **verificable** y supera ``max_age_days``.

    Sin política de frescura (``max_age_days <= 0``) o sin instantes parseables no se
    puede afirmar antigüedad, así que no se declara ``STALE`` (no se inventa un
    problema): la presencia del dato la evalúa quien lo resuelve.
    """
    if max_age_days <= 0:
        return False
    observed = _parse_moment(observed_at)
    moment = _parse_moment(as_of)
    if observed is None or moment is None:
        return False
    age_seconds = (moment - observed).total_seconds()
    # Un dato del futuro no es un dato viejo (reloj desplazado): no se afirma staleness.
    if age_seconds <= 0:
        return False
    return age_seconds > max_age_days * 86400


@dataclass(frozen=True, slots=True)
class TradeContext:
    """Estado explícito de los gates de cartera para UNA oportunidad."""

    sector: str | None = None
    sector_status: SectorResolutionStatus = SECTOR_UNKNOWN
    liquidity_notional: float | None = None
    liquidity_status: LiquidityStatus = LIQUIDITY_UNKNOWN
    correlation: float | None = None
    correlation_status: CorrelationStatus = CORRELATION_UNAVAILABLE

    @property
    def sector_is_known(self) -> bool:
        return self.sector_status == SECTOR_KNOWN

    @property
    def liquidity_is_known(self) -> bool:
        return self.liquidity_status == LIQUIDITY_KNOWN

    @property
    def correlation_is_calculated(self) -> bool:
        return self.correlation_status == CORRELATION_CALCULATED

    @classmethod
    def from_legacy(
        cls,
        *,
        sector: Any = None,
        liquidity_notional: Any = None,
        correlation: Any = None,
    ) -> TradeContext:
        """Contexto desde valores sueltos: presente ⇒ ``KNOWN``/``CALCULATED``.

        Es el puente para los llamantes que ya tienen el valor resuelto (no la
        observación cruda con su instante). ``None`` ⇒ ``UNKNOWN``/``UNAVAILABLE``,
        nunca "exento".
        """
        sector_value = sector if isinstance(sector, str) and sector.strip() else None
        liquidity = _finite_positive(liquidity_notional, allow_zero=True)
        correlation_value = _finite(correlation)
        return cls(
            sector=sector_value.strip() if sector_value else None,
            sector_status=SECTOR_KNOWN if sector_value else SECTOR_UNKNOWN,
            liquidity_notional=liquidity,
            liquidity_status=LIQUIDITY_KNOWN if liquidity is not None else LIQUIDITY_UNKNOWN,
            correlation=correlation_value,
            correlation_status=(
                CORRELATION_CALCULATED
                if correlation_value is not None
                else CORRELATION_UNAVAILABLE
            ),
        )

    @classmethod
    def from_observation(
        cls,
        *,
        sector_declared: Any = None,
        sector_catalog: Any = None,
        adv_usd: Any = None,
        correlation: Any = None,
        correlation_status: CorrelationStatus | None = None,
        observed_at: Any = None,
        as_of: Any = None,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> TradeContext:
        """Contexto desde la observación cruda, resolviendo el estado de cada gate.

        * Sector: ``CONFLICTING`` si lo declarado y el catálogo discrepan; si no, el
          valor disponible; ``STALE`` si su antigüedad es verificable y excesiva.
        * Liquidez: ``STALE`` cuando el dato es viejo; ``UNKNOWN`` cuando no hay ADV.
        * Correlación: el estado lo aporta el llamante (``CALCULATED`` por defecto si
          hay número); sin número ⇒ ``UNAVAILABLE``.
        """
        declared = normalize_sector(sector_declared)
        catalog = normalize_sector(sector_catalog)

        if declared is not None and catalog is not None and declared != catalog:
            sector_value: str | None = None
            sector_status: SectorResolutionStatus = SECTOR_CONFLICTING
        else:
            raw_sector = sector_catalog if sector_catalog is not None else sector_declared
            sector_value = (
                raw_sector.strip()
                if isinstance(raw_sector, str) and raw_sector.strip()
                else None
            )
            if sector_value is None:
                sector_status = SECTOR_UNKNOWN
            elif is_stale(observed_at=observed_at, as_of=as_of, max_age_days=max_age_days):
                sector_status = SECTOR_STALE
            else:
                sector_status = SECTOR_KNOWN

        liquidity = _finite_positive(adv_usd, allow_zero=True)
        if liquidity is None:
            liquidity_status: LiquidityStatus = LIQUIDITY_UNKNOWN
        elif is_stale(observed_at=observed_at, as_of=as_of, max_age_days=max_age_days):
            liquidity_status = LIQUIDITY_STALE
        else:
            liquidity_status = LIQUIDITY_KNOWN

        correlation_value = _finite(correlation)
        if correlation_value is None:
            resolved_correlation_status: CorrelationStatus = CORRELATION_UNAVAILABLE
        elif correlation_status is not None:
            resolved_correlation_status = correlation_status
        else:
            resolved_correlation_status = CORRELATION_CALCULATED

        return cls(
            sector=sector_value,
            sector_status=sector_status,
            liquidity_notional=liquidity,
            liquidity_status=liquidity_status,
            correlation=correlation_value,
            correlation_status=resolved_correlation_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "sectorStatus": self.sector_status,
            "liquidityNotional": self.liquidity_notional,
            "liquidityStatus": self.liquidity_status,
            "correlation": self.correlation,
            "correlationStatus": self.correlation_status,
        }


def _finite(value: Any) -> float | None:
    """Float finito o ``None`` (NaN/inf/no numérico ⇒ ausente)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _finite_positive(value: Any, *, allow_zero: bool = False) -> float | None:
    """Float finito; con ``allow_zero`` el 0 es un valor legítimo (liquidez nula).

    Un ``0`` de liquidez es información (no hay capacidad), no ausencia de dato: el
    motor lo veta por ``liquidity_insufficient``, no por ``liquidity_unknown``.
    """
    number = _finite(value)
    if number is None:
        return None
    if number < 0:
        return None
    if number == 0 and not allow_zero:
        return None
    return number


__all__ = [
    "CORRELATION_CALCULATED",
    "CORRELATION_CONFLICTING",
    "CORRELATION_STALE",
    "CORRELATION_UNAVAILABLE",
    "CorrelationStatus",
    "DEFAULT_MAX_AGE_DAYS",
    "LIQUIDITY_KNOWN",
    "LIQUIDITY_STALE",
    "LIQUIDITY_UNKNOWN",
    "LiquidityStatus",
    "SECTOR_CONFLICTING",
    "SECTOR_KNOWN",
    "SECTOR_STALE",
    "SECTOR_UNKNOWN",
    "SectorResolutionStatus",
    "TradeContext",
    "UNKNOWN_SECTOR_VALUE",
    "is_stale",
    "normalize_sector",
]
