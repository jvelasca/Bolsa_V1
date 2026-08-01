"""F2.4 — WACC proxy por sector + impacto en DCF."""

from __future__ import annotations

from bolsa_market.valuation import compute_dcf_fcf_2stage, compute_valuation_from_yahoo_fields
from bolsa_market.wacc import (
    FUND_WACC_VERSION,
    WACC_SECTOR_DEFAULT,
    resolve_sector_wacc,
)


def test_resolve_known_and_default():
    known, rate, key, method = resolve_sector_wacc("Technology")
    assert known is True
    assert rate == 0.095
    assert key == "Technology"
    assert method == FUND_WACC_VERSION

    known2, rate2, key2, method2 = resolve_sector_wacc("Unknown Sector XYZ")
    assert known2 is False
    assert rate2 == WACC_SECTOR_DEFAULT
    assert key2 is None
    assert method2 == FUND_WACC_VERSION


def test_case_insensitive_sector():
    _, rate, _, _ = resolve_sector_wacc("utilities")
    assert rate == 0.065


def test_lower_wacc_raises_dcf_value():
    """Menor r (Utilities) → mayor valor DCF que r=10% default."""
    common = dict(free_cashflow=1e9, market_cap=10e9, revenue_growth=0.05)
    v_hi_r, _, _ = compute_dcf_fcf_2stage(**common, discount_rate=0.10)
    v_lo_r, _, _ = compute_dcf_fcf_2stage(**common, discount_rate=0.065)
    assert v_hi_r is not None and v_lo_r is not None
    assert v_lo_r > v_hi_r

    util = compute_valuation_from_yahoo_fields(
        market_cap=10e9,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=None,
        trailing_eps=None,
        book_value_per_share=None,
        shares_outstanding=None,
        sector="Utilities",
    )
    tech = compute_valuation_from_yahoo_fields(
        market_cap=10e9,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=None,
        trailing_eps=None,
        book_value_per_share=None,
        shares_outstanding=None,
        sector="Technology",
    )
    assert util["dcfEquityValue"] > tech["dcfEquityValue"]
