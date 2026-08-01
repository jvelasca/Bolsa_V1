"""Piotroski F-Score F2.1 — 9/9 o null."""

from bolsa_market.piotroski import (
    PIOTROSKI_METHOD,
    compute_piotroski_f,
    compute_piotroski_from_yahoo_modules,
)
from bolsa_market.instrument_fundamentals import build_fundamentals_snapshot


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def _healthy_pair() -> dict:
    """Inputs que cumplen los 9 criterios → F=9."""
    balance_curr = {
        "totalAssets": _raw(110.0),
        "totalCurrentAssets": _raw(55.0),
        "totalCurrentLiabilities": _raw(25.0),
        "longTermDebt": _raw(20.0),
        "ordinarySharesNumber": _raw(100.0),
    }
    balance_prev = {
        "totalAssets": _raw(100.0),
        "totalCurrentAssets": _raw(40.0),
        "totalCurrentLiabilities": _raw(25.0),
        "longTermDebt": _raw(30.0),
        "ordinarySharesNumber": _raw(100.0),
    }
    income_curr = {
        "netIncome": _raw(12.0),
        "totalRevenue": _raw(120.0),
        "grossProfit": _raw(60.0),
    }
    income_prev = {
        "netIncome": _raw(8.0),
        "totalRevenue": _raw(100.0),
        "grossProfit": _raw(45.0),
    }
    cashflow_curr = {
        "totalCashFromOperatingActivities": _raw(15.0),
    }
    return {
        "balance_curr": balance_curr,
        "balance_prev": balance_prev,
        "income_curr": income_curr,
        "income_prev": income_prev,
        "cashflow_curr": cashflow_curr,
    }


def test_piotroski_perfect_nine():
    score, method = compute_piotroski_f(**_healthy_pair())
    assert method == PIOTROSKI_METHOD == "piotroski_f_annual_v1"
    assert score == 9


def test_piotroski_incomplete_returns_null():
    pair = _healthy_pair()
    pair["cashflow_curr"] = None
    score, method = compute_piotroski_f(**pair)
    assert score is None and method is None


def test_piotroski_missing_shares_returns_null():
    pair = _healthy_pair()
    del pair["balance_curr"]["ordinarySharesNumber"]
    del pair["balance_prev"]["ordinarySharesNumber"]
    score, method = compute_piotroski_f(**pair)
    assert score is None and method is None


def test_piotroski_ltd_missing_treated_as_zero():
    pair = _healthy_pair()
    del pair["balance_curr"]["longTermDebt"]
    del pair["balance_prev"]["longTermDebt"]
    # sin LTD: lev_c=0, lev_p=0 → Δleverage no baja → F=8 (resto OK)
    score, method = compute_piotroski_f(**pair)
    assert method == PIOTROSKI_METHOD
    assert score == 8


def test_piotroski_from_yahoo_modules():
    pair = _healthy_pair()
    modules = {
        "balanceSheetHistory": {
            "balanceSheetStatements": [pair["balance_curr"], pair["balance_prev"]],
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [pair["income_curr"], pair["income_prev"]],
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [pair["cashflow_curr"]],
        },
    }
    score, method = compute_piotroski_from_yahoo_modules(modules)
    assert score == 9 and method == PIOTROSKI_METHOD


def test_piotroski_yahoo_needs_two_years():
    pair = _healthy_pair()
    modules = {
        "balanceSheetHistory": {
            "balanceSheetStatements": [pair["balance_curr"]],
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [pair["income_curr"], pair["income_prev"]],
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [pair["cashflow_curr"]],
        },
    }
    score, method = compute_piotroski_from_yahoo_modules(modules)
    assert score is None and method is None


def test_snapshot_includes_piotroski():
    pair = _healthy_pair()
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {"marketCap": _raw(2e11)},
        "financialData": {"returnOnEquity": _raw(0.18)},
        "defaultKeyStatistics": {},
        "balanceSheetHistory": {
            "balanceSheetStatements": [pair["balance_curr"], pair["balance_prev"]],
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [pair["income_curr"], pair["income_prev"]],
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [pair["cashflow_curr"]],
        },
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["piotroski"] == 9
    assert snap["piotroskiMethod"] == PIOTROSKI_METHOD


def test_snapshot_piotroski_null_without_cashflow():
    pair = _healthy_pair()
    modules = {
        "summaryProfile": {},
        "summaryDetail": {},
        "financialData": {},
        "defaultKeyStatistics": {},
        "balanceSheetHistory": {
            "balanceSheetStatements": [pair["balance_curr"], pair["balance_prev"]],
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [pair["income_curr"], pair["income_prev"]],
        },
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["piotroski"] is None
    assert snap["piotroskiMethod"] is None
