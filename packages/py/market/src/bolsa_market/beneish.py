"""FIE F2.8 — Beneish M-Score anual (`beneish_m_annual_v1`).

Modelo clásico (8 índices). Null-if-incomplete: si falta cualquier índice → null.
No scores parciales.

M = −4.84 + 0.92·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI
    + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI

TATA simplificado: (NI − CFO) / TA (documentado; no accrual completo).

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

from typing import Any

BENEISH_METHOD = "beneish_m_annual_v1"
# Umbral clásico de manipulación probable
BENEISH_MANIPULATION_THRESHOLD = -1.78


def _num(node: Any) -> float | None:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict):
        raw = node.get("raw")
        if isinstance(raw, (int, float)):
            return float(raw)
        fmt = node.get("fmt")
        if isinstance(fmt, str):
            cleaned = fmt.replace(",", "").replace("%", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _first(row: dict[str, Any] | None, *keys: str) -> float | None:
    if not isinstance(row, dict):
        return None
    for key in keys:
        if key in row:
            val = _num(row.get(key))
            if val is not None:
                return val
    return None


def _rows(module: dict[str, Any] | None, list_key: str) -> list[dict[str, Any]]:
    if not isinstance(module, dict):
        return []
    rows = module.get(list_key)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _safe_ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _receivables(row: dict[str, Any] | None) -> float | None:
    return _first(row, "netReceivables", "accountsReceivable", "receivables")


def _ppe(row: dict[str, Any] | None) -> float | None:
    return _first(
        row,
        "netPPE",
        "netTangibleAssets",
        "propertyPlantEquipment",
        "grossPPE",
    )


def _depreciation(income: dict[str, Any] | None, cashflow: dict[str, Any] | None) -> float | None:
    return _first(
        cashflow,
        "depreciation",
        "depreciationAndAmortization",
        "depreciationAmortizationDepletion",
    ) or _first(
        income,
        "depreciation",
        "depreciationAndAmortization",
        "reconciledDepreciation",
    )


def _sga(income: dict[str, Any] | None) -> float | None:
    return _first(
        income,
        "sellingGeneralAdministrative",
        "sellingGeneralAndAdministration",
        "sellingAndMarketingExpense",
    )


def _ltd(row: dict[str, Any] | None) -> float | None:
    return _first(
        row,
        "longTermDebt",
        "longTermDebtAndCapitalLeaseObligation",
        "longTermDebtTotal",
    )


def _cfo(row: dict[str, Any] | None) -> float | None:
    return _first(
        row,
        "totalCashFromOperatingActivities",
        "operatingCashflow",
        "cashFlowFromContinuingOperatingActivities",
    )


def compute_beneish_indices(
    *,
    bal_c: dict[str, Any],
    bal_p: dict[str, Any],
    inc_c: dict[str, Any],
    inc_p: dict[str, Any],
    cf_c: dict[str, Any],
    cf_p: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    sales_c = _first(inc_c, "totalRevenue")
    sales_p = _first(inc_p, "totalRevenue")
    gp_c = _first(inc_c, "grossProfit")
    gp_p = _first(inc_p, "grossProfit")
    ta_c = _first(bal_c, "totalAssets")
    ta_p = _first(bal_p, "totalAssets")
    ca_c = _first(bal_c, "totalCurrentAssets")
    ca_p = _first(bal_p, "totalCurrentAssets")
    cl_c = _first(bal_c, "totalCurrentLiabilities")
    cl_p = _first(bal_p, "totalCurrentLiabilities")
    rec_c = _receivables(bal_c)
    rec_p = _receivables(bal_p)
    ppe_c = _ppe(bal_c)
    ppe_p = _ppe(bal_p)
    dep_c = _depreciation(inc_c, cf_c)
    dep_p = _depreciation(inc_p, cf_p)
    sga_c = _sga(inc_c)
    sga_p = _sga(inc_p)
    ltd_c = _ltd(bal_c)
    ltd_p = _ltd(bal_p)
    ni_c = _first(inc_c, "netIncome", "netIncomeApplicableToCommonShares")
    cfo_c = _cfo(cf_c)

    if None in (
        sales_c,
        sales_p,
        gp_c,
        gp_p,
        ta_c,
        ta_p,
        ca_c,
        ca_p,
        cl_c,
        cl_p,
        rec_c,
        rec_p,
        ppe_c,
        ppe_p,
        dep_c,
        dep_p,
        sga_c,
        sga_p,
        ltd_c,
        ltd_p,
        ni_c,
        cfo_c,
    ):
        return None
    assert sales_c is not None and sales_p is not None
    assert gp_c is not None and gp_p is not None
    assert ta_c is not None and ta_p is not None and ta_c > 0 and ta_p > 0
    assert ca_c is not None and ca_p is not None
    assert cl_c is not None and cl_p is not None
    assert rec_c is not None and rec_p is not None
    assert ppe_c is not None and ppe_p is not None
    assert dep_c is not None and dep_p is not None
    assert sga_c is not None and sga_p is not None
    assert ltd_c is not None and ltd_p is not None
    assert ni_c is not None and cfo_c is not None

    if sales_c <= 0 or sales_p <= 0:
        return None

    # DSRI
    dsri = _safe_ratio(rec_c / sales_c, rec_p / sales_p)
    # GMI
    gm_c = gp_c / sales_c
    gm_p = gp_p / sales_p
    if gm_c == 0:
        return None
    gmi = gm_p / gm_c
    # AQI
    aq_c = 1.0 - (ca_c + ppe_c) / ta_c
    aq_p = 1.0 - (ca_p + ppe_p) / ta_p
    if aq_p == 0:
        return None
    aqi = aq_c / aq_p
    # SGI
    sgi = sales_c / sales_p
    # DEPI
    dep_rate_c = dep_c / (dep_c + ppe_c) if (dep_c + ppe_c) != 0 else None
    dep_rate_p = dep_p / (dep_p + ppe_p) if (dep_p + ppe_p) != 0 else None
    depi = _safe_ratio(dep_rate_p, dep_rate_c)
    # SGAI
    sgai = _safe_ratio(sga_c / sales_c, sga_p / sales_p)
    # LVGI
    lev_c = (cl_c + ltd_c) / ta_c
    lev_p = (cl_p + ltd_p) / ta_p
    lvgi = _safe_ratio(lev_c, lev_p)
    # TATA simplified
    tata = (ni_c - cfo_c) / ta_c

    if None in (dsri, depi, sgai, lvgi):
        return None
    assert dsri is not None and depi is not None and sgai is not None and lvgi is not None

    return {
        "dsri": dsri,
        "gmi": gmi,
        "aqi": aqi,
        "sgi": sgi,
        "depi": depi,
        "sgai": sgai,
        "tata": tata,
        "lvgi": lvgi,
    }


def compute_beneish_m(indices: dict[str, float]) -> float:
    return round(
        -4.84
        + 0.92 * indices["dsri"]
        + 0.528 * indices["gmi"]
        + 0.404 * indices["aqi"]
        + 0.892 * indices["sgi"]
        + 0.115 * indices["depi"]
        - 0.172 * indices["sgai"]
        + 4.679 * indices["tata"]
        - 0.327 * indices["lvgi"],
        4,
    )


def compute_beneish_from_yahoo_modules(
    yahoo_modules: dict[str, Any],
) -> tuple[float | None, str | None]:
    balances = _rows(yahoo_modules.get("balanceSheetHistory"), "balanceSheetStatements")
    incomes = _rows(yahoo_modules.get("incomeStatementHistory"), "incomeStatementHistory")
    cashflows = _rows(yahoo_modules.get("cashflowStatementHistory"), "cashflowStatements")
    if not cashflows:
        cashflows = _rows(
            yahoo_modules.get("cashflowStatementHistory"),
            "cashflowStatementHistory",
        )

    if len(balances) < 2 or len(incomes) < 2 or len(cashflows) < 1:
        return None, None

    indices = compute_beneish_indices(
        bal_c=balances[0],
        bal_p=balances[1],
        inc_c=incomes[0],
        inc_p=incomes[1],
        cf_c=cashflows[0],
        cf_p=cashflows[1] if len(cashflows) >= 2 else None,
    )
    if indices is None:
        return None, None
    return compute_beneish_m(indices), BENEISH_METHOD
