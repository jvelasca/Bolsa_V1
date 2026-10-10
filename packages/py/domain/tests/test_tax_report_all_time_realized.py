"""F4 — P&L realizado AGREGADO (todo el historial) del resumen de cuenta.

``compute_all_time_realized_pnl`` reutiliza la máquina canónica de realized del tax report
(``_compute_realized_gains`` → FIFO/``average`` + semántica de fees) SIN el filtro de
ejercicio fiscal, de modo que concilia con ``net_realized_gain`` de un ejercicio que
contenga todas las ventas.
"""

from __future__ import annotations

import pytest

from bolsa_domain.tax_report import (
    TaxReportTransaction,
    build_tax_report,
    compute_all_time_realized_pnl,
)


def _tx(
    *,
    tx_id: str,
    typ: str,
    symbol: str,
    quantity: float,
    price: float,
    executed_at: str,
    fee: float = 0.0,
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
        fee_amount=fee,
    )


def _roundtrip() -> list[TaxReportTransaction]:
    # buy 10@100 fee=5, sell 5@120 fee=3 → FIFO: cost_basis = (1005/10)*5 = 502.5,
    # proceeds = 600-3 = 597 → realized = +94.5 (average da el mismo resultado).
    return [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100,
            executed_at="2025-05-01T00:00:00Z", fee=5),
        _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120,
            executed_at="2026-06-01T00:00:00Z", fee=3),
    ]


def test_roundtrip_fifo_realizado_agregado() -> None:
    assert compute_all_time_realized_pnl(
        transactions=_roundtrip(), method="fifo"
    ) == pytest.approx(94.5)


def test_roundtrip_average_realizado_agregado() -> None:
    assert compute_all_time_realized_pnl(
        transactions=_roundtrip(), method="average"
    ) == pytest.approx(94.5)


def test_sin_transacciones_es_cero_conocido() -> None:
    # Historial vacío → el realizado es genuinamente 0 (hecho conocido, no hueco).
    assert compute_all_time_realized_pnl(transactions=[], method="fifo") == 0.0


def test_solo_compras_es_cero_conocido() -> None:
    # Sin ventas no hay realizado: 0 conocido (no None), la posición sigue abierta.
    only_buys = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100,
            executed_at="2026-05-01T00:00:00Z", fee=5),
    ]
    assert compute_all_time_realized_pnl(
        transactions=only_buys, method="fifo"
    ) == 0.0


def test_concilia_con_net_realized_gain_de_un_ejercicio() -> None:
    # Todas las ventas caen en el ejercicio 2026 → el agregado all-time coincide
    # EXACTAMENTE con el net_realized_gain del tax report de ese año.
    tx = _roundtrip()
    all_time = compute_all_time_realized_pnl(transactions=tx, method="fifo")
    fees = {t.id: t.fee_amount for t in tx}
    report = build_tax_report(
        account_id="acc-1",
        currency="EUR",
        method="fifo",
        jurisdiction="ES",
        year=2026,
        transactions=tx,
        fees_by_transaction_id=fees,
    )
    assert report.net_realized_gain == pytest.approx(94.5)
    assert all_time == pytest.approx(report.net_realized_gain)


def test_historial_multi_anio_suma_todo_el_historial() -> None:
    # buy 10@100 (2024), sell 2@110 (2025, +20) y sell 3@130 (2026, +90):
    # el agregado all-time suma AMBOS ejercicios (110), no solo el último (90).
    tx = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100,
            executed_at="2024-01-01T00:00:00Z"),
        _tx(tx_id="s1", typ="sell", symbol="XYZ", quantity=2, price=110,
            executed_at="2025-06-01T00:00:00Z"),
        _tx(tx_id="s2", typ="sell", symbol="XYZ", quantity=3, price=130,
            executed_at="2026-06-01T00:00:00Z"),
    ]
    all_time = compute_all_time_realized_pnl(transactions=tx, method="fifo")
    assert all_time == pytest.approx(110.0)

    report_2026 = build_tax_report(
        account_id="acc-1",
        currency="EUR",
        method="fifo",
        jurisdiction="ES",
        year=2026,
        transactions=tx,
    )
    assert report_2026.net_realized_gain == pytest.approx(90.0)
    assert all_time != pytest.approx(report_2026.net_realized_gain)
