"""Inputs fundamentales para Knowledge Layer (RFC-008 D5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FundamentalInputs:
    """
    Snapshot fundamental (Yahoo quoteSummary v3 / FIE).

    PE, ROE, márgenes, growth, D/E, currentRatio, Altman Z, FCF yield.
    Piotroski: F2 (series YoY).
    """

    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    sector: str | None = None
    roe: float | None = None
    roic: float | None = None
    operating_margin: float | None = None
    revenue_growth: float | None = None
    eps_growth: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    free_cashflow: float | None = None
    fcf_yield: float | None = None
    piotroski: float | None = None
    altman_z: float | None = None
    beneish_m: float | None = None
    fetched_at: str | None = None

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> FundamentalInputs:
        if not data:
            return FundamentalInputs()

        def g(*keys: str) -> float | None:
            for k in keys:
                if k in data and data[k] is not None:
                    try:
                        return float(data[k])
                    except (TypeError, ValueError):
                        return None
            return None

        sector = data.get("sector")
        sector_str = str(sector).strip() if isinstance(sector, str) and sector.strip() else None
        fetched = data.get("fetchedAt") or data.get("fetched_at")
        return FundamentalInputs(
            market_cap=g("marketCap", "market_cap"),
            trailing_pe=g("trailingPe", "trailing_pe"),
            forward_pe=g("forwardPe", "forward_pe"),
            sector=sector_str,
            roe=g("roe", "returnOnEquity"),
            roic=g("roic", "returnOnInvestedCapital"),
            operating_margin=g("operatingMargin", "operating_margin"),
            revenue_growth=g("revenueGrowth", "revenue_growth"),
            eps_growth=g("earningsGrowth", "eps_growth", "epsGrowth"),
            debt_to_equity=g("debtToEquity", "debt_to_equity"),
            current_ratio=g("currentRatio", "current_ratio"),
            free_cashflow=g("freeCashflow", "free_cashflow"),
            fcf_yield=g("fcfYield", "fcf_yield"),
            piotroski=g("piotroski", "piotroskiFScore"),
            altman_z=g("altmanZ", "altman_z"),
            beneish_m=g("beneishM", "beneish_m"),
            fetched_at=str(fetched) if fetched else None,
        )
