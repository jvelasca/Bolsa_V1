"""F2.6 — CAPM cost of equity + discount preferido sobre WACC sector."""

from bolsa_market.capm import (
    CAPM_ERP,
    CAPM_RF,
    FUND_CAPM_VERSION,
    clamp_beta,
    compute_capm_cost_of_equity,
)
from bolsa_market.valuation import compute_valuation_from_yahoo_fields


def test_capm_basic():
    ke, method, meta = compute_capm_cost_of_equity(1.0)
    assert method == FUND_CAPM_VERSION
    assert ke == round(CAPM_RF + 1.0 * CAPM_ERP, 4)
    assert meta["beta"] == 1.0
    assert meta["rf"] == CAPM_RF


def test_beta_clamped():
    assert clamp_beta(0.1) == 0.3
    assert clamp_beta(3.0) == 2.5
    assert clamp_beta(None) is None
    assert clamp_beta(-1) is None


def test_valuation_prefers_capm_when_beta():
    out = compute_valuation_from_yahoo_fields(
        market_cap=1e10,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=15.0,
        trailing_eps=4.0,
        book_value_per_share=20.0,
        shares_outstanding=5e8,
        sector="Utilities",  # sector WACC 6.5%
        beta=1.2,
    )
    assert out["waccMethod"] == FUND_CAPM_VERSION
    assert out["beta"] == 1.2
    expected = round(CAPM_RF + 1.2 * CAPM_ERP, 4)
    assert out["wacc"] == expected
    assert out["capmRf"] == CAPM_RF
    assert out["capmErp"] == CAPM_ERP
    assert out["dcfScenarios"]["base"]["wacc"] == expected


def test_valuation_falls_back_to_sector_without_beta():
    out = compute_valuation_from_yahoo_fields(
        market_cap=1e10,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=15.0,
        trailing_eps=4.0,
        book_value_per_share=20.0,
        shares_outstanding=5e8,
        sector="Utilities",
        beta=None,
    )
    assert out["waccMethod"] == "fund_wacc_sector_v1"
    assert out["wacc"] == 0.065
    assert out["beta"] is None
    assert out["capmRf"] is None
    assert out["capmErp"] is None
