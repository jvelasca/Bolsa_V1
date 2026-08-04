"""Tests: prefs UI override vs flags servidor para email Alarmas."""

from types import SimpleNamespace

import pytest

from bolsa_infrastructure.alerts.estudio_opinion_email import maybe_notify_estudio_alarmas


def _settings(**kwargs):
    base = dict(
        estudio_opinion_email_enabled=False,
        estudio_opinion_email_to=None,
        smtp_host=None,
        smtp_from=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _alarma_row():
    return SimpleNamespace(
        instrument_id="inst-1",
        stance="buy",
        dictamen_stars=5,
        as_of_bar_date="2026-08-04",
        reasons=["test"],
    )


@pytest.mark.asyncio
async def test_client_prefs_disabled_skips() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        [_alarma_row()],
        email_to="user@example.com",
        email_enabled=False,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "email_disabled"
    assert meta["alarma_count"] == 1


@pytest.mark.asyncio
async def test_client_prefs_empty_email_skips() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(smtp_host="smtp.example", smtp_from="a@b.c"),
        [_alarma_row()],
        email_to="",
        email_enabled=True,
    )
    assert meta["sent"] is False
    assert meta["skipped_reason"] == "email_to vacío"


@pytest.mark.asyncio
async def test_client_prefs_smtp_missing() -> None:
    meta = await maybe_notify_estudio_alarmas(
        _settings(),
        [_alarma_row()],
        email_to="user@example.com",
        email_enabled=True,
    )
    assert meta["sent"] is False
    assert "SMTP" in (meta["skipped_reason"] or "")
