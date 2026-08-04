"""Tests: HTML builder + prefs skip para digest operativo R3."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from bolsa_infrastructure.alerts.daily_ops_digest_email import (
    build_daily_ops_digest_html,
    build_daily_ops_digest_text,
    maybe_notify_daily_ops_digest,
)


def _bundle(**overrides):
    account = SimpleNamespace(name="DEMO Alpha")
    summary = SimpleNamespace(
        account=account,
        cash=10_000.0,
        total_equity=12_500.5,
        total_unrealized_pnl=250.5,
        positions_count=2,
    )
    trade = SimpleNamespace(
        type="buy",
        symbol="SAN",
        instrument_id="inst-san",
        quantity=10.0,
        amount=-100.0,
    )
    base = dict(
        as_of=date(2026, 8, 4),
        account_id="acc-1",
        summary=summary,
        trades_today=[trade],
        f3_pending_count=1,
        channels={"alarma": 1, "aviso": 2, "none": 0},
        opinions=[
            {
                "instrumentId": "inst-san",
                "symbol": "SAN",
                "channel": "alarma",
                "dictamenStars": 5,
            }
        ],
        week=[
            {
                "date": "2026-08-04",
                "tradeCount": 1,
                "ledgerCount": 1,
                "balanceAfter": 9900.0,
                "netAmount": -100.0,
            }
        ],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _settings(**kwargs):
    base = dict(
        daily_ops_digest_email_enabled=False,
        estudio_opinion_email_to=None,
        smtp_host=None,
        smtp_from=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_html_contains_kpis_and_escapes() -> None:
    html = build_daily_ops_digest_html(_bundle())
    assert "Resumen operativo" in html
    assert "DEMO Alpha" in html
    assert "12,500.50" in html or "12500.50" in html
    assert "SAN" in html
    assert "alarma" in html.lower()
    plain = build_daily_ops_digest_text(_bundle())
    assert "Trades hoy: 1" in plain
    assert "F3 pendiente: 1" in plain


@pytest.mark.asyncio
async def test_digest_disabled_skips() -> None:
    meta = await maybe_notify_daily_ops_digest(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        _bundle(),
        email_to="user@example.com",
        digest_enabled=False,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "digest_disabled"


@pytest.mark.asyncio
async def test_digest_missing_account_skips() -> None:
    meta = await maybe_notify_daily_ops_digest(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        None,
        email_to="user@example.com",
        digest_enabled=True,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "sin_account_id"


@pytest.mark.asyncio
async def test_digest_smtp_missing() -> None:
    meta = await maybe_notify_daily_ops_digest(
        _settings(),
        _bundle(),
        email_to="user@example.com",
        digest_enabled=True,
    )
    assert meta["sent"] is False
    assert "SMTP" in (meta["skipped_reason"] or "")
