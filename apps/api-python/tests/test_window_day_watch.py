"""Tests del vigía diario de la ventana PAPER (v2.88.140).

Cubren la decisión PURA (``evaluate_day_watch``) por veredicto y el cableado del
aviso (``evaluate_once``) sin depender de red, SMTP ni PostgreSQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from bolsa_infrastructure.config import get_settings

from bolsa_api.background.window_day_watch_worker import (
    alert_recipient,
    evaluate_day_watch,
    evaluate_once,
    read_ledger_rows,
    start_window_day_watch,
)

MADRID = ZoneInfo("Europe/Madrid")
DUE_HOUR = 20
DUE_MINUTE = 0

#: Viernes 2026-10-16 20:30 Europe/Madrid — día laborable, ya vencida la hora del vigía.
_WEEKDAY_AFTER_DUE = datetime(2026, 10, 16, 20, 30, tzinfo=MADRID)
#: Sábado 2026-10-17 20:30 — fin de semana.
_WEEKEND = datetime(2026, 10, 17, 20, 30, tzinfo=MADRID)


def _row(day: str, status: str, reason: str | None = None) -> dict:
    return {"day": day, "status": status, "reason": reason}


def _decide(now: datetime, rows: list[dict], *, running: bool = False):
    return evaluate_day_watch(
        now=now, due_hour=DUE_HOUR, due_minute=DUE_MINUTE, rows=rows, running=running
    )


# ---------------------------------------------------------------------------
# Decisión pura
# ---------------------------------------------------------------------------


def test_weekend_is_non_market_day() -> None:
    watch = _decide(_WEEKEND, [_row("20261017", "MEDIDO")])
    assert watch.verdict == "NON_MARKET_DAY"
    assert watch.severity == "ok"


def test_not_due_before_hour() -> None:
    before = datetime(2026, 10, 16, 19, 0, tzinfo=MADRID)
    watch = _decide(before, [])
    assert watch.verdict == "NOT_DUE"
    assert watch.severity == "ok"


def test_running_suppresses_alert() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [], running=True)
    assert watch.verdict == "RUNNING"
    assert watch.severity == "info"


def test_missed_when_weekday_without_row() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [])
    assert watch.verdict == "MISSED"
    assert watch.severity == "alert"
    assert watch.reason == "ledger_sin_dia"


def test_measured_is_ok() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO")])
    assert watch.verdict == "OK"
    assert watch.severity == "ok"
    assert watch.status == "MEDIDO"


def test_veto_is_info_not_alert() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "NO_MEDIDO_REGIMEN", "regime_invalid")])
    assert watch.verdict == "VETO"
    assert watch.severity == "info"


def test_declared_is_info() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "DECLARADO", "sin_material")])
    assert watch.verdict == "DECLARED"
    assert watch.severity == "info"


def test_hard_error_is_alert() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "HARD_ERROR", "API_NOT_READY")])
    assert watch.verdict == "HARD_ERROR"
    assert watch.severity == "alert"
    assert watch.reason == "API_NOT_READY"


def test_unknown_status_is_declared_not_alert() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "ESTADO_RARO")])
    assert watch.verdict == "DECLARED"
    assert watch.severity == "info"


def test_latest_row_for_day_wins() -> None:
    rows = [_row("20261016", "HARD_ERROR"), _row("20261016", "MEDIDO")]
    assert _decide(_WEEKDAY_AFTER_DUE, rows).verdict == "OK"


def test_other_day_row_does_not_count_as_today() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261015", "MEDIDO")])
    assert watch.verdict == "MISSED"


# ---------------------------------------------------------------------------
# I/O read-only
# ---------------------------------------------------------------------------


def test_read_ledger_rows_ignores_corrupt_lines(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"day":"20261016"}\nno-es-json\n\n{"day":"20261015"}\n', encoding="utf-8")
    assert [row["day"] for row in read_ledger_rows(path)] == ["20261016", "20261015"]


def test_read_ledger_rows_missing_file_is_empty(tmp_path) -> None:
    assert read_ledger_rows(tmp_path / "nope.jsonl") == []


# ---------------------------------------------------------------------------
# Aviso (cableado) — nunca toca SMTP real
# ---------------------------------------------------------------------------


def test_alert_recipient_prefers_watcher_override() -> None:
    settings = SimpleNamespace(
        window_day_watch_email_to="vigia@x",
        estudio_opinion_email_to="estudio@x",
        smtp_user="user@x",
        smtp_from="from@x",
    )
    assert alert_recipient(settings) == "vigia@x"


def test_alert_recipient_falls_back_to_smtp_user() -> None:
    settings = SimpleNamespace(
        window_day_watch_email_to=None,
        estudio_opinion_email_to=None,
        smtp_user="user@x",
        smtp_from="from@x",
    )
    assert alert_recipient(settings) == "user@x"


def test_alert_recipient_empty_when_none_configured() -> None:
    settings = SimpleNamespace(
        window_day_watch_email_to=None,
        estudio_opinion_email_to=None,
        smtp_user=None,
        smtp_from=None,
    )
    assert alert_recipient(settings) == ""


@pytest.mark.asyncio
async def test_evaluate_once_alerts_missed_and_wires_email(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "bolsa_api.background.window_day_watch_worker.send_alert_email",
        lambda settings, watch: bool(sent.append(watch.verdict)) or False,
    )
    watch = await evaluate_once(
        now=_WEEKDAY_AFTER_DUE, rows=[], running=False, settings=get_settings()
    )
    assert watch.verdict == "MISSED"
    assert sent == ["MISSED"]


@pytest.mark.asyncio
async def test_evaluate_once_veto_does_not_alert(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "bolsa_api.background.window_day_watch_worker.send_alert_email",
        lambda settings, watch: bool(sent.append(watch.verdict)) or False,
    )
    watch = await evaluate_once(
        now=_WEEKDAY_AFTER_DUE,
        rows=[_row("20261016", "NO_MEDIDO_REGIMEN", "regime_invalid")],
        running=False,
        settings=get_settings(),
    )
    assert watch.verdict == "VETO"
    assert sent == []


@pytest.mark.asyncio
async def test_start_window_day_watch_disabled_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("WINDOW_DAY_WATCH_ENABLED", "0")
    assert start_window_day_watch() is None


@pytest.mark.asyncio
async def test_start_window_day_watch_enabled_creates_task(monkeypatch) -> None:
    monkeypatch.setenv("WINDOW_DAY_WATCH_ENABLED", "1")
    task = start_window_day_watch(tick_seconds=9999)
    assert task is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
