"""FIE F2.2 — Umbrales de gate normalizados por sector (`fund_sector_bands_v1`).

Catálogo alineado con `packages/shared/src/fundamentals-sector-bands.ts`.
"""

from __future__ import annotations

from typing import Any

FUND_SECTOR_BANDS_VERSION = "fund_sector_bands_v1"

BANDED_METRICS = frozenset(
    {
        "trailingPe",
        "roe",
        "debtToEquity",
        "currentRatio",
        "altmanZ",
        "fcfYield",
        "operatingMargin",
    }
)

# rule: {"operator": "lte"|"gte", "value": float} | "skip"
SectorBandRule = dict[str, Any] | str

SECTOR_BAND_DEFAULT: dict[str, SectorBandRule] = {
    "trailingPe": {"operator": "lte", "value": 25.0},
    "roe": {"operator": "gte", "value": 0.1},
    "debtToEquity": {"operator": "lte", "value": 1.5},
    "currentRatio": {"operator": "gte", "value": 1.0},
    "altmanZ": {"operator": "gte", "value": 1.8},
    "fcfYield": {"operator": "gte", "value": 0.02},
    "operatingMargin": {"operator": "gte", "value": 0.08},
}

SECTOR_BAND_OVERLAYS: dict[str, dict[str, SectorBandRule]] = {
    "Technology": {
        "trailingPe": {"operator": "lte", "value": 40.0},
        "roe": {"operator": "gte", "value": 0.12},
        "debtToEquity": {"operator": "lte", "value": 1.2},
        "operatingMargin": {"operator": "gte", "value": 0.12},
    },
    "Communication Services": {
        "trailingPe": {"operator": "lte", "value": 30.0},
        "roe": {"operator": "gte", "value": 0.1},
        "debtToEquity": {"operator": "lte", "value": 1.8},
    },
    "Healthcare": {
        "trailingPe": {"operator": "lte", "value": 35.0},
        "roe": {"operator": "gte", "value": 0.1},
        "operatingMargin": {"operator": "gte", "value": 0.1},
    },
    "Consumer Cyclical": {
        "trailingPe": {"operator": "lte", "value": 28.0},
        "debtToEquity": {"operator": "lte", "value": 1.8},
        "currentRatio": {"operator": "gte", "value": 1.1},
    },
    "Consumer Defensive": {
        "trailingPe": {"operator": "lte", "value": 22.0},
        "roe": {"operator": "gte", "value": 0.12},
        "debtToEquity": {"operator": "lte", "value": 1.2},
    },
    "Industrials": {
        "trailingPe": {"operator": "lte", "value": 22.0},
        "debtToEquity": {"operator": "lte", "value": 1.4},
        "altmanZ": {"operator": "gte", "value": 2.0},
    },
    "Energy": {
        "trailingPe": {"operator": "lte", "value": 18.0},
        "roe": {"operator": "gte", "value": 0.08},
        "debtToEquity": {"operator": "lte", "value": 1.2},
        "fcfYield": {"operator": "gte", "value": 0.04},
    },
    "Basic Materials": {
        "trailingPe": {"operator": "lte", "value": 18.0},
        "roe": {"operator": "gte", "value": 0.08},
        "debtToEquity": {"operator": "lte", "value": 1.0},
    },
    "Utilities": {
        "trailingPe": {"operator": "lte", "value": 20.0},
        "roe": {"operator": "gte", "value": 0.08},
        "debtToEquity": {"operator": "lte", "value": 2.5},
        "currentRatio": {"operator": "gte", "value": 0.8},
        "altmanZ": {"operator": "gte", "value": 1.2},
        "fcfYield": {"operator": "gte", "value": 0.03},
    },
    "Financial Services": {
        "trailingPe": {"operator": "lte", "value": 15.0},
        "roe": {"operator": "gte", "value": 0.08},
        "debtToEquity": "skip",
        "currentRatio": "skip",
        "altmanZ": "skip",
        "fcfYield": "skip",
        "operatingMargin": {"operator": "gte", "value": 0.15},
    },
    "Real Estate": {
        "trailingPe": {"operator": "lte", "value": 25.0},
        "roe": {"operator": "gte", "value": 0.06},
        "debtToEquity": {"operator": "lte", "value": 2.5},
        "altmanZ": "skip",
        "fcfYield": {"operator": "gte", "value": 0.03},
    },
}

_OVERLAY_BY_LOWER = {k.lower(): v for k, v in SECTOR_BAND_OVERLAYS.items()}


def resolve_sector_band_profile(
    sector: str | None,
) -> tuple[bool, dict[str, SectorBandRule], str | None]:
    """Return (known, merged_profile, sector_key)."""
    if not isinstance(sector, str) or not sector.strip():
        return False, dict(SECTOR_BAND_DEFAULT), None
    overlay = _OVERLAY_BY_LOWER.get(sector.strip().lower())
    if overlay is None:
        return False, dict(SECTOR_BAND_DEFAULT), None
    merged = {**SECTOR_BAND_DEFAULT, **overlay}
    return True, merged, sector.strip()


def apply_sector_bands_to_conditions(
    conditions: list[dict[str, Any]],
    *,
    sector: str | None,
    sector_bands_version: str | None,
) -> list[dict[str, Any]]:
    """
    Si version == fund_sector_bands_v1 y el sector es conocido:
    - sustituye operator/value de métricas banded
    - omite condiciones con rule 'skip'
    Sector desconocido → condiciones intactas (fallback UI).
    """
    if sector_bands_version != FUND_SECTOR_BANDS_VERSION:
        return conditions
    known, profile, _ = resolve_sector_band_profile(sector)
    if not known:
        return conditions

    out: list[dict[str, Any]] = []
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        metric = str(cond.get("metric") or "")
        if metric not in BANDED_METRICS:
            out.append(cond)
            continue
        rule = profile.get(metric)
        if rule is None:
            out.append(cond)
            continue
        if rule == "skip":
            continue
        if not isinstance(rule, dict):
            out.append(cond)
            continue
        out.append(
            {
                **cond,
                "operator": rule["operator"],
                "value": float(rule["value"]),
                "sectorBand": True,
            }
        )
    return out


def default_sector_band_conditions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for metric, rule in SECTOR_BAND_DEFAULT.items():
        if rule == "skip" or not isinstance(rule, dict):
            continue
        out.append(
            {
                "metric": metric,
                "operator": rule["operator"],
                "value": float(rule["value"]),
            }
        )
    return out
