"""F2.8 — Beneish M-Score (null-if-incomplete)."""

from bolsa_market.beneish import (
    BENEISH_METHOD,
    compute_beneish_from_yahoo_modules,
    compute_beneish_indices,
    compute_beneish_m,
)


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def _bal(*, ta, ca, cl, rec, ppe, ltd):
    return {
        "totalAssets": _raw(ta),
        "totalCurrentAssets": _raw(ca),
        "totalCurrentLiabilities": _raw(cl),
        "netReceivables": _raw(rec),
        "netPPE": _raw(ppe),
        "longTermDebt": _raw(ltd),
    }


def _inc(*, sales, gp, sga, ni, dep):
    return {
        "totalRevenue": _raw(sales),
        "grossProfit": _raw(gp),
        "sellingGeneralAdministrative": _raw(sga),
        "netIncome": _raw(ni),
        "depreciationAndAmortization": _raw(dep),
    }


def _cf(*, cfo, dep):
    return {
        "totalCashFromOperatingActivities": _raw(cfo),
        "depreciationAndAmortization": _raw(dep),
    }


def test_beneish_computes_with_full_inputs():
    indices = compute_beneish_indices(
        bal_c=_bal(ta=1000, ca=400, cl=200, rec=120, ppe=300, ltd=150),
        bal_p=_bal(ta=900, ca=350, cl=180, rec=90, ppe=280, ltd=140),
        inc_c=_inc(sales=800, gp=320, sga=80, ni=60, dep=40),
        inc_p=_inc(sales=700, gp=300, sga=70, ni=55, dep=35),
        cf_c=_cf(cfo=70, dep=40),
        cf_p=_cf(cfo=65, dep=35),
    )
    assert indices is not None
    m = compute_beneish_m(indices)
    assert isinstance(m, float)


def test_beneish_null_if_missing_receivables():
    bal_c = _bal(ta=1000, ca=400, cl=200, rec=120, ppe=300, ltd=150)
    del bal_c["netReceivables"]
    indices = compute_beneish_indices(
        bal_c=bal_c,
        bal_p=_bal(ta=900, ca=350, cl=180, rec=90, ppe=280, ltd=140),
        inc_c=_inc(sales=800, gp=320, sga=80, ni=60, dep=40),
        inc_p=_inc(sales=700, gp=300, sga=70, ni=55, dep=35),
        cf_c=_cf(cfo=70, dep=40),
    )
    assert indices is None


def test_beneish_from_modules():
    modules = {
        "balanceSheetHistory": {
            "balanceSheetStatements": [
                _bal(ta=1000, ca=400, cl=200, rec=120, ppe=300, ltd=150),
                _bal(ta=900, ca=350, cl=180, rec=90, ppe=280, ltd=140),
            ]
        },
        "incomeStatementHistory": {
            "incomeStatementHistory": [
                _inc(sales=800, gp=320, sga=80, ni=60, dep=40),
                _inc(sales=700, gp=300, sga=70, ni=55, dep=35),
            ]
        },
        "cashflowStatementHistory": {
            "cashflowStatements": [
                _cf(cfo=70, dep=40),
                _cf(cfo=65, dep=35),
            ]
        },
    }
    m, method = compute_beneish_from_yahoo_modules(modules)
    assert method == BENEISH_METHOD
    assert m is not None
