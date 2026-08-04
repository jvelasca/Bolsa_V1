"""Tests R4 — PDF digest mínimo."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from bolsa_infrastructure.alerts.daily_ops_digest_pdf import (
    build_daily_ops_digest_pdf,
    digest_pdf_filename,
)


def _bundle():
    account = SimpleNamespace(name="DEMO Beta")
    summary = SimpleNamespace(
        account=account,
        cash=5_000.0,
        total_equity=5_500.0,
        total_unrealized_pnl=100.0,
        positions_count=1,
    )
    trade = SimpleNamespace(
        type="sell",
        symbol="IBE",
        instrument_id="inst-ibe",
        quantity=5.0,
        amount=50.0,
    )
    return SimpleNamespace(
        as_of=date(2026, 8, 4),
        account_id="acc-2",
        summary=summary,
        trades_today=[trade],
        f3_pending_count=0,
        channels={"alarma": 0, "aviso": 1, "none": 0},
        opinions=[
            {
                "instrumentId": "inst-ibe",
                "symbol": "IBE",
                "channel": "aviso",
                "dictamenStars": 3,
            }
        ],
        week=[
            {
                "date": "2026-08-04",
                "tradeCount": 1,
                "ledgerCount": 1,
                "balanceAfter": 5050.0,
                "netAmount": 50.0,
            }
        ],
    )


def test_pdf_magic_and_filename() -> None:
    b = _bundle()
    pdf = build_daily_ops_digest_pdf(b)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf[-32:]
    assert b"DEMO Beta" in pdf or b"Resumen" in pdf
    assert digest_pdf_filename(b) == "bolsa-resumen-operativo-2026-08-04.pdf"
    assert len(pdf) > 400
