"""Inputs macro para Market State Engine (RFC-008 D6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MacroInputs:
    """
    Snapshot de régimen de mercado (no por instrumento).

    Fuentes típicas: VIX, curva US 10y–2y, crédito HY OAS, amplitud.
    Todos opcionales; cobertura baja → régimen uncertain.
    """

    vix: float | None = None
    vix_percentile: float | None = None  # 0–100
    yield_curve_10y2y_bps: float | None = None  # negativo = invertida
    credit_spread_oas_bps: float | None = None
    usd_dxy_change_5d_pct: float | None = None
    breadth_pct_above_ma50: float | None = None  # 0–100
    fetched_at: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> MacroInputs:
        if not data:
            return MacroInputs()

        def g(*keys: str) -> float | None:
            for k in keys:
                if k in data and data[k] is not None:
                    try:
                        return float(data[k])
                    except (TypeError, ValueError):
                        return None
            return None

        fetched = data.get("fetchedAt") or data.get("fetched_at")
        return MacroInputs(
            vix=g("vix", "VIX"),
            vix_percentile=g("vixPercentile", "vix_percentile"),
            yield_curve_10y2y_bps=g(
                "yieldCurve10y2yBps",
                "yield_curve_10y2y_bps",
                "us10y2yBps",
            ),
            credit_spread_oas_bps=g(
                "creditSpreadOasBps",
                "credit_spread_oas_bps",
                "hyOasBps",
            ),
            usd_dxy_change_5d_pct=g(
                "usdDxyChange5dPct",
                "usd_dxy_change_5d_pct",
            ),
            breadth_pct_above_ma50=g(
                "breadthPctAboveMa50",
                "breadth_pct_above_ma50",
            ),
            fetched_at=str(fetched) if fetched else None,
        )
