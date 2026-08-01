"""Snapshot fundamentales Yahoo v3 — Altman Z + ratios cognitivos."""

from bolsa_market.instrument_fundamentals import (
    FUNDAMENTALS_SOURCE_VERSION,
    build_fundamentals_snapshot,
    compute_altman_z,
    compute_fcf_yield,
    parse_fundamentals_from_profile_snapshot,
)


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def test_compute_altman_z_classic():
    z, method = compute_altman_z(
        total_assets=100.0,
        total_current_assets=40.0,
        total_current_liabilities=20.0,
        retained_earnings=30.0,
        ebit=15.0,
        market_cap=200.0,
        total_liabilities=50.0,
        sales=120.0,
    )
    # X1=0.2, X2=0.3, X3=0.15, X4=4.0, X5=1.2
    # 1.2*0.2 + 1.4*0.3 + 3.3*0.15 + 0.6*4 + 1.2 = 0.24+0.42+0.495+2.4+1.2 = 4.755
    assert method == "altman_z_classic_v1"
    assert z is not None
    assert abs(z - 4.755) < 1e-3


def test_compute_altman_z_incomplete():
    z, method = compute_altman_z(
        total_assets=100.0,
        total_current_assets=40.0,
        total_current_liabilities=20.0,
        retained_earnings=None,
        ebit=15.0,
        market_cap=200.0,
        total_liabilities=50.0,
        sales=120.0,
    )
    assert z is None and method is None


def test_build_fundamentals_snapshot_with_altman():
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {
            "marketCap": _raw(2e11),
            "trailingPE": _raw(22.0),
            "forwardPE": _raw(20.0),
        },
        "financialData": {
            "returnOnEquity": _raw(0.18),
            "operatingMargins": _raw(0.25),
            "revenueGrowth": _raw(0.1),
            "debtToEquity": _raw(80.0),
            "currentRatio": _raw(1.4),
            "ebitda": _raw(2e10),
            "totalRevenue": _raw(8e10),
        },
        "defaultKeyStatistics": {},
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                {
                    "totalAssets": _raw(1e11),
                    "totalCurrentAssets": _raw(4e10),
                    "totalCurrentLiabilities": _raw(2e10),
                    "retainedEarnings": _raw(3e10),
                    "totalLiab": _raw(4e10),
                }
            ]
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [
                {
                    "ebit": _raw(1.5e10),
                    "totalRevenue": _raw(8e10),
                }
            ]
        },
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["sourceVersion"] == FUNDAMENTALS_SOURCE_VERSION
    assert snap["roe"] == 0.18
    assert snap["altmanZ"] is not None
    assert snap["altmanMethod"] == "altman_z_classic_v1"
    assert snap["altmanEbitSource"] == "income_statement"
    assert abs(snap["debtToEquity"] - 0.8) < 1e-6


def test_altman_fallback_ebitda_proxy():
    modules = {
        "summaryProfile": {},
        "summaryDetail": {"marketCap": _raw(1e11)},
        "financialData": {
            "ebitda": _raw(1e10),
            "totalRevenue": _raw(5e10),
        },
        "defaultKeyStatistics": {},
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                {
                    "totalAssets": _raw(8e10),
                    "totalCurrentAssets": _raw(3e10),
                    "totalCurrentLiabilities": _raw(1.5e10),
                    "retainedEarnings": _raw(2e10),
                    "totalLiab": _raw(3e10),
                }
            ]
        },
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["altmanZ"] is not None
    assert snap["altmanEbitSource"] == "financial_ebitda_proxy"


def test_compute_fcf_yield():
    assert compute_fcf_yield(free_cashflow=1e9, market_cap=1e10) == 0.1
    assert compute_fcf_yield(free_cashflow=1e9, market_cap=0) is None
    assert compute_fcf_yield(free_cashflow=None, market_cap=1e10) is None


def test_build_fundamentals_snapshot_fcf_yield():
    modules = {
        "summaryProfile": {},
        "summaryDetail": {"marketCap": _raw(1e10)},
        "financialData": {"freeCashflow": _raw(1e9)},
        "defaultKeyStatistics": {},
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["fcfYield"] == 0.1
    assert snap["freeCashflow"] == 1e9


def test_roic_uses_balance_debt_cash_when_financial_thin():
    """Timeseries llena balance.totalDebt/cash; financialData a veces no trae TTM."""
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {"marketCap": _raw(1e10), "sharesOutstanding": _raw(1e8)},
        "financialData": {},  # sin totalDebt/totalCash
        "defaultKeyStatistics": {"bookValue": _raw(40.0)},
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                {
                    "totalAssets": _raw(5e9),
                    "totalStockholderEquity": _raw(4e9),
                    "totalDebt": _raw(2e9),
                    "cash": _raw(5e8),
                }
            ]
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [
                {
                    "ebit": _raw(1e9),
                    "totalRevenue": _raw(8e9),
                    "incomeTaxExpense": _raw(2.1e8),
                    "incomeBeforeTax": _raw(1e9),
                }
            ]
        },
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["roic"] is not None
    assert snap["roicMethod"] == "roic_nopat_ic_v1"


def test_parse_from_profile_snapshot():
    profile = {
        "fundamentals": {
            "marketCap": 1e9,
            "roe": 0.2,
            "altmanZ": 3.1,
            "fetchedAt": "2026-07-23T00:00:00Z",
        }
    }
    assert parse_fundamentals_from_profile_snapshot(profile)["altmanZ"] == 3.1
    assert parse_fundamentals_from_profile_snapshot({}) is None
