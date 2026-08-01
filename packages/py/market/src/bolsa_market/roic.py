"""FIE F2.7 — ROIC = NOPAT / Invested Capital (`roic_nopat_ic_v1`).

``NOPAT = EBIT × (1 − t)``
``IC = bookEquity + totalDebt − totalCash``

- EBIT solo de income statement (sin proxy EBITDA silencioso).
- ``t`` = taxExpense/pretax si ambos > 0; si no, proxy estatutario 21% (documentado).
- Null-if-incomplete (como Piotroski): falta input o IC ≤ 0 → null.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

from typing import Any

ROIC_METHOD = "roic_nopat_ic_v1"
ROIC_TAX_PROXY = 0.21


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


def resolve_book_equity(
    *,
    balance: dict[str, Any] | None,
    book_value_per_share: float | None,
    shares_outstanding: float | None,
) -> float | None:
    eq = _first(
        balance,
        "totalStockholderEquity",
        "stockholdersEquity",
        "commonStockEquity",
        "totalEquityGrossMinorityInterest",
    )
    if eq is not None:
        return eq
    if (
        book_value_per_share is not None
        and book_value_per_share > 0
        and shares_outstanding is not None
        and shares_outstanding > 0
    ):
        return book_value_per_share * shares_outstanding
    return None


def resolve_tax_rate(income: dict[str, Any] | None) -> tuple[float, str]:
    """Returns ``(rate, source)`` — ``income_ratio`` o ``statutory_proxy``."""
    tax = _first(income, "incomeTaxExpense", "taxProvision")
    pretax = _first(income, "incomeBeforeTax", "pretaxIncome", "earningsBeforeTax")
    if tax is not None and pretax is not None and pretax > 0 and tax >= 0:
        rate = tax / pretax
        if 0 <= rate <= 0.6:
            return rate, "income_ratio"
    return ROIC_TAX_PROXY, "statutory_proxy"


def compute_roic(
    *,
    ebit: float | None,
    ebit_source: str | None,
    book_equity: float | None,
    total_debt: float | None,
    total_cash: float | None,
    tax_rate: float,
) -> tuple[float | None, str | None]:
    """
    Returns ``(roic, method)``. Requiere EBIT de income statement.
    """
    if ebit_source != "income_statement" or ebit is None:
        return None, None
    if book_equity is None or total_debt is None or total_cash is None:
        return None, None
    if tax_rate < 0 or tax_rate >= 1:
        return None, None

    invested = float(book_equity) + float(total_debt) - float(total_cash)
    if invested <= 0:
        return None, None

    nopat = float(ebit) * (1.0 - float(tax_rate))
    return round(nopat / invested, 6), ROIC_METHOD


def compute_roic_from_parts(
    *,
    income: dict[str, Any] | None,
    balance: dict[str, Any] | None,
    ebit: float | None,
    ebit_source: str | None,
    total_debt: float | None,
    total_cash: float | None,
    book_value_per_share: float | None,
    shares_outstanding: float | None,
) -> dict[str, Any]:
    """Bundle for snapshot: roic, roicMethod, nopat, investedCapital, roicTaxRate."""
    equity = resolve_book_equity(
        balance=balance,
        book_value_per_share=book_value_per_share,
        shares_outstanding=shares_outstanding,
    )
    tax_rate, tax_source = resolve_tax_rate(income)
    roic, method = compute_roic(
        ebit=ebit,
        ebit_source=ebit_source,
        book_equity=equity,
        total_debt=total_debt,
        total_cash=total_cash,
        tax_rate=tax_rate,
    )
    invested = None
    nopat = None
    if (
        equity is not None
        and total_debt is not None
        and total_cash is not None
        and ebit is not None
        and ebit_source == "income_statement"
    ):
        invested_raw = float(equity) + float(total_debt) - float(total_cash)
        if invested_raw > 0:
            invested = round(invested_raw, 2)
            nopat = round(float(ebit) * (1.0 - float(tax_rate)), 2)

    return {
        "roic": roic,
        "roicMethod": method,
        "nopat": nopat if method else None,
        "investedCapital": invested if method else None,
        "roicTaxRate": round(tax_rate, 4) if method else None,
        "roicTaxSource": tax_source if method else None,
    }
