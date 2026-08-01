"""FIE F2.4 — WACC proxy por sector Yahoo (`fund_wacc_sector_v1`).

No es CAPM completo: tasas ilustrativas versionadas para el DCF.
Cambiar tasas ⇒ bump ``FUND_WACC_VERSION`` (+ method DCF si aplica).
"""

from __future__ import annotations

FUND_WACC_VERSION = "fund_wacc_sector_v1"
WACC_SECTOR_DEFAULT = 0.10

# Overlays Yahoo summaryProfile.sector (case-insensitive)
WACC_SECTOR_OVERLAYS: dict[str, float] = {
    "Technology": 0.095,
    "Communication Services": 0.085,
    "Healthcare": 0.085,
    "Consumer Cyclical": 0.10,
    "Consumer Defensive": 0.075,
    "Industrials": 0.09,
    "Energy": 0.105,
    "Basic Materials": 0.095,
    "Utilities": 0.065,
    "Financial Services": 0.10,
    "Real Estate": 0.075,
}

_OVERLAY_BY_LOWER = {k.lower(): v for k, v in WACC_SECTOR_OVERLAYS.items()}


def resolve_sector_wacc(sector: str | None) -> tuple[bool, float, str | None, str]:
    """
    Returns ``(known, wacc, sector_key, wacc_method)``.

    Sector desconocido / vacío → default 10% (compat F2.3).
    """
    if not isinstance(sector, str) or not sector.strip():
        return False, WACC_SECTOR_DEFAULT, None, FUND_WACC_VERSION
    key = sector.strip()
    rate = _OVERLAY_BY_LOWER.get(key.lower())
    if rate is None:
        return False, WACC_SECTOR_DEFAULT, None, FUND_WACC_VERSION
    return True, float(rate), key, FUND_WACC_VERSION
