"""F2.3 — Graham Number + DCF FCF 2 etapas."""

from bolsa_market.valuation import (
    DCF_METHOD,
    GRAHAM_METHOD,
    compute_dcf_fcf_2stage,
    compute_graham_number,
    compute_graham_upside,
    compute_price_per_share,
    compute_valuation_from_yahoo_fields,
)
from bolsa_market.instrument_fundamentals import build_fundamentals_snapshot


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def test_graham_number_classic():
    # sqrt(22.5 * 5 * 20) = sqrt(2250) ≈ 47.434
    g, method = compute_graham_number(eps=5.0, book_value_per_share=20.0)
    assert method == GRAHAM_METHOD
    assert g is not None
    assert abs(g - 47.4342) < 1e-3


def test_graham_requires_positive_inputs():
    assert compute_graham_number(eps=-1.0, book_value_per_share=10.0) == (None, None)
    assert compute_graham_number(eps=1.0, book_value_per_share=None) == (None, None)


def test_graham_upside():
    upside = compute_graham_upside(graham_number=50.0, price_per_share=40.0)
    assert upside is not None
    assert abs(upside - 0.25) < 1e-6


def test_price_from_mcap_shares():
    p = compute_price_per_share(
        market_cap=1_000_000.0,
        shares_outstanding=10_000.0,
        eps=None,
        trailing_pe=None,
    )
    assert p == 100.0


def test_dcf_positive_fcf():
    value, upside, method = compute_dcf_fcf_2stage(
        free_cashflow=1e9,
        market_cap=10e9,
        revenue_growth=0.08,
    )
    assert method == DCF_METHOD
    assert value is not None and value > 0
    assert upside is not None


def test_dcf_null_when_fcf_non_positive():
    assert compute_dcf_fcf_2stage(
        free_cashflow=-1e6,
        market_cap=1e9,
        revenue_growth=0.05,
    ) == (None, None, None)


def test_dcf_growth_capped():
    # g raw 50% → capped 15%; still computable
    v1, _, _ = compute_dcf_fcf_2stage(
        free_cashflow=1e9, market_cap=10e9, revenue_growth=0.5
    )
    v2, _, _ = compute_dcf_fcf_2stage(
        free_cashflow=1e9, market_cap=10e9, revenue_growth=0.15
    )
    assert v1 == v2


def test_snapshot_includes_valuation():
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {
            "marketCap": _raw(1e11),
            "trailingPE": _raw(20.0),
        },
        "financialData": {
            "freeCashflow": _raw(5e9),
            "revenueGrowth": _raw(0.08),
            "returnOnEquity": _raw(0.15),
        },
        "defaultKeyStatistics": {
            "trailingEps": _raw(5.0),
            "bookValue": _raw(25.0),
            "sharesOutstanding": _raw(1e9),
        },
        "balanceSheetHistory": {"balanceSheetStatements": []},
        "incomeStatementHistory": {"incomeStatementHistory": []},
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["grahamNumber"] is not None
    assert snap["grahamMethod"] == GRAHAM_METHOD
    assert snap["grahamUpside"] is not None
    assert snap["dcfEquityValue"] is not None
    assert snap["dcfMethod"] == DCF_METHOD
    assert snap["dcfUpside"] is not None
    assert snap["wacc"] == 0.095  # Technology overlay F2.4
    assert snap["waccMethod"] == "fund_wacc_sector_v1"


def test_valuation_bundle_keys():
    out = compute_valuation_from_yahoo_fields(
        market_cap=1e10,
        free_cashflow=1e9,
        revenue_growth=0.05,
        trailing_pe=15.0,
        trailing_eps=4.0,
        book_value_per_share=20.0,
        shares_outstanding=5e8,
        sector="Utilities",
    )
    assert set(out) == {
        "grahamNumber",
        "grahamMethod",
        "grahamUpside",
        "beta",
        "wacc",
        "waccMethod",
        "capmRf",
        "capmErp",
        "dcfEquityValue",
        "dcfUpside",
        "dcfMethod",
        "dcfScenarios",
    }
    assert out["dcfScenarios"] is not None
    assert out["dcfScenarios"]["base"]["upside"] == out["dcfUpside"]
    assert out["wacc"] == 0.065
    assert out["dcfMethod"] == DCF_METHOD
