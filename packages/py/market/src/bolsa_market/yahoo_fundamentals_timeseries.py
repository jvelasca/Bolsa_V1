"""Yahoo fundamentals-timeseries → statements compatibles con quoteSummary.

Desde ~2025/26 `balanceSheetHistory` / cashflow anuales llegan vacíos (solo endDate).
La API `ws/fundamentals-timeseries` sigue exponiendo annual* con `reportedValue.raw`.

Este módulo rellena `balanceSheetHistory` / `cashflowStatementHistory` /
`incomeStatementHistory` (si llegan vacíos) en la forma que ya consumen
Piotroski / Beneish / Altman / ROIC.
"""

from __future__ import annotations

from typing import Any

# timeseries type → clave estilo quoteSummary statement
_BALANCE_MAP: dict[str, str] = {
    "annualTotalAssets": "totalAssets",
    "annualCurrentAssets": "totalCurrentAssets",
    "annualCurrentLiabilities": "totalCurrentLiabilities",
    "annualTotalLiabilitiesNetMinorityInterest": "totalLiab",
    "annualStockholdersEquity": "totalStockholderEquity",
    "annualCommonStockEquity": "commonStockEquity",
    "annualRetainedEarnings": "retainedEarnings",
    "annualLongTermDebt": "longTermDebt",
    "annualTotalDebt": "totalDebt",
    "annualOrdinarySharesNumber": "ordinarySharesNumber",
    "annualShareIssued": "ordinarySharesNumber",
    "annualNetPPE": "netPPE",
    "annualAccountsReceivable": "netReceivables",
    "annualReceivables": "netReceivables",
    "annualCashAndCashEquivalents": "cash",
    "annualCashCashEquivalentsAndShortTermInvestments": "cash",
}

_CASHFLOW_MAP: dict[str, str] = {
    "annualOperatingCashFlow": "totalCashFromOperatingActivities",
    "annualCashFlowFromContinuingOperatingActivities": "totalCashFromOperatingActivities",
    "annualDepreciationAndAmortization": "depreciationAndAmortization",
    "annualNetIncome": "netIncome",
}

_INCOME_MAP: dict[str, str] = {
    "annualEBIT": "ebit",
    "annualOperatingIncome": "operatingIncome",
    "annualGrossProfit": "grossProfit",
    "annualTotalRevenue": "totalRevenue",
    "annualNetIncome": "netIncome",
    "annualTaxProvision": "incomeTaxExpense",
    "annualPretaxIncome": "incomeBeforeTax",
    "annualSellingGeneralAndAdministration": "sellingGeneralAdministrative",
    "annualDepreciationAndAmortization": "depreciationAndAmortization",
}


def _is_empty_metric(node: Any) -> bool:
    """Yahoo a veces deja ebit={raw:0,fmt:null} u objetos vacíos."""
    if node is None:
        return True
    if isinstance(node, dict):
        if not node:
            return True
        raw = node.get("raw")
        fmt = node.get("fmt")
        if raw is None and fmt is None:
            return True
        if raw == 0 and fmt is None:
            return True
    return False


ALL_TIMESERIES_TYPES: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            *_BALANCE_MAP.keys(),
            *_CASHFLOW_MAP.keys(),
            *_INCOME_MAP.keys(),
        ]
    )
)


def _raw(n: float) -> dict[str, Any]:
    return {"raw": float(n), "fmt": str(n)}


def _series_points(block: dict[str, Any], type_key: str) -> list[tuple[str, float]]:
    """[(asOfDate, raw), ...] más reciente primero."""
    rows = block.get(type_key)
    if not isinstance(rows, list):
        return []
    out: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        as_of = row.get("asOfDate")
        reported = row.get("reportedValue") or {}
        raw = reported.get("raw") if isinstance(reported, dict) else None
        if not isinstance(as_of, str) or not isinstance(raw, (int, float)):
            continue
        out.append((as_of, float(raw)))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def parse_timeseries_payload(payload: dict[str, Any]) -> dict[str, list[tuple[str, float]]]:
    result = (payload.get("timeseries") or {}).get("result") or []
    series: dict[str, list[tuple[str, float]]] = {}
    if not isinstance(result, list):
        return series
    for block in result:
        if not isinstance(block, dict):
            continue
        meta = block.get("meta") or {}
        types = meta.get("type") if isinstance(meta, dict) else None
        type_keys = [t for t in (types or []) if isinstance(t, str)]
        if not type_keys:
            # a veces el bloque solo tiene la clave del type
            type_keys = [k for k in block if k not in {"meta", "timestamp"}]
        for tk in type_keys:
            pts = _series_points(block, tk)
            if pts:
                series[tk] = pts
    return series


def _statements_from_map(
    series: dict[str, list[tuple[str, float]]],
    field_map: dict[str, str],
    *,
    min_years: int = 2,
) -> list[dict[str, Any]]:
    # fechas unión (más recientes primero)
    dates: list[str] = []
    seen: set[str] = set()
    for ts_key in field_map:
        for as_of, _ in series.get(ts_key) or []:
            if as_of not in seen:
                seen.add(as_of)
                dates.append(as_of)
    dates.sort(reverse=True)
    if len(dates) < min_years:
        return []

    statements: list[dict[str, Any]] = []
    for as_of in dates[:4]:
        row: dict[str, Any] = {"endDate": {"fmt": as_of, "raw": as_of}}
        for ts_key, stmt_key in field_map.items():
            pts = series.get(ts_key) or []
            hit = next((v for d, v in pts if d == as_of), None)
            if hit is None:
                continue
            # no pisar si ya hay valor (p.ej. ordinarySharesNumber vs shareIssued)
            if stmt_key in row:
                continue
            row[stmt_key] = _raw(hit)
        statements.append(row)
    return statements


def enrich_modules_from_timeseries(
    modules: dict[str, Any] | None,
    timeseries_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fusiona timeseries en modules; no pisa statements que ya tengan campos útiles."""
    out = dict(modules or {})
    if not timeseries_payload:
        return out

    series = parse_timeseries_payload(timeseries_payload)
    if not series:
        return out

    def _needs_fill(container_key: str, list_key: str, required: str) -> bool:
        block = out.get(container_key)
        if not isinstance(block, dict):
            return True
        rows = block.get(list_key)
        if not isinstance(rows, list) or len(rows) < 2:
            return True
        first = rows[0] if isinstance(rows[0], dict) else {}
        return first.get(required) is None

    if _needs_fill("balanceSheetHistory", "balanceSheetStatements", "totalAssets"):
        bals = _statements_from_map(series, _BALANCE_MAP)
        if bals:
            out["balanceSheetHistory"] = {"balanceSheetStatements": bals}

    if _needs_fill("cashflowStatementHistory", "cashflowStatements", "totalCashFromOperatingActivities"):
        cfs = _statements_from_map(series, _CASHFLOW_MAP, min_years=1)
        if cfs:
            out["cashflowStatementHistory"] = {"cashflowStatements": cfs}

    # Income: reemplazo completo si vacío (como balance); si hay filas, solo parches.
    if _needs_fill("incomeStatementHistory", "incomeStatementHistory", "totalRevenue"):
        incomes_fill = _statements_from_map(series, _INCOME_MAP, min_years=2)
        if incomes_fill:
            out["incomeStatementHistory"] = {"incomeStatementHistory": incomes_fill}
    else:
        incomes_block = out.get("incomeStatementHistory")
        incomes = (
            incomes_block.get("incomeStatementHistory")
            if isinstance(incomes_block, dict)
            else None
        )
        if isinstance(incomes, list) and incomes:
            income_fill = _statements_from_map(series, _INCOME_MAP, min_years=1)
            by_date = {
                (r.get("endDate") or {}).get("fmt"): r
                for r in income_fill
                if isinstance(r.get("endDate"), dict)
            }
            for idx, row in enumerate(incomes):
                if not isinstance(row, dict):
                    continue
                end = row.get("endDate") or {}
                as_of = end.get("fmt") if isinstance(end, dict) else None
                extra = by_date.get(as_of) if as_of else None
                if extra is None and idx < len(income_fill):
                    extra = income_fill[idx]
                if not extra:
                    continue
                for k, v in extra.items():
                    if k == "endDate":
                        continue
                    if _is_empty_metric(row.get(k)):
                        row[k] = v

    return out
