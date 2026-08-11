"""Tests R4 — PDF digest presentación (operativa diaria)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from bolsa_infrastructure.alerts.daily_ops_digest_pdf import (
    build_daily_ops_digest_pdf,
    digest_pdf_filename,
)


def _bundle(*, many_trades: bool = False):
    account = SimpleNamespace(name="DEMO Beta")
    summary = SimpleNamespace(
        account=account,
        cash=5_000.0,
        total_equity=5_500.0,
        total_unrealized_pnl=100.0,
        positions_count=2,
    )
    trades = [
        SimpleNamespace(
            type="sell",
            symbol="IBE",
            instrument_id="inst-ibe",
            quantity=5.0,
            amount=50.0,
            note="take profit",
        ),
        SimpleNamespace(
            type="buy",
            symbol="SAN",
            instrument_id="inst-san",
            quantity=10.0,
            amount=-120.0,
            note=None,
        ),
    ]
    if many_trades:
        for i in range(20):
            trades.append(
                SimpleNamespace(
                    type="buy" if i % 2 == 0 else "sell",
                    symbol=f"T{i}",
                    instrument_id=f"id-{i}",
                    quantity=1.0,
                    amount=10.0 * i,
                    note=None,
                )
            )
    week = []
    for i in range(29, 36):
        # 2026-07-29 … 2026-08-04 approx via iso strings
        d = f"2026-08-{i + 1:02d}"
        week.append(
            {
                "date": d,
                "tradeCount": i % 4,
                "ledgerCount": i % 4 + 1,
                "balanceAfter": 5000.0 + i * 25.0,
                "netAmount": float(i * 10),
            }
        )
    return SimpleNamespace(
        as_of=date(2026, 8, 4),
        account_id="acc-2",
        summary=summary,
        trades_today=trades,
        f3_pending_count=3,
        channels={"alarma": 1, "aviso": 2, "none": 0},
        opinions=[
            {
                "instrumentId": "inst-ibe",
                "symbol": "IBE",
                "channel": "aviso",
                "dictamenStars": 3,
                "stance": "hold",
            },
            {
                "instrumentId": "inst-san",
                "symbol": "SAN",
                "channel": "alarma",
                "dictamenStars": 5,
                "stance": "sell_bias",
            },
        ],
        week=week,
    )


def test_pdf_magic_and_filename() -> None:
    b = _bundle()
    pdf = build_daily_ops_digest_pdf(b)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf[-32:]
    assert b"Operativa diaria" in pdf or b"OPERATIVA" in pdf.upper() or b"Operativa" in pdf
    assert b"DEMO Beta" in pdf
    assert b"IBE" in pdf
    assert digest_pdf_filename(b) == "bolsa-resumen-operativo-2026-08-04.pdf"
    assert len(pdf) > 1200


def test_pdf_handles_empty_trades() -> None:
    b = _bundle()
    b.trades_today = []
    pdf = build_daily_ops_digest_pdf(b)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"Sin compras" in pdf or b"sin compras" in pdf.lower()


def test_pdf_many_trades_still_valid() -> None:
    b = _bundle(many_trades=True)
    pdf = build_daily_ops_digest_pdf(b)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"/Type /Page" in pdf or b"/Type /Page" in pdf.replace(b" ", b" ")
    # Helvetica-Bold presente
    assert b"Helvetica-Bold" in pdf
