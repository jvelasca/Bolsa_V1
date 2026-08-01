"""Extracción numérica de fundamentales Yahoo (P12 → Cognitive FUND / FIE).

v3: + Altman Z desde balanceSheetHistory (+ EBIT/revenue de incomeStatement
o EBITDA/totalRevenue de financialData como fallback documentado).
v3.1: + fcfYield = freeCashflow / marketCap.
v3.2 / F2.1: + piotroski (9/9 o null) vía cashflowStatementHistory + YoY.
v3.3 / F2.3: + Graham Number + DCF FCF 2 etapas (valuation.py).
v3.4 / F2.6: + beta (CAPM) + averageVolume / advUsd (liquidez).
v3.5 / F2.7–F2.8: + roic + beneishM.

Regla FIE: ratios siempre aqui (Python); LLM solo explica.
Filings (SEC/RAG) viven fuera de este snapshot y no alimentan Score_FUND.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
@see docs/engineering/fa-status-and-test-plan-2026-07-31.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bolsa_market.beneish import compute_beneish_from_yahoo_modules
from bolsa_market.piotroski import compute_piotroski_from_yahoo_modules
from bolsa_market.roic import compute_roic_from_parts
from bolsa_market.valuation import compute_valuation_from_yahoo_fields

FUNDAMENTALS_SOURCE_VERSION = "yahoo_quote_summary_v3"


def compute_adv_usd(
    *,
    average_volume: float | None,
    price: float | None,
) -> float | None:
    """ADV ≈ averageVolume × price (USD notionals / día)."""
    if (
        average_volume is None
        or average_volume <= 0
        or price is None
        or price <= 0
    ):
        return None
    return round(float(average_volume) * float(price), 2)


def _numeric(node: Any) -> float | None:
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
            multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
            for suffix, factor in multipliers.items():
                if cleaned.endswith(suffix):
                    try:
                        return float(cleaned[:-1]) * factor
                    except ValueError:
                        return None
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _normalize_debt_to_equity(raw: float | None) -> float | None:
    """Yahoo a menudo reporta D/E×100 (p.ej. 151.5). Normalizamos a ratio."""
    if raw is None:
        return None
    if raw > 10.0:
        return raw / 100.0
    return raw


def compute_fcf_yield(*, free_cashflow: float | None, market_cap: float | None) -> float | None:
    """FCF Yield = FCF / marketCap (ratio, not percent)."""
    if free_cashflow is None or market_cap is None or market_cap <= 0:
        return None
    return round(free_cashflow / market_cap, 6)


def _latest_statement(module: dict[str, Any] | None, list_key: str) -> dict[str, Any] | None:
    if not isinstance(module, dict):
        return None
    rows = module.get(list_key)
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    return first if isinstance(first, dict) else None


def compute_altman_z(
    *,
    total_assets: float | None,
    total_current_assets: float | None,
    total_current_liabilities: float | None,
    retained_earnings: float | None,
    ebit: float | None,
    market_cap: float | None,
    total_liabilities: float | None,
    sales: float | None,
) -> tuple[float | None, str | None]:
    """
    Altman Z (manufacturing / público clásico):
      Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    """
    if (
        total_assets is None
        or total_assets <= 0
        or total_current_assets is None
        or total_current_liabilities is None
        or retained_earnings is None
        or ebit is None
        or market_cap is None
        or total_liabilities is None
        or total_liabilities <= 0
        or sales is None
    ):
        return None, None

    working_capital = total_current_assets - total_current_liabilities
    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = market_cap / total_liabilities
    x5 = sales / total_assets
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    return round(z, 4), "altman_z_classic_v1"


def _resolve_ebit_and_sales(
    *,
    income: dict[str, Any] | None,
    financial: dict[str, Any],
) -> tuple[float | None, float | None, str]:
    """Prefiere income statement; fallback financialData (EBITDA / totalRevenue)."""
    ebit = None
    sales = None
    source = "none"
    if income:
        ebit = _numeric(income.get("ebit") or income.get("operatingIncome"))
        sales = _numeric(income.get("totalRevenue"))
        if ebit is not None and sales is not None:
            return ebit, sales, "income_statement"
    # Fallback documentado: EBITDA ≈ EBIT (sesgo al alza)
    ebit_fb = _numeric(financial.get("ebitda"))
    sales_fb = _numeric(financial.get("totalRevenue"))
    if ebit_fb is not None and sales_fb is not None:
        return ebit_fb, sales_fb, "financial_ebitda_proxy"
    if ebit is not None and sales_fb is not None:
        return ebit, sales_fb, "mixed_income_financial"
    if ebit_fb is not None and sales is not None:
        return ebit_fb, sales, "mixed_financial_income"
    return ebit or ebit_fb, sales or sales_fb, source


def build_fundamentals_snapshot(*, yahoo_modules: dict[str, Any]) -> dict[str, Any]:
    profile = yahoo_modules.get("summaryProfile") or {}
    detail = yahoo_modules.get("summaryDetail") or {}
    financial = yahoo_modules.get("financialData") or {}
    stats = yahoo_modules.get("defaultKeyStatistics") or {}
    balance = _latest_statement(
        yahoo_modules.get("balanceSheetHistory"),
        "balanceSheetStatements",
    )
    income = _latest_statement(
        yahoo_modules.get("incomeStatementHistory"),
        "incomeStatementHistory",
    )

    sector = profile.get("sector")
    sector_str = str(sector).strip() if isinstance(sector, str) and sector.strip() else None

    debt_raw = _numeric(financial.get("debtToEquity"))
    if debt_raw is None:
        debt_raw = _numeric(stats.get("debtToEquity"))

    market_cap = _numeric(detail.get("marketCap"))
    free_cashflow = _numeric(financial.get("freeCashflow"))
    total_assets = _numeric(balance.get("totalAssets")) if balance else None
    total_current_assets = _numeric(balance.get("totalCurrentAssets")) if balance else None
    total_current_liabilities = (
        _numeric(balance.get("totalCurrentLiabilities")) if balance else None
    )
    retained_earnings = _numeric(balance.get("retainedEarnings")) if balance else None
    total_liabilities = _numeric(balance.get("totalLiab")) if balance else None

    ebit, sales, ebit_source = _resolve_ebit_and_sales(income=income, financial=financial)
    altman_z, altman_method = compute_altman_z(
        total_assets=total_assets,
        total_current_assets=total_current_assets,
        total_current_liabilities=total_current_liabilities,
        retained_earnings=retained_earnings,
        ebit=ebit,
        market_cap=market_cap,
        total_liabilities=total_liabilities,
        sales=sales,
    )

    piotroski, piotroski_method = compute_piotroski_from_yahoo_modules(yahoo_modules)
    beneish_m, beneish_method = compute_beneish_from_yahoo_modules(yahoo_modules)

    trailing_eps = _numeric(stats.get("trailingEps") or stats.get("epsTrailingTwelveMonths"))
    book_value_ps = _numeric(stats.get("bookValue"))
    shares_out = _numeric(
        stats.get("sharesOutstanding")
        or detail.get("sharesOutstanding")
        or (balance.get("ordinarySharesNumber") if balance else None)
    )
    total_debt = _numeric(financial.get("totalDebt"))
    total_cash = _numeric(financial.get("totalCash"))
    # Fallback: timeseries rellena balance.totalDebt/cash cuando financialData viene fino.
    if total_debt is None and balance:
        total_debt = _numeric(balance.get("totalDebt") or balance.get("longTermDebt"))
    if total_cash is None and balance:
        total_cash = _numeric(
            balance.get("cash")
            or balance.get("cashAndCashEquivalents")
            or balance.get("shortTermInvestments")
        )
    roic_bundle = compute_roic_from_parts(
        income=income,
        balance=balance,
        ebit=ebit,
        ebit_source=ebit_source,
        total_debt=total_debt,
        total_cash=total_cash,
        book_value_per_share=book_value_ps,
        shares_outstanding=shares_out,
    )
    beta = _numeric(stats.get("beta"))
    average_volume = _numeric(
        detail.get("averageVolume")
        or detail.get("averageDailyVolume10Day")
        or stats.get("averageVolume")
    )
    price = None
    if market_cap is not None and shares_out is not None and shares_out > 0:
        price = market_cap / shares_out
    if price is None:
        price = _numeric(
            detail.get("regularMarketPrice")
            or detail.get("previousClose")
            or financial.get("currentPrice")
        )
    adv_usd = compute_adv_usd(average_volume=average_volume, price=price)

    valuation = compute_valuation_from_yahoo_fields(
        market_cap=market_cap,
        free_cashflow=free_cashflow,
        revenue_growth=_numeric(financial.get("revenueGrowth")),
        trailing_pe=_numeric(detail.get("trailingPE")),
        trailing_eps=trailing_eps,
        book_value_per_share=book_value_ps,
        shares_outstanding=shares_out,
        sector=sector_str,
        beta=beta,
    )

    return {
        "marketCap": market_cap,
        "trailingPe": _numeric(detail.get("trailingPE")),
        "forwardPe": _numeric(detail.get("forwardPE")),
        "sector": sector_str,
        "roe": _numeric(financial.get("returnOnEquity")),
        "roa": _numeric(financial.get("returnOnAssets")),
        "operatingMargin": _numeric(financial.get("operatingMargins")),
        "profitMargin": _numeric(
            financial.get("profitMargins") or stats.get("profitMargins")
        ),
        "revenueGrowth": _numeric(financial.get("revenueGrowth")),
        "earningsGrowth": _numeric(financial.get("earningsGrowth")),
        "debtToEquity": _normalize_debt_to_equity(debt_raw),
        "currentRatio": _numeric(financial.get("currentRatio")),
        "quickRatio": _numeric(financial.get("quickRatio")),
        "totalCash": total_cash,
        "totalDebt": total_debt,
        "ebitda": _numeric(financial.get("ebitda")),
        "freeCashflow": free_cashflow,
        "fcfYield": compute_fcf_yield(free_cashflow=free_cashflow, market_cap=market_cap),
        "priceToBook": _numeric(stats.get("priceToBook")),
        "trailingEps": trailing_eps,
        "bookValuePerShare": book_value_ps,
        "sharesOutstanding": shares_out,
        "totalAssets": total_assets,
        "retainedEarnings": retained_earnings,
        "totalLiabilities": total_liabilities,
        "altmanZ": altman_z,
        "altmanMethod": altman_method,
        "altmanEbitSource": ebit_source if altman_z is not None else None,
        "piotroski": piotroski,
        "piotroskiMethod": piotroski_method,
        "beneishM": beneish_m,
        "beneishMethod": beneish_method,
        **roic_bundle,
        "averageVolume": average_volume,
        "advUsd": adv_usd,
        **valuation,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "sourceVersion": FUNDAMENTALS_SOURCE_VERSION,
    }


def parse_fundamentals_from_profile_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    fundamentals = snapshot.get("fundamentals")
    if isinstance(fundamentals, dict) and fundamentals.get("fetchedAt"):
        return fundamentals
    return None
