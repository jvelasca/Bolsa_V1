"""Evaluación de gate fundamental (P12 / FIE F2.0–F2.3).

Evalúa condiciones del snapshot (incl. Piotroski, dcfUpside, grahamUpside)
y aplica bandas sectoriales si `sectorBandsVersion` está presente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.signals.sector_bands import (
    FUND_SECTOR_BANDS_VERSION,
    apply_sector_bands_to_conditions,
    default_sector_band_conditions,
)

# Snapshot v3 fields evaluables en scan (incluye Piotroski F2.1).
ALLOWED_METRICS = frozenset(
    {
        "marketCap",
        "trailingPe",
        "forwardPe",
        "roe",
        "debtToEquity",
        "currentRatio",
        "altmanZ",
        "fcfYield",
        "operatingMargin",
        "revenueGrowth",
        "piotroski",
        "dcfUpside",
        "grahamUpside",
        "roic",
        "beneishM",
    }
)
OPERATORS = {
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
    "eq": lambda left, right: left == right,
}


def build_fundamental_gate(
    *,
    max_trailing_pe: float | None = None,
    min_market_cap_millions: float | None = None,
    min_roe: float | None = None,
    max_debt_to_equity: float | None = None,
    min_current_ratio: float | None = None,
    min_altman_z: float | None = None,
    min_fcf_yield: float | None = None,
    min_operating_margin: float | None = None,
    min_revenue_growth: float | None = None,
    min_piotroski: float | None = None,
    min_dcf_upside: float | None = None,
    min_graham_upside: float | None = None,
    min_roic: float | None = None,
    max_beneish_m: float | None = None,
    sectors: list[str] | None = None,
    max_age_days: int = 30,
    operator: str = "all",
    use_sector_bands: bool = False,
) -> dict[str, Any] | None:
    """Construye ``fundamental_gate``."""
    conditions: list[dict[str, Any]] = []
    if max_trailing_pe is not None and max_trailing_pe > 0:
        conditions.append(
            {"metric": "trailingPe", "operator": "lte", "value": float(max_trailing_pe)}
        )
    if min_market_cap_millions is not None and min_market_cap_millions > 0:
        conditions.append(
            {
                "metric": "marketCap",
                "operator": "gte",
                "value": float(min_market_cap_millions) * 1_000_000,
            }
        )
    if min_roe is not None:
        conditions.append({"metric": "roe", "operator": "gte", "value": float(min_roe)})
    if max_debt_to_equity is not None:
        conditions.append(
            {"metric": "debtToEquity", "operator": "lte", "value": float(max_debt_to_equity)}
        )
    if min_current_ratio is not None:
        conditions.append(
            {"metric": "currentRatio", "operator": "gte", "value": float(min_current_ratio)}
        )
    if min_altman_z is not None:
        conditions.append({"metric": "altmanZ", "operator": "gte", "value": float(min_altman_z)})
    if min_fcf_yield is not None:
        conditions.append({"metric": "fcfYield", "operator": "gte", "value": float(min_fcf_yield)})
    if min_operating_margin is not None:
        conditions.append(
            {"metric": "operatingMargin", "operator": "gte", "value": float(min_operating_margin)}
        )
    if min_revenue_growth is not None:
        conditions.append(
            {"metric": "revenueGrowth", "operator": "gte", "value": float(min_revenue_growth)}
        )
    if min_piotroski is not None and min_piotroski >= 0:
        conditions.append(
            {"metric": "piotroski", "operator": "gte", "value": float(min_piotroski)}
        )
    if min_dcf_upside is not None:
        conditions.append(
            {"metric": "dcfUpside", "operator": "gte", "value": float(min_dcf_upside)}
        )
    if min_graham_upside is not None:
        conditions.append(
            {"metric": "grahamUpside", "operator": "gte", "value": float(min_graham_upside)}
        )
    if min_roic is not None:
        conditions.append({"metric": "roic", "operator": "gte", "value": float(min_roic)})
    if max_beneish_m is not None:
        conditions.append(
            {"metric": "beneishM", "operator": "lte", "value": float(max_beneish_m)}
        )

    if use_sector_bands:
        present = {str(c.get("metric")) for c in conditions}
        for seed in default_sector_band_conditions():
            metric = str(seed["metric"])
            if metric not in present:
                conditions.append(seed)
                present.add(metric)

    if not conditions and not sectors and not use_sector_bands:
        return None
    gate: dict[str, Any] = {
        "operator": operator if operator in ("all", "any") else "all",
        "conditions": conditions,
        "maxAgeDays": max_age_days,
    }
    if sectors:
        gate["sectors"] = sectors
    if use_sector_bands:
        gate["sectorBandsVersion"] = FUND_SECTOR_BANDS_VERSION
    return gate


def _fundamental_gate(definition: dict[str, Any]) -> dict[str, Any] | None:
    hybrid = definition.get("hybrid")
    if isinstance(hybrid, dict):
        gate = hybrid.get("fundamentalGate")
        if isinstance(gate, dict):
            return gate
    return definition.get("fundamentalGate") if isinstance(definition.get("fundamentalGate"), dict) else None


def definition_has_fundamental_gate(definition: dict[str, Any]) -> bool:
    """Función pública ``definition_has_fundamental_gate``."""
    gate = _fundamental_gate(definition)
    if gate is None:
        return False
    return bool(gate.get("conditions")) or bool(gate.get("sectors")) or bool(
        gate.get("sectorBandsVersion")
    )


def fundamental_gate_max_age_days(definition: dict[str, Any]) -> int:
    """Función pública ``fundamental_gate_max_age_days``."""
    gate = _fundamental_gate(definition)
    if gate is None:
        return 30
    return int(gate.get("maxAgeDays") or 30)


def fundamentals_need_refresh(
    fundamentals: dict[str, Any] | None,
    max_age_days: int,
) -> bool:
    """Caducidad por edad (scans / gates). Thin v2 se evalúa aparte."""
    if fundamentals is None:
        return True
    return _is_stale(fundamentals, max_age_days)


def fundamentals_thin_for_cognitive(fundamentals: dict[str, Any] | None) -> bool:
    """True si falta calidad/solvencia v2 (solo PE/mcap o sin ratios)."""
    if fundamentals is None:
        return True
    return not any(
        fundamentals.get(k) is not None
        for k in ("roe", "operatingMargin", "debtToEquity", "currentRatio", "revenueGrowth")
    )


def _metric_value(fundamentals: dict[str, Any], metric: str) -> float | None:
    value = fundamentals.get(metric)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _is_stale(fundamentals: dict[str, Any], max_age_days: int) -> bool:
    fetched_at = fundamentals.get("fetchedAt")
    if not isinstance(fetched_at, str):
        return True
    try:
        fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    age = datetime.now(UTC) - fetched.astimezone(UTC)
    return age.days > max_age_days


def evaluate_fundamental_condition(
    condition: dict[str, Any],
    *,
    fundamentals: dict[str, Any],
) -> bool:
    """Evalúa ``fundamental_condition``."""
    metric = str(condition.get("metric") or "")
    if metric not in ALLOWED_METRICS:
        return False
    operator = str(condition.get("operator") or "")
    compare_fn = OPERATORS.get(operator)
    if compare_fn is None:
        return False
    left = _metric_value(fundamentals, metric)
    right = condition.get("value")
    if left is None or not isinstance(right, (int, float)):
        return False
    return compare_fn(left, float(right))


def passes_fundamental_gate(
    definition: dict[str, Any],
    fundamentals: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """Función pública ``passes_fundamental_gate``."""
    gate = _fundamental_gate(definition)
    if gate is None:
        return True, None

    if fundamentals is None:
        return False, "Sin datos fundamentales — sincroniza el instrumento"

    max_age_days = int(gate.get("maxAgeDays") or 30)
    if _is_stale(fundamentals, max_age_days):
        return False, f"Fundamentales obsoletos (>{max_age_days} días)"

    sectors = gate.get("sectors") or []
    if sectors:
        sector = fundamentals.get("sector")
        if not isinstance(sector, str) or sector not in sectors:
            return False, f"Sector {sector!r} no permitido"

    raw_conditions = [c for c in (gate.get("conditions") or []) if isinstance(c, dict)]
    sector_raw = fundamentals.get("sector")
    sector = sector_raw if isinstance(sector_raw, str) else None
    conditions = apply_sector_bands_to_conditions(
        raw_conditions,
        sector=sector,
        sector_bands_version=gate.get("sectorBandsVersion"),
    )
    if not conditions:
        return True, None

    operator = str(gate.get("operator") or "all")
    results = [
        evaluate_fundamental_condition(condition, fundamentals=fundamentals)
        for condition in conditions
    ]
    if not results:
        return True, None

    passed = all(results) if operator == "all" else any(results)
    if passed:
        return True, None
    return False, "No cumple filtro fundamental"
