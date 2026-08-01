"""FA as-of desde statementPack."""

from __future__ import annotations

from bolsa_market.fundamentals_as_of import (
    ASOF_SOURCE_VERSION,
    build_fundamentals_as_of_from_pack,
    extract_statement_pack,
    filter_statement_rows,
    statement_end_date,
)


def _stmt(end: str, **fields: float) -> dict:
    row: dict = {"endDate": {"fmt": end, "raw": end}}
    for k, v in fields.items():
        row[k] = {"raw": v}
    return row


def test_statement_end_date():
    assert statement_end_date({"endDate": {"fmt": "2023-12-31"}}) == "2023-12-31"
    assert statement_end_date({"endDate": "2022-06-30"}) == "2022-06-30"


def test_filter_statement_rows_cuts_future():
    rows = [
        _stmt("2024-12-31", totalAssets=100),
        _stmt("2023-12-31", totalAssets=90),
        _stmt("2022-12-31", totalAssets=80),
    ]
    kept = filter_statement_rows(rows, "2023-06-15")
    assert [statement_end_date(r) for r in kept] == ["2022-12-31"]


def test_extract_and_rebuild_as_of():
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                _stmt(
                    "2024-12-31",
                    totalAssets=200,
                    totalCurrentAssets=80,
                    totalCurrentLiabilities=40,
                    retainedEarnings=50,
                    totalLiab=100,
                    totalStockholderEquity=100,
                    ordinarySharesNumber=10,
                    totalDebt=20,
                    cash=5,
                ),
                _stmt(
                    "2023-12-31",
                    totalAssets=180,
                    totalCurrentAssets=70,
                    totalCurrentLiabilities=35,
                    retainedEarnings=40,
                    totalLiab=90,
                    totalStockholderEquity=90,
                    ordinarySharesNumber=10,
                    totalDebt=25,
                    cash=4,
                ),
            ]
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [
                _stmt(
                    "2024-12-31",
                    totalRevenue=120,
                    operatingIncome=30,
                    netIncome=20,
                    ebit=30,
                ),
                _stmt(
                    "2023-12-31",
                    totalRevenue=100,
                    operatingIncome=22,
                    netIncome=15,
                    ebit=22,
                ),
            ]
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [
                _stmt(
                    "2024-12-31",
                    totalCashFromOperatingActivities=25,
                    capitalExpenditures=-5,
                    netIncome=20,
                ),
                _stmt(
                    "2023-12-31",
                    totalCashFromOperatingActivities=18,
                    capitalExpenditures=-4,
                    netIncome=15,
                ),
            ]
        },
    }
    pack = extract_statement_pack(modules)
    assert pack["sector"] == "Technology"
    assert len(pack["balanceSheetHistory"]) == 2

    # As-of mid-2024: only 2023 statements
    snap = build_fundamentals_as_of_from_pack(pack, "2024-06-01", close_price=15.0)
    assert snap is not None
    assert snap["asOfReconstructed"] is True
    assert snap["asOfDate"] == "2024-06-01"
    assert snap["sourceVersion"] == ASOF_SOURCE_VERSION
    assert snap["sector"] == "Technology"
    assert snap["marketCap"] == 15.0 * 10
    assert snap["fetchedAt"].startswith("2024-06-01")
    # 2024 statements must not leak
    assert snap["totalAssets"] == 180


def test_rebuild_none_without_statements():
    assert build_fundamentals_as_of_from_pack({"schemaVersion": "fa_statement_pack_v1"}, "2020-01-01") is None
