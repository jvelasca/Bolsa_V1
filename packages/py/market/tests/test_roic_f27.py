"""F2.7 — ROIC NOPAT / invested capital."""

from bolsa_market.roic import (
    ROIC_METHOD,
    compute_roic,
    compute_roic_from_parts,
    resolve_book_equity,
)


def _raw(n: float) -> dict:
    return {"raw": n, "fmt": str(n)}


def test_roic_basic():
    # NOPAT = 100*(1-0.21)=79; IC = 400+200-50=550 → 79/550
    roic, method = compute_roic(
        ebit=100.0,
        ebit_source="income_statement",
        book_equity=400.0,
        total_debt=200.0,
        total_cash=50.0,
        tax_rate=0.21,
    )
    assert method == ROIC_METHOD
    assert roic is not None
    assert abs(roic - 79 / 550) < 1e-6


def test_roic_null_without_income_ebit():
    assert compute_roic(
        ebit=100.0,
        ebit_source="financial_ebitda_proxy",
        book_equity=400.0,
        total_debt=200.0,
        total_cash=50.0,
        tax_rate=0.21,
    ) == (None, None)


def test_roic_null_negative_ic():
    assert compute_roic(
        ebit=100.0,
        ebit_source="income_statement",
        book_equity=10.0,
        total_debt=0.0,
        total_cash=50.0,
        tax_rate=0.21,
    ) == (None, None)


def test_book_equity_from_bvps():
    eq = resolve_book_equity(
        balance=None,
        book_value_per_share=20.0,
        shares_outstanding=1e6,
    )
    assert eq == 2e7


def test_bundle_from_parts():
    out = compute_roic_from_parts(
        income={"incomeTaxExpense": _raw(21), "incomeBeforeTax": _raw(100)},
        balance={"totalStockholderEquity": _raw(400)},
        ebit=100.0,
        ebit_source="income_statement",
        total_debt=200.0,
        total_cash=50.0,
        book_value_per_share=None,
        shares_outstanding=None,
    )
    assert out["roicMethod"] == ROIC_METHOD
    assert out["roicTaxSource"] == "income_ratio"
    assert out["roic"] is not None
