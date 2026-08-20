"""M-3 (T-M3) — puente de conciliación de cost-basis con fee en la cara unrealized.

Verifica ``open_positions_with_fee_basis``: el residual ABIERTO se deriva con la MISMA
máquina FIFO/avg que la cara realized, de modo que realized + unrealized concilian sobre
la misma base canónica (fee CAPITALIZADA de compra).

Decisión de usuario (iv — "puente"): el storage/``avg_cost`` de la posición sigue
fee-excluido; el cost-basis "con fee" es un valor DERIVADO solo para la conciliación
fiscal del report.
"""

from __future__ import annotations

import logging

import pytest

from bolsa_domain.tax_report import (
    TaxReportSummary,
    TaxReportTransaction,
    UnrealizedGainLine,
    _compute_realized_gains,
    build_tax_report,
    open_positions_with_fee_basis,
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


def _open(symbol: str, price: float) -> dict[str, float]:
    return {f"inst-{symbol}": price}


def test_fifo_buy_only_unrealized_with_fee() -> None:
    # buy 10@100 fee=5, sin venta → posición abierta qty=10, cost_basis=1005 (con fee),
    # avg_cost=100.5, market_value @120 = 1200, unrealized = 1200 - 1005 = 195.
    lines = open_positions_with_fee_basis(
        [
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        ],
        "fifo",
        _open("XYZ", 120),
    )
    assert len(lines) == 1
    line = lines[0]
    assert line.quantity == pytest.approx(10.0)
    assert line.cost_basis == pytest.approx(1005.0)
    assert line.avg_cost == pytest.approx(100.5)
    assert line.market_price == pytest.approx(120.0)
    assert line.market_value == pytest.approx(1200.0)
    assert line.unrealized_gain == pytest.approx(195.0)


def test_fifo_realized_plus_unrealized_concilian_misma_base() -> None:
    # buy 10@100 fee=5, sell 5@120 fee=3 → residual qty=5 con cost_basis CON fee = 502.5.
    # - FIFO realized de las 5 vendidas: cost_basis = (1005/10)*5 = 502.5, proceeds = 600-3 = 597,
    #   realized = +94.5.
    # - Unrealized (puente) de las 5 restantes: market_value = 5*120 = 600, unrealized = 600-502.5 = 97.5.
    # Conciliación sobre la MISMA base con fee: realized + unrealized = 502.5 + 502.5 = 1005 = coste
    # total con fee; y proceeds + market_value = 597 + 600 = 1197 (= 1200 - 3 fee_venta).
    tx = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-06-01T00:00:00Z", fee=3),
    ]
    realized = _compute_realized_gains(tx, "fifo")
    assert len(realized) == 1
    assert realized[0].cost_basis == pytest.approx(502.5)
    assert realized[0].proceeds == pytest.approx(597.0)
    assert realized[0].realized_gain == pytest.approx(94.5)

    lines = open_positions_with_fee_basis(tx, "fifo", _open("XYZ", 120))
    assert len(lines) == 1
    line = lines[0]
    assert line.quantity == pytest.approx(5.0)
    assert line.cost_basis == pytest.approx(502.5)
    assert line.avg_cost == pytest.approx(100.5)
    assert line.unrealized_gain == pytest.approx(97.5)

    # Paridad: realized (95.5? no: 94.5) + unrealized (97.5) sobre bases con fee que cierran
    # el coste total con fee (502.5 + 502.5 = 1005) → el par no se contradice.
    assert realized[0].cost_basis + line.cost_basis == pytest.approx(1005.0)
    assert realized[0].proceeds - realized[0].realized_gain == pytest.approx(502.5)
    assert realized[0].proceeds + line.market_value == pytest.approx(1197.0)


def test_average_buy_only_unrealized_with_fee() -> None:
    # average, buy 10@100 fee=5 → residual qty=10, total_cost con fee = 1005.
    lines = open_positions_with_fee_basis(
        [
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        ],
        "average",
        _open("XYZ", 120),
    )
    assert len(lines) == 1
    line = lines[0]
    assert line.quantity == pytest.approx(10.0)
    assert line.cost_basis == pytest.approx(1005.0)
    assert line.avg_cost == pytest.approx(100.5)
    assert line.unrealized_gain == pytest.approx(195.0)


def test_average_realized_plus_unrealized_concilian_misma_base() -> None:
    # average, buy 10@100 fee=5, sell 5@120 fee=3:
    # avg_cost = 1005/10 = 100.5; realized cost_basis = 100.5*5 = 502.5, proceeds = 597, realized = 94.5.
    # residual: total_cost = 1005 - 502.5 = 502.5, qty = 5 → unrealized = 600 - 502.5 = 97.5.
    tx = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-06-01T00:00:00Z", fee=3),
    ]
    realized = _compute_realized_gains(tx, "average")
    assert len(realized) == 1
    assert realized[0].cost_basis == pytest.approx(502.5)
    assert realized[0].proceeds == pytest.approx(597.0)
    assert realized[0].realized_gain == pytest.approx(94.5)

    lines = open_positions_with_fee_basis(tx, "average", _open("XYZ", 120))
    assert len(lines) == 1
    line = lines[0]
    assert line.quantity == pytest.approx(5.0)
    assert line.cost_basis == pytest.approx(502.5)
    assert line.unrealized_gain == pytest.approx(97.5)

    assert realized[0].cost_basis + line.cost_basis == pytest.approx(1005.0)
    assert realized[0].proceeds + line.market_value == pytest.approx(1197.0)


def test_gap_report_vs_storage_se_loguea_no_se_silencia(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # La cantidad residual del report (qty=5) NO coincide con la posición viva (qty=4):
    # el gap se loguea (risk gauge del puente M-3), sin inventar ni alterar el DTO.
    tx = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-06-01T00:00:00Z"),
    ]
    with caplog.at_level(logging.WARNING, logger="bolsa_domain.tax_report"):
        lines = open_positions_with_fee_basis(
            tx, "fifo", _open("XYZ", 120), live_quantities={"inst-XYZ": 4.0}
        )
    assert len(lines) == 1
    assert any(
        "M-3 gap report-vs-storage" in rec.message and "inst-XYZ" in rec.message
        for rec in caplog.records
    )


def test_no_gap_cuando_live_qty_coincide(caplog: pytest.LogCaptureFixture) -> None:
    # Si la cantidad viva coincide con el residual del método, NO se loguea ningún gap.
    tx = [
        _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        _tx(tx_id="s", typ="sell", symbol="XYZ", quantity=5, price=120, executed_at="2026-06-01T00:00:00Z"),
    ]
    with caplog.at_level(logging.WARNING, logger="bolsa_domain.tax_report"):
        open_positions_with_fee_basis(tx, "fifo", _open("XYZ", 120), live_quantities={"inst-XYZ": 5.0})
    assert not any("M-3 gap report-vs-storage" in rec.message for rec in caplog.records)


def test_no_price_leaves_unrealized_none() -> None:
    # Sin precio de mercado: market_value/unrealized permanecen None (no rompe el DTO).
    lines = open_positions_with_fee_basis(
        [
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        ],
        "fifo",
        {},
    )
    assert len(lines) == 1
    line = lines[0]
    assert line.cost_basis == pytest.approx(1005.0)
    assert line.market_price is None
    assert line.market_value is None
    assert line.unrealized_gain is None


# ── B-2 (T-M8) — total_unrealized_gain fail-closed con posiciones sin precio ──


def _summary_with_positions(
    transactions: list[TaxReportTransaction],
    prices: dict[str, float],
) -> tuple[TaxReportSummary, list[UnrealizedGainLine]]:
    positions = open_positions_with_fee_basis(transactions, "fifo", prices)
    return build_tax_report(
        account_id="acc-1",
        currency="EUR",
        method="fifo",
        jurisdiction="ES",
        year=2026,
        transactions=transactions,
        positions=positions,
    ), positions


def test_total_unrealized_gain_none_por_linea_sin_precio() -> None:
    # B-2: posición abierta sin precio de mercado → unrealized_gain None → el TOTAL pasa a
    # None (fail-closed, no silencia a 0). El FE lo muestra como "—" en lugar de un 0 real.
    report, positions = _summary_with_positions(
        [
            _tx(tx_id="b", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
        ],
        {},
    )
    assert len(positions) == 1
    assert positions[0].unrealized_gain is None
    assert report.total_unrealized_gain is None


def test_total_unrealized_gain_suma_cuando_todas_tienen_precio() -> None:
    # B-2 (regresión): todas las posiciones con precio → el total SÍ es la suma real.
    report, positions = _summary_with_positions(
        [
            _tx(tx_id="b1", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
            _tx(tx_id="b2", typ="buy", symbol="ABC", quantity=5, price=50, executed_at="2026-05-02T00:00:00Z"),
        ],
        _open("XYZ", 120) | _open("ABC", 60),
    )
    assert len(positions) == 2
    # XYZ: mv=1200, cost=1005 → 195. ABC: mv=300, cost=250 → 50. Total 245.
    assert report.total_unrealized_gain == pytest.approx(245.0)


def test_total_unrealized_gain_none_con_mixto_precio_y_sin_precio() -> None:
    # B-2: mezcla — una con precio y otra sin → total None (no suma solo las conocidas a 0).
    report, positions = _summary_with_positions(
        [
            _tx(tx_id="b1", typ="buy", symbol="XYZ", quantity=10, price=100, executed_at="2026-05-01T00:00:00Z", fee=5),
            _tx(tx_id="b2", typ="buy", symbol="ABC", quantity=5, price=50, executed_at="2026-05-02T00:00:00Z"),
        ],
        {"inst-XYZ": 120.0},
    )
    assert len(positions) == 2
    assert any(p.unrealized_gain is None for p in positions)
    assert report.total_unrealized_gain is None
