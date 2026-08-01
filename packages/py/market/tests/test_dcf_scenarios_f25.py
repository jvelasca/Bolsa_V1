"""F2.5 — DCF multi-escenario bear/base/bull."""

from bolsa_market.valuation import (
    DCF_SCENARIOS_METHOD,
    compute_dcf_scenarios,
    compute_valuation_from_yahoo_fields,
)


def test_scenarios_ordering_bull_gt_base_gt_bear():
    sc = compute_dcf_scenarios(
        free_cashflow=1e9,
        market_cap=10e9,
        revenue_growth=0.08,
        discount_rate=0.10,
    )
    assert sc is not None
    assert sc["method"] == DCF_SCENARIOS_METHOD
    assert sc["bull"]["upside"] > sc["base"]["upside"] > sc["bear"]["upside"]
    assert sc["bull"]["equityValue"] > sc["base"]["equityValue"] > sc["bear"]["equityValue"]
    assert sc["bear"]["wacc"] > sc["base"]["wacc"] > sc["bull"]["wacc"]
    assert sc["bear"]["growth"] < sc["base"]["growth"] < sc["bull"]["growth"]


def test_scenarios_null_without_fcf():
    assert (
        compute_dcf_scenarios(
            free_cashflow=None,
            market_cap=1e9,
            revenue_growth=0.05,
            discount_rate=0.10,
        )
        is None
    )


def test_base_matches_flat_dcf_fields():
    out = compute_valuation_from_yahoo_fields(
        market_cap=1e10,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=15.0,
        trailing_eps=4.0,
        book_value_per_share=20.0,
        shares_outstanding=5e8,
        sector="Technology",
    )
    assert out["dcfScenarios"] is not None
    assert out["dcfScenarios"]["base"]["upside"] == out["dcfUpside"]
    assert out["dcfScenarios"]["base"]["equityValue"] == out["dcfEquityValue"]
    assert abs(out["dcfScenarios"]["base"]["wacc"] - out["wacc"]) < 1e-9
