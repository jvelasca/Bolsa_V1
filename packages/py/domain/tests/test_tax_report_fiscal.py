"""F-FIN-2 — integridad fiscal: rango de ejercicio, FIFO cross-year y fees del año.

Cubre los cambios de F-FIN-2:
- `fiscal_year_range` es la fuente canónica del rango SQL del ejercicio fiscal.
- `build_tax_report.fees_paid_total` suma SOLO fees del año pedido (antes sumaba todas).
- El carry-in (compras de ejercicios anteriores) NO se rompe al acotar transacciones.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_domain.tax_report import (
    TaxReportSummary,
    TaxReportTransaction,
    build_tax_report,
    fiscal_year_range,
)


def _tx(
    *,
    tx_id: str,
    typ: str,
    symbol: str,
    quantity: float,
    price: float,
    executed_at: str,
) -> TaxReportTransaction:
    return TaxReportTransaction(
        id=tx_id,
        type=typ,
        instrument_id=f"inst-{symbol}",
        symbol=symbol,
        quantity=quantity,
        price=price,
        total=quantity * price,
        executed_at=executed_at,
    )


def test_fiscal_year_range_natural_year() -> None:
    start, end = fiscal_year_range(2026, 1)
    assert start == datetime(2026, 1, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


def test_fiscal_year_range_desfasado_no_natural() -> None:
    # Ejercicio 2024 con start=9 → [2024-09-01, 2025-09-01). Una transacción de
    # 2025-mar (mes < 9) es calendar_year == year+1 → SÍ pertenece al ejercicio 2024.
    start, end = fiscal_year_range(2024, 9)
    assert start == datetime(2024, 9, 1, tzinfo=UTC)
    assert end == datetime(2025, 9, 1, tzinfo=UTC)


def _build_one_year(
    *,
    year: int,
    transactions: list[TaxReportTransaction],
    start_month: int = 1,
    fees_by_tx: dict[str, float] | None = None,
) -> TaxReportSummary:
    return build_tax_report(
        account_id="acc-1",
        currency="EUR",
        method="fifo",
        jurisdiction="ES",
        year=year,
        transactions=transactions,
        fees_by_transaction_id=fees_by_tx,
        fiscal_year_start_month=start_month,
    )


def test_fees_paid_total_solo_suma_fees_del_anio() -> None:
    # En el pathway real las fees llegan vía ledger (fees_by_transaction_id); aqui se
    # simulan igual: b/s del 2026 con fee, c del 2025 (carry-in) con fee.
    fees_by_tx = {"b": 5.0, "s": 2.0, "c": 7.0}
    report = _build_one_year(
        year=2026,
        transactions=[
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z"),
            _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-06-01T00:00:00Z"),
            # Carry-in de 2025 (año anterior) con fee que NO pertenece al ejercicio 2026.
            _tx(tx_id="c", typ="buy", symbol="ABC", quantity=10, price=10, executed_at="2025-04-01T00:00:00Z"),
        ],
        start_month=1,
        fees_by_tx=fees_by_tx,
    )
    # fees_paid_total debe ser solo las del 2026 (5 + 2), NO la del carry-in de 2025 (7).
    assert report.fees_paid_total == pytest.approx(7.0)


def test_fifo_carry_in_cross_year_no_rompe_cost_basis() -> None:
    # Compra el 2025 (ejercicio anterior), venta el 2026: el cost basis de la venta
    # de 2026 debe venir de la compra previa, aunque la compra quede "fuera" del año.
    report = _build_one_year(
        year=2026,
        transactions=[
            _tx(tx_id="buy2025", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2025-06-01T00:00:00Z"),
            _tx(tx_id="sell2026", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-02-01T00:00:00Z"),
        ],
        start_month=1,
    )
    lines = [line for line in report.realized_lines if line.sell_transaction_id == "sell2026"]
    assert len(lines) == 1
    line = lines[0]
    assert line.cost_basis == pytest.approx(5 * 100.0)
    assert line.realized_gain == pytest.approx((120 - 100) * 5.0)


def test_fifo_buy_quantity_zero_no_divide_by_zero_ni_lote() -> None:
    # Buy con quantity == 0 dentro del FIFO: no puede lanzar ZeroDivisionError, no
    # debe fabricar un lote (ni basis ni quantity) y el sell debe consumir SOLO el
    # lote válido, con el realized esperado.
    report = _build_one_year(
        year=2026,
        transactions=[
            _tx(tx_id="zero", typ="buy", symbol="XYZ", quantity=0, price=100, executed_at="2026-01-01T00:00:00Z"),
            _tx(tx_id="valid", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-02-01T00:00:00Z"),
            _tx(tx_id="sell", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-03-01T00:00:00Z"),
        ],
        start_month=1,
    )
    lines = [line for line in report.realized_lines if line.sell_transaction_id == "sell"]
    assert len(lines) == 1
    line = lines[0]
    assert line.cost_basis == pytest.approx(5 * 100.0)
    assert line.realized_gain == pytest.approx((120 - 100) * 5.0)


def test_realized_lines_filtradas_por_anio_desfasado() -> None:
    # Ejercicio 2024 start=9: la venta de 2025-mar pertenece al ejercicio 2024,
    # la venta de 2025-oct al ejercicio 2025.
    report = _build_one_year(
        year=2024,
        transactions=[
            _tx(tx_id="a", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2024-10-01T00:00:00Z"),
            _tx(tx_id="s2025mar", typ="sell", symbol="XYZ", quantity=4, price=110, executed_at="2025-03-01T00:00:00Z"),
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=6, price=100, executed_at="2025-10-01T00:00:00Z"),
            _tx(tx_id="s2025oct", typ="sell", symbol="XYZ", quantity=3, price=100, executed_at="2025-11-01T00:00:00Z"),
        ],
        start_month=9,
    )
    sell_ids = {line.sell_transaction_id for line in report.realized_lines}
    assert sell_ids == {"s2025mar"}
