"""Timeseries Yahoo → statements cuando balanceSheetHistory llega vacío."""

from __future__ import annotations

from bolsa_market.yahoo_fundamentals_timeseries import (
    enrich_modules_from_timeseries,
    parse_timeseries_payload,
)


def _ts_payload_assets() -> dict:
    assets = [
        {
            "asOfDate": "2024-09-30",
            "reportedValue": {"raw": 3.65e11},
        },
        {
            "asOfDate": "2023-09-30",
            "reportedValue": {"raw": 3.53e11},
        },
    ]
    ca = [
        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.5e11}},
        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.4e11}},
    ]
    cl = [
        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.2e11}},
        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.1e11}},
    ]
    equity = [
        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 6.0e10}},
        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 5.5e10}},
    ]
    ocf = [
        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.1e11}},
        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.0e11}},
    ]
    return {
        "timeseries": {
            "result": [
                {"meta": {"type": ["annualTotalAssets"]}, "annualTotalAssets": assets},
                {"meta": {"type": ["annualCurrentAssets"]}, "annualCurrentAssets": ca},
                {
                    "meta": {"type": ["annualCurrentLiabilities"]},
                    "annualCurrentLiabilities": cl,
                },
                {
                    "meta": {"type": ["annualStockholdersEquity"]},
                    "annualStockholdersEquity": equity,
                },
                {
                    "meta": {"type": ["annualLongTermDebt"]},
                    "annualLongTermDebt": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 9e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1e11}},
                    ],
                },
                {
                    "meta": {"type": ["annualRetainedEarnings"]},
                    "annualRetainedEarnings": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 2e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.5e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualTotalLiabilitiesNetMinorityInterest"]},
                    "annualTotalLiabilitiesNetMinorityInterest": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 3e11}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 2.9e11}},
                    ],
                },
                {
                    "meta": {"type": ["annualOrdinarySharesNumber"]},
                    "annualOrdinarySharesNumber": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.5e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.55e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualNetPPE"]},
                    "annualNetPPE": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 4e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 3.8e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualAccountsReceivable"]},
                    "annualAccountsReceivable": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 3e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 2.5e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualCashAndCashEquivalents"]},
                    "annualCashAndCashEquivalents": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 3e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 2.8e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualOperatingCashFlow"]},
                    "annualOperatingCashFlow": ocf,
                },
                {
                    "meta": {"type": ["annualDepreciationAndAmortization"]},
                    "annualDepreciationAndAmortization": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.1e10}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.0e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualTotalRevenue"]},
                    "annualTotalRevenue": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 4e11}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 3.8e11}},
                    ],
                },
                {
                    "meta": {"type": ["annualNetIncome"]},
                    "annualNetIncome": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1e11}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 9e10}},
                    ],
                },
                {
                    "meta": {"type": ["annualEBIT"]},
                    "annualEBIT": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.2e11}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.1e11}},
                    ],
                },
                {
                    "meta": {"type": ["annualGrossProfit"]},
                    "annualGrossProfit": [
                        {"asOfDate": "2024-09-30", "reportedValue": {"raw": 1.8e11}},
                        {"asOfDate": "2023-09-30", "reportedValue": {"raw": 1.7e11}},
                    ],
                },
            ]
        }
    }


def test_parse_and_enrich_empty_balance() -> None:
    series = parse_timeseries_payload(_ts_payload_assets())
    assert "annualTotalAssets" in series
    assert series["annualTotalAssets"][0][0] == "2024-09-30"

    modules = {
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                {"endDate": {"fmt": "2024-09-30"}, "maxAge": 1},
                {"endDate": {"fmt": "2023-09-30"}, "maxAge": 1},
            ]
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [
                {"endDate": {"fmt": "2024-09-30"}, "netIncome": {"raw": 1e11}},
            ]
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [
                {
                    "endDate": {"fmt": "2024-09-30"},
                    "netIncome": {"raw": 1e11},
                    "totalRevenue": {"raw": 4e11},
                    "grossProfit": {"raw": 1.8e11},
                },
                {
                    "endDate": {"fmt": "2023-09-30"},
                    "netIncome": {"raw": 9e10},
                    "totalRevenue": {"raw": 3.8e11},
                    "grossProfit": {"raw": 1.7e11},
                },
            ]
        },
    }
    enriched = enrich_modules_from_timeseries(modules, _ts_payload_assets())
    bals = enriched["balanceSheetHistory"]["balanceSheetStatements"]
    assert bals[0]["totalAssets"]["raw"] == 3.65e11
    assert bals[1]["totalAssets"]["raw"] == 3.53e11
    cfs = enriched["cashflowStatementHistory"]["cashflowStatements"]
    assert cfs[0]["totalCashFromOperatingActivities"]["raw"] == 1.1e11

    from bolsa_market.piotroski import compute_piotroski_from_yahoo_modules

    score, method = compute_piotroski_from_yahoo_modules(enriched)
    assert method == "piotroski_f_annual_v1"
    assert score is not None and 0 <= score <= 9


def test_enrich_replaces_empty_income_statement() -> None:
    modules = {
        "incomeStatementHistory": {"incomeStatementHistory": []},
        "balanceSheetHistory": {"balanceSheetStatements": []},
    }
    enriched = enrich_modules_from_timeseries(modules, _ts_payload_assets())
    incomes = enriched["incomeStatementHistory"]["incomeStatementHistory"]
    assert len(incomes) >= 2
    assert incomes[0]["totalRevenue"]["raw"] == 4e11
    assert incomes[0]["ebit"]["raw"] == 1.2e11
    assert incomes[1]["netIncome"]["raw"] == 9e10
