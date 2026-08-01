"""F2.6 — ADV notional desde volume × price."""

from bolsa_market.instrument_fundamentals import build_fundamentals_snapshot, compute_adv_usd


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def test_compute_adv_usd():
    assert compute_adv_usd(average_volume=1e6, price=50.0) == 5e7
    assert compute_adv_usd(average_volume=None, price=50.0) is None
    assert compute_adv_usd(average_volume=1e6, price=0) is None


def test_snapshot_includes_adv_and_beta():
    modules = {
        "summaryProfile": {"sector": "Technology"},
        "summaryDetail": {
            "marketCap": _raw(1e11),
            "trailingPE": _raw(20.0),
            "averageVolume": _raw(2e6),
            "regularMarketPrice": _raw(100.0),
        },
        "financialData": {
            "freeCashflow": _raw(5e9),
            "revenueGrowth": _raw(0.08),
            "returnOnEquity": _raw(0.15),
            "currentPrice": _raw(100.0),
        },
        "defaultKeyStatistics": {
            "trailingEps": _raw(5.0),
            "bookValue": _raw(25.0),
            "sharesOutstanding": _raw(1e9),
            "beta": _raw(1.1),
        },
        "balanceSheetHistory": {"balanceSheetStatements": []},
        "incomeStatementHistory": {"incomeStatementHistory": []},
    }
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    assert snap["beta"] == 1.1
    assert snap["waccMethod"] == "fund_capm_v1"
    assert snap["averageVolume"] == 2e6
    # price from mcap/shares = 100
    assert snap["advUsd"] == 2e8
