"""FA point-in-time desde estados financieros Yahoo (DÍA D).

Persiste un ``statementPack`` ligero en ``profile_snapshot`` al refresh.
Con ``asOf`` en el pasado: filtra estados con endDate ≤ D, deriva ratios
desde balance/income/cashflow (sin TTM live de financialData) e inyecta
marketCap ≈ close×shares si hay precio as-of.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bolsa_market.instrument_fundamentals import (
    FUNDAMENTALS_SOURCE_VERSION,
    build_fundamentals_snapshot,
    compute_fcf_yield,
)

ASOF_SOURCE_VERSION = f"{FUNDAMENTALS_SOURCE_VERSION}_asof_statements_v1"

_STATEMENT_SPECS: tuple[tuple[str, str, str], ...] = (
    ("balanceSheetHistory", "balanceSheetStatements", "balanceSheetStatements"),
    ("incomeStatementHistory", "incomeStatementHistory", "incomeStatementHistory"),
    ("cashflowStatementHistory", "cashflowStatements", "cashflowStatementHistory"),
)


def statement_end_date(row: dict[str, Any] | None) -> str | None:
    if not isinstance(row, dict):
        return None
    end = row.get("endDate")
    if isinstance(end, dict):
        fmt = end.get("fmt")
        if isinstance(fmt, str) and len(fmt) >= 10:
            return fmt[:10]
        raw = end.get("raw")
        if isinstance(raw, (int, float)):
            # Yahoo epoch seconds
            try:
                return datetime.fromtimestamp(float(raw), tz=timezone.utc).date().isoformat()
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(raw, str) and len(raw) >= 10:
            return raw[:10]
    if isinstance(end, str) and len(end) >= 10:
        return end[:10]
    return None


def _num(node: Any) -> float | None:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict):
        raw = node.get("raw")
        if isinstance(raw, (int, float)):
            return float(raw)
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


def filter_statement_rows(
    rows: list[Any] | None,
    as_of: str,
) -> list[dict[str, Any]]:
    """Keep statements with endDate ≤ as_of, newest first (Yahoo order)."""
    cut = as_of[:10]
    kept: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        end = statement_end_date(row)
        if end is None or end > cut:
            continue
        kept.append(row)
    kept.sort(key=lambda r: statement_end_date(r) or "", reverse=True)
    return kept


def extract_statement_pack(yahoo_modules: dict[str, Any]) -> dict[str, Any]:
    """Compact pack to persist (histories + sector)."""
    profile = yahoo_modules.get("summaryProfile") or {}
    sector = profile.get("sector") if isinstance(profile, dict) else None
    pack: dict[str, Any] = {
        "schemaVersion": "fa_statement_pack_v1",
        "sector": sector.strip() if isinstance(sector, str) and sector.strip() else None,
    }
    for hist_key, primary_list, alt_list in _STATEMENT_SPECS:
        mod = yahoo_modules.get(hist_key)
        rows: list[Any] = []
        if isinstance(mod, dict):
            raw = mod.get(primary_list)
            if not isinstance(raw, list) or not raw:
                raw = mod.get(alt_list)
            if isinstance(raw, list):
                rows = [r for r in raw if isinstance(r, dict)]
        pack[hist_key] = rows
    return pack


def parse_statement_pack(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    pack = snapshot.get("statementPack")
    if not isinstance(pack, dict):
        return None
    if pack.get("schemaVersion") != "fa_statement_pack_v1":
        return None
    return pack


def _modules_from_pack(
    pack: dict[str, Any],
    as_of: str,
    *,
    close_price: float | None,
) -> dict[str, Any]:
    sector = pack.get("sector")
    modules: dict[str, Any] = {
        "summaryProfile": {"sector": sector} if sector else {},
        "summaryDetail": {},
        "financialData": {},
        "defaultKeyStatistics": {},
    }

    bals = filter_statement_rows(pack.get("balanceSheetHistory"), as_of)
    incs = filter_statement_rows(pack.get("incomeStatementHistory"), as_of)
    cfs = filter_statement_rows(pack.get("cashflowStatementHistory"), as_of)

    modules["balanceSheetHistory"] = {"balanceSheetStatements": bals}
    modules["incomeStatementHistory"] = {"incomeStatementHistory": incs}
    modules["cashflowStatementHistory"] = {"cashflowStatements": cfs}

    bal = bals[0] if bals else None
    inc = incs[0] if incs else None
    inc_prev = incs[1] if len(incs) > 1 else None
    cf = cfs[0] if cfs else None

    shares = _first(
        bal,
        "ordinarySharesNumber",
        "commonStock",
        "shareIssued",
    )
    total_debt = _first(bal, "totalDebt", "longTermDebt")
    total_cash = _first(bal, "cash", "cashAndCashEquivalents")
    equity = _first(bal, "totalStockholderEquity", "commonStockEquity", "stockholdersEquity")
    tca = _first(bal, "totalCurrentAssets")
    tcl = _first(bal, "totalCurrentLiabilities")
    revenue = _first(inc, "totalRevenue")
    op_inc = _first(inc, "operatingIncome", "ebit")
    net_income = _first(inc, "netIncome")
    revenue_prev = _first(inc_prev, "totalRevenue")
    ebitda = _first(inc, "ebitda", "operatingIncome")

    cfo = _first(
        cf,
        "totalCashFromOperatingActivities",
        "operatingCashflow",
        "cashFlowFromContinuingOperatingActivities",
    )
    capex = _first(cf, "capitalExpenditures", "purchaseOfPPE")
    fcf = None
    if cfo is not None:
        # Capex Yahoo often negative; FCF = CFO + capex (if capex signed) or CFO - |capex|
        if capex is None:
            fcf = cfo
        elif capex <= 0:
            fcf = cfo + capex
        else:
            fcf = cfo - capex

    financial: dict[str, Any] = {}
    if total_debt is not None:
        financial["totalDebt"] = {"raw": total_debt}
    if total_cash is not None:
        financial["totalCash"] = {"raw": total_cash}
    if tca is not None and tcl is not None and tcl > 0:
        financial["currentRatio"] = {"raw": tca / tcl}
    if total_debt is not None and equity is not None and equity > 0:
        financial["debtToEquity"] = {"raw": total_debt / equity}
    if op_inc is not None and revenue is not None and revenue > 0:
        financial["operatingMargins"] = {"raw": op_inc / revenue}
    if net_income is not None and revenue is not None and revenue > 0:
        financial["profitMargins"] = {"raw": net_income / revenue}
    if net_income is not None and equity is not None and equity > 0:
        financial["returnOnEquity"] = {"raw": net_income / equity}
    ta = _first(bal, "totalAssets")
    if net_income is not None and ta is not None and ta > 0:
        financial["returnOnAssets"] = {"raw": net_income / ta}
    if revenue is not None and revenue_prev is not None and revenue_prev > 0:
        financial["revenueGrowth"] = {"raw": (revenue - revenue_prev) / abs(revenue_prev)}
    if ebitda is not None:
        financial["ebitda"] = {"raw": ebitda}
    if fcf is not None:
        financial["freeCashflow"] = {"raw": fcf}
    if close_price is not None and close_price > 0:
        financial["currentPrice"] = {"raw": close_price}

    modules["financialData"] = financial

    detail: dict[str, Any] = {}
    if close_price is not None and shares is not None and shares > 0:
        mcap = close_price * shares
        detail["marketCap"] = {"raw": mcap}
        if net_income is not None and shares > 0:
            eps = net_income / shares
            modules["defaultKeyStatistics"] = {
                "trailingEps": {"raw": eps},
                "bookValue": (
                    {"raw": equity / shares} if equity is not None and shares > 0 else None
                ),
                "sharesOutstanding": {"raw": shares},
            }
            # drop None bookValue
            dks = {k: v for k, v in modules["defaultKeyStatistics"].items() if v is not None}
            modules["defaultKeyStatistics"] = dks
            if eps > 0:
                detail["trailingPE"] = {"raw": close_price / eps}
    elif shares is not None:
        modules["defaultKeyStatistics"] = {"sharesOutstanding": {"raw": shares}}

    modules["summaryDetail"] = detail
    return modules


def build_fundamentals_as_of_from_pack(
    pack: dict[str, Any] | None,
    as_of: str,
    *,
    close_price: float | None = None,
) -> dict[str, Any] | None:
    """Rebuild fundamentals snapshot usable as-of D. None if insufficient statements."""
    if not isinstance(pack, dict):
        return None
    cut = as_of[:10]
    bals = filter_statement_rows(pack.get("balanceSheetHistory"), cut)
    incs = filter_statement_rows(pack.get("incomeStatementHistory"), cut)
    if not bals and not incs:
        return None

    modules = _modules_from_pack(pack, cut, close_price=close_price)
    snap = build_fundamentals_snapshot(yahoo_modules=modules)
    # Vintage = D so as_of_cut treats as safe snapshot.
    snap["fetchedAt"] = f"{cut}T12:00:00+00:00"
    snap["sourceVersion"] = ASOF_SOURCE_VERSION
    snap["asOfDate"] = cut
    snap["asOfReconstructed"] = True
    # Ensure fcfYield if mcap+fcf present
    if snap.get("fcfYield") is None:
        snap["fcfYield"] = compute_fcf_yield(
            free_cashflow=snap.get("freeCashflow"),
            market_cap=snap.get("marketCap"),
        )
    return snap


RECONSTRUCTED_WARNING = (
    "FA as-of: reconstruida desde estados financieros ≤ DÍA D "
    "(sin TTM live Yahoo; marketCap vía precio×acciones si hay barra)."
)
