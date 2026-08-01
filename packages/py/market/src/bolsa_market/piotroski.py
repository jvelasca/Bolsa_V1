"""Piotroski F-Score (9 criterios anuales) — FIE F2.1.

Solo se devuelve un entero 0–9 si **todos** los criterios son computables.
Si falta cualquier input YoY → (None, None). Sin scores parciales engañosos.

Método: `piotroski_f_annual_v1` (estados anuales Yahoo: balance, income, cashflow).

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

from typing import Any

PIOTROSKI_METHOD = "piotroski_f_annual_v1"


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


def _first_present(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in row:
            val = _num(row.get(key))
            if val is not None:
                return val
    return None


def _statement_rows(module: dict[str, Any] | None, list_key: str) -> list[dict[str, Any]]:
    if not isinstance(module, dict):
        return []
    rows = module.get(list_key)
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
    return out


def _gross_margin(*, revenue: float | None, gross_profit: float | None) -> float | None:
    if revenue is None or revenue <= 0 or gross_profit is None:
        return None
    return gross_profit / revenue


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    return num / den


def compute_piotroski_f(
    *,
    balance_curr: dict[str, Any] | None,
    balance_prev: dict[str, Any] | None,
    income_curr: dict[str, Any] | None,
    income_prev: dict[str, Any] | None,
    cashflow_curr: dict[str, Any] | None,
) -> tuple[int | None, str | None]:
    """
    F-Score clásico (Piotroski 2000), versión anual pública.

    1 ROA > 0
    2 CFO > 0
    3 ΔROA > 0
    4 Accrual: CFO > NI
    5 ΔLeverage (LTD/Assets) ↓
    6 ΔCurrent ratio ↑
    7 Sin dilución de acciones (shares_t ≤ shares_{t-1})
    8 ΔGross margin ↑
    9 ΔAsset turnover ↑
    """
    if not all((balance_curr, balance_prev, income_curr, income_prev, cashflow_curr)):
        return None, None

    ta_c = _first_present(balance_curr, "totalAssets")
    ta_p = _first_present(balance_prev, "totalAssets")
    tca_c = _first_present(balance_curr, "totalCurrentAssets")
    tca_p = _first_present(balance_prev, "totalCurrentAssets")
    tcl_c = _first_present(balance_curr, "totalCurrentLiabilities")
    tcl_p = _first_present(balance_prev, "totalCurrentLiabilities")
    ltd_c = _first_present(
        balance_curr,
        "longTermDebt",
        "longTermDebtTotal",
        "longTermDebtNoncurrent",
        "longTermDebtAndCapitalLeaseObligation",
    )
    ltd_p = _first_present(
        balance_prev,
        "longTermDebt",
        "longTermDebtTotal",
        "longTermDebtNoncurrent",
        "longTermDebtAndCapitalLeaseObligation",
    )
    # Deuda a LP ausente en Yahoo ≈ 0 (empresas sin LTD).
    if ltd_c is None and ta_c is not None:
        ltd_c = 0.0
    if ltd_p is None and ta_p is not None:
        ltd_p = 0.0
    shares_c = _first_present(
        balance_curr,
        "ordinarySharesNumber",
        "shareIssued",
        "commonStockSharesOutstanding",
        "commonStock",
    )
    shares_p = _first_present(
        balance_prev,
        "ordinarySharesNumber",
        "shareIssued",
        "commonStockSharesOutstanding",
        "commonStock",
    )

    ni_c = _first_present(income_curr, "netIncome", "netIncomeApplicableToCommonShares")
    ni_p = _first_present(income_prev, "netIncome", "netIncomeApplicableToCommonShares")
    rev_c = _first_present(income_curr, "totalRevenue")
    rev_p = _first_present(income_prev, "totalRevenue")
    gp_c = _first_present(income_curr, "grossProfit")
    gp_p = _first_present(income_prev, "grossProfit")

    cfo_c = _first_present(
        cashflow_curr,
        "totalCashFromOperatingActivities",
        "operatingCashflow",
        "cashFlowFromContinuingOperatingActivities",
    )

    roa_c = _safe_div(ni_c, ta_c)
    roa_p = _safe_div(ni_p, ta_p)
    cr_c = _safe_div(tca_c, tcl_c)
    cr_p = _safe_div(tca_p, tcl_p)
    lev_c = _safe_div(ltd_c, ta_c)
    lev_p = _safe_div(ltd_p, ta_p)
    gm_c = _gross_margin(revenue=rev_c, gross_profit=gp_c)
    gm_p = _gross_margin(revenue=rev_p, gross_profit=gp_p)
    at_c = _safe_div(rev_c, ta_c)
    at_p = _safe_div(rev_p, ta_p)

    needed = [
        roa_c,
        cfo_c,
        roa_p,
        ni_c,
        lev_c,
        lev_p,
        cr_c,
        cr_p,
        shares_c,
        shares_p,
        gm_c,
        gm_p,
        at_c,
        at_p,
    ]
    if any(v is None for v in needed):
        return None, None

    assert roa_c is not None and cfo_c is not None and roa_p is not None
    assert ni_c is not None and lev_c is not None and lev_p is not None
    assert cr_c is not None and cr_p is not None
    assert shares_c is not None and shares_p is not None
    assert gm_c is not None and gm_p is not None and at_c is not None and at_p is not None

    score = 0
    # 1 ROA > 0
    if roa_c > 0:
        score += 1
    # 2 CFO > 0
    if cfo_c > 0:
        score += 1
    # 3 ΔROA > 0
    if roa_c > roa_p:
        score += 1
    # 4 Accrual CFO > NI
    if cfo_c > ni_c:
        score += 1
    # 5 Leverage down
    if lev_c < lev_p:
        score += 1
    # 6 Current ratio up
    if cr_c > cr_p:
        score += 1
    # 7 No dilution
    if shares_c <= shares_p:
        score += 1
    # 8 Gross margin up
    if gm_c > gm_p:
        score += 1
    # 9 Asset turnover up
    if at_c > at_p:
        score += 1

    return score, PIOTROSKI_METHOD


def compute_piotroski_from_yahoo_modules(yahoo_modules: dict[str, Any]) -> tuple[int | None, str | None]:
    balances = _statement_rows(
        yahoo_modules.get("balanceSheetHistory"),
        "balanceSheetStatements",
    )
    incomes = _statement_rows(
        yahoo_modules.get("incomeStatementHistory"),
        "incomeStatementHistory",
    )
    cashflows = _statement_rows(
        yahoo_modules.get("cashflowStatementHistory"),
        "cashflowStatements",
    )
    # Yahoo a veces usa cashflowStatementHistory/cashflowStatements
    if not cashflows:
        cashflows = _statement_rows(
            yahoo_modules.get("cashflowStatementHistory"),
            "cashflowStatementHistory",
        )

    if len(balances) < 2 or len(incomes) < 2 or len(cashflows) < 1:
        return None, None

    return compute_piotroski_f(
        balance_curr=balances[0],
        balance_prev=balances[1],
        income_curr=incomes[0],
        income_prev=incomes[1],
        cashflow_curr=cashflows[0],
    )
