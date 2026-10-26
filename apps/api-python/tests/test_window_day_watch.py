"""Tests del vigía diario de la ventana PAPER (v2.88.140 · v2.88.142).

Cubren la decisión PURA (``evaluate_day_watch``), el arrastre de días perdidos
(``evaluate_backfill``), el latido durable (``write_status``) y el cableado del aviso
(``evaluate_once``/``_tick``/``main``) sin depender de red, SMTP ni PostgreSQL.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from bolsa_api.background import window_day_watch_worker as watch_worker
from bolsa_api.background.window_day_watch_worker import (
    ALERT_EXIT_CODE,
    DEFAULT_LOOKBACK_DAYS,
    alert_key,
    alert_recipient,
    announce_pending,
    default_lookback_days,
    evaluate_backfill,
    evaluate_day_watch,
    evaluate_once,
    main,
    read_alerted,
    read_ledger_rows,
    start_window_day_watch,
    write_status,
)
from bolsa_infrastructure.config import get_settings

MADRID = ZoneInfo("Europe/Madrid")
DUE_HOUR = 20
DUE_MINUTE = 0

#: Viernes 2026-10-16 20:30 Europe/Madrid — día laborable, ya vencida la hora del vigía.
_WEEKDAY_AFTER_DUE = datetime(2026, 10, 16, 20, 30, tzinfo=MADRID)
#: Sábado 2026-10-17 20:30 — fin de semana.
_WEEKEND = datetime(2026, 10, 17, 20, 30, tzinfo=MADRID)

#: W-1 — gate de un día que SÍ acredita material medible (lo que el runner publica).
_MEASURED_GATE = {"verdict": "READY", "cycles": 8}


def _row(day: str, status: str, reason: str | None = None, gate: dict | None = None) -> dict:
    row: dict = {"day": day, "status": status, "reason": reason}
    if gate is not None:
        row["gate"] = gate
    return row


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


def test_measured_with_measurable_cycles_is_ok() -> None:
    """Control positivo: ``MEDIDO`` + gate con ciclos medibles es un día ganado."""
    watch = _decide(
        _WEEKDAY_AFTER_DUE,
        [_row("20261016", "MEDIDO", gate=_MEASURED_GATE)],
    )
    assert watch.verdict == "OK"
    assert watch.severity == "ok"


def test_measured_without_a_gate_is_inconclusive() -> None:
    """W-1: sin gate no hay evidencia; ``MEDIDO`` a secas NO es un día ganado.

    Un ledger antiguo o uno cuya procedencia no se pudo verificar deja ``gate`` en
    ``None``. Publicar ``OK`` ahí convertiría la ausencia de evidencia en evidencia
    favorable.
    """
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO")])
    assert watch.verdict == "INCONCLUSIVE"
    assert watch.severity == "alert"
    assert watch.reason == "gate_missing"
    assert watch.status == "MEDIDO"


def test_measured_with_a_null_or_empty_gate_is_inconclusive() -> None:
    for gate in (None, {}):
        watch = _decide(
            _WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO", gate=gate)]
        )
        assert watch.verdict == "INCONCLUSIVE", gate
        assert watch.severity == "alert", gate


def test_measured_with_zero_cycles_and_inconclusive_gate_alerts() -> None:
    """W-1: un día ``MEDIDO`` sin ciclos medibles NO es un día ganado.

    Antes ``MEDIDO`` se mapeaba directo a ``OK`` y el caso que mantiene la ventana
    INCONCLUSIVE (0 ciclos) se publicaba como un día bueno.
    """
    watch = _decide(
        _WEEKDAY_AFTER_DUE,
        [_row("20261016", "MEDIDO", gate={"verdict": "INCONCLUSIVE", "cycles": 0})],
    )
    assert watch.verdict == "INCONCLUSIVE"
    assert watch.severity == "alert"
    assert watch.reason == "gate_inconclusive"
    assert watch.status == "MEDIDO"
    assert alert_key(watch) != alert_key(
        _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO", gate=_MEASURED_GATE)])
    )


def test_measured_with_inconclusive_gate_alerts_even_without_the_counter() -> None:
    """El verdicto del gate basta: no hace falta que el contador viaje en la fila."""
    watch = _decide(
        _WEEKDAY_AFTER_DUE,
        [_row("20261016", "MEDIDO", gate={"verdict": "INCONCLUSIVE"})],
    )
    assert watch.verdict == "INCONCLUSIVE"
    assert watch.severity == "alert"


def test_hard_error_wins_over_an_inconclusive_gate() -> None:
    """Control negativo: el HARD_ERROR no se disfraza de ``INCONCLUSIVE``."""
    watch = _decide(
        _WEEKDAY_AFTER_DUE,
        [
            _row(
                "20261016",
                "HARD_ERROR",
                "API_NOT_READY",
                gate={"verdict": "INCONCLUSIVE", "cycles": 0},
            )
        ],
    )
    assert watch.verdict == "HARD_ERROR"
    assert watch.severity == "alert"
    assert watch.reason == "API_NOT_READY"


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
    rows = [_row("20261016", "HARD_ERROR"), _row("20261016", "MEDIDO", gate=_MEASURED_GATE)]
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
async def test_start_window_day_watch_enabled_creates_task(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WINDOW_DAY_WATCH_ENABLED", "1")
    task = start_window_day_watch(tick_seconds=9999, directory=tmp_path)
    assert task is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# Arrastre de días perdidos (v2.88.142)
# ---------------------------------------------------------------------------

#: Viernes 2026-10-23 20:30 — el arrastre mira la semana laborable 19-22.
_FRIDAY_AFTER_DUE = datetime(2026, 10, 23, 20, 30, tzinfo=MADRID)


def test_backfill_reports_previous_weekdays_without_row() -> None:
    missed = evaluate_backfill(
        now=_FRIDAY_AFTER_DUE, rows=[_row("20261016", "MEDIDO")], lookback_days=7
    )
    assert [watch.day for watch in missed] == ["20261019", "20261020", "20261021", "20261022"]
    assert all(watch.verdict == "MISSED" and watch.severity == "alert" for watch in missed)
    assert all(watch.reason == "ledger_sin_dia_previo" for watch in missed)


def test_backfill_skips_weekend() -> None:
    monday = datetime(2026, 10, 19, 20, 30, tzinfo=MADRID)
    missed = evaluate_backfill(now=monday, rows=[_row("20261015", "MEDIDO")], lookback_days=4)
    assert [watch.day for watch in missed] == ["20261016"]  # 17=sábado y 18=domingo no cuentan


def test_backfill_does_not_invent_days_before_baseline() -> None:
    """Antes de la PRIMERA fila del ledger no había ventana: no se alerta de ese pasado."""
    missed = evaluate_backfill(
        now=_FRIDAY_AFTER_DUE, rows=[_row("20261016", "MEDIDO")], lookback_days=30
    )
    assert [watch.day for watch in missed] == ["20261019", "20261020", "20261021", "20261022"]


def test_backfill_empty_ledger_is_silent() -> None:
    assert evaluate_backfill(now=_FRIDAY_AFTER_DUE, rows=[], lookback_days=7) == []


def test_backfill_zero_days_is_off() -> None:
    assert (
        evaluate_backfill(
            now=_FRIDAY_AFTER_DUE, rows=[_row("20261016", "MEDIDO")], lookback_days=0
        )
        == []
    )


def test_backfill_ignores_days_with_row_and_today() -> None:
    rows = [_row("20261016", "MEDIDO"), _row("20261021", "NO_MEDIDO_REGIMEN")]
    missed = evaluate_backfill(now=_FRIDAY_AFTER_DUE, rows=rows, lookback_days=7)
    assert [watch.day for watch in missed] == ["20261019", "20261020", "20261022"]
    assert "20261023" not in [watch.day for watch in missed]


@pytest.mark.asyncio
async def test_evaluate_once_alerts_backfill_days_too(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "bolsa_api.background.window_day_watch_worker.send_alert_email",
        lambda settings, watch: bool(sent.append(watch.day)) or False,
    )
    watch = await evaluate_once(
        now=_FRIDAY_AFTER_DUE,
        rows=[_row("20261016", "MEDIDO")],
        running=False,
        settings=get_settings(),
        lookback_days=7,
    )
    assert watch.verdict == "MISSED"  # hoy (23) también falta
    assert sent == ["20261023", "20261019", "20261020", "20261021", "20261022"]


# ---------------------------------------------------------------------------
# Latido durable (v2.88.142) — el instrumento que prueba que el vigía vive
# ---------------------------------------------------------------------------


def test_write_status_writes_latido_and_journal(tmp_path: Path) -> None:
    checks = [_decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO", gate=_MEASURED_GATE)])]
    path = write_status(
        checks, now=_WEEKDAY_AFTER_DUE, lookback_days=7, source="test", directory=tmp_path
    )
    assert path == tmp_path / "day-watch.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["day"] == "20261016"
    assert payload["dayIso"] == "2026-10-16"
    assert payload["verdict"] == "OK"
    assert payload["severity"] == "ok"
    assert payload["alerts"] == []
    assert payload["lookbackDays"] == 7
    assert payload["source"] == "test"
    assert [check["day"] for check in payload["checks"]] == ["20261016"]

    journal = tmp_path / "day-watch.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["verdict"] == "OK"


def test_write_status_records_alerts(tmp_path: Path) -> None:
    missing_today = _decide(_FRIDAY_AFTER_DUE, [_row("20261016", "MEDIDO")])
    checks = [
        missing_today,
        *evaluate_backfill(
            now=_FRIDAY_AFTER_DUE, rows=[_row("20261016", "MEDIDO")], lookback_days=7
        ),
    ]
    write_status(checks, now=_FRIDAY_AFTER_DUE, lookback_days=7, directory=tmp_path)
    payload = json.loads((tmp_path / "day-watch.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "MISSED"
    assert payload["alerts"][0] == "20261023:MISSED"
    assert len(payload["alerts"]) == len(checks) == 5


def test_default_lookback_days_env_and_clamp(monkeypatch) -> None:
    monkeypatch.delenv("WINDOW_DAY_WATCH_LOOKBACK_DAYS", raising=False)
    assert default_lookback_days(get_settings()) == DEFAULT_LOOKBACK_DAYS
    monkeypatch.setenv("WINDOW_DAY_WATCH_LOOKBACK_DAYS", "0")
    assert default_lookback_days(get_settings()) == 0
    monkeypatch.setenv("WINDOW_DAY_WATCH_LOOKBACK_DAYS", "999")
    assert default_lookback_days(get_settings()) == watch_worker.MAX_LOOKBACK_DAYS
    monkeypatch.setenv("WINDOW_DAY_WATCH_LOOKBACK_DAYS", "no-es-entero")
    assert default_lookback_days(get_settings()) == DEFAULT_LOOKBACK_DAYS


# ---------------------------------------------------------------------------
# Marca durable de avisos — el dedupe sobrevive a los reinicios
# ---------------------------------------------------------------------------


def test_alert_key_is_day_and_verdict() -> None:
    watch = _decide(_WEEKDAY_AFTER_DUE, [_row("20261016", "MEDIDO", gate=_MEASURED_GATE)])
    assert alert_key(watch) == "20261016:OK"
    missed = _decide(_WEEKDAY_AFTER_DUE, [])
    assert alert_key(missed) == "20261016:MISSED"


def test_read_alerted_is_fail_open(tmp_path: Path) -> None:
    """Latido ausente, corrupto, o sin marcas ⇒ conjunto vacío (repetir antes que callar)."""
    assert read_alerted(tmp_path) == set()
    path = tmp_path / "day-watch.json"
    path.write_text("no-es-json", encoding="utf-8")
    assert read_alerted(tmp_path) == set()
    path.write_text('{"alerted": "no-es-lista"}', encoding="utf-8")
    assert read_alerted(tmp_path) == set()
    path.write_text('{"alerted": ["20261016:MISSED", 7, ""]}', encoding="utf-8")
    assert read_alerted(tmp_path) == {"20261016:MISSED"}


def test_read_alerted_migrates_the_previous_format(tmp_path: Path) -> None:
    """Un latido sin ``alerted`` adopta sus ``alerts``: el primer tick no reenvía lo ya visto."""
    (tmp_path / "day-watch.json").write_text(
        json.dumps({"alerts": ["20261020:MISSED", "20261023:MISSED"]}), encoding="utf-8"
    )
    assert read_alerted(tmp_path) == {"20261020:MISSED", "20261023:MISSED"}


@pytest.mark.asyncio
async def test_announce_pending_skips_known_keys(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker,
        "send_alert_email",
        lambda settings, watch: bool(sent.append(alert_key(watch))) or False,
    )
    checks = [_decide(_WEEKDAY_AFTER_DUE, [])]
    already = {"20261016:MISSED"}
    updated = await announce_pending(get_settings(), checks, already)
    assert sent == []  # ya constaba: no hay email
    assert updated == already

    updated_again = await announce_pending(get_settings(), checks, set())
    assert sent == ["20261016:MISSED"]
    assert updated_again == {"20261016:MISSED"}


@pytest.mark.asyncio
async def test_tick_writes_heartbeat_and_announces_once(monkeypatch, tmp_path: Path) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker, "send_alert_email", lambda settings, watch: bool(sent.append(watch.day)) or False
    )
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)

    cfg = get_settings()
    first = await watch_worker._tick(
        cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE
    )
    second = await watch_worker._tick(
        cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE
    )

    assert first.verdict == second.verdict == "MISSED"
    assert sent == ["20261016"]  # el aviso NO se repite en el segundo tick…
    journal = (tmp_path / "day-watch.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(journal) == 2  # …pero el latido sí se reescribe (prueba de vida)


@pytest.mark.asyncio
async def test_tick_dedupe_survives_a_restart(monkeypatch, tmp_path: Path) -> None:
    """La marca vive en el latido: un «reinicio» (sin estado en memoria) no reenvía.

    Regresión del ruido medido: ``_announced`` era un ``set`` en memoria y cada arranque del
    stack reenviaba el email del mismo día perdido.
    """
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker, "send_alert_email", lambda settings, watch: bool(sent.append(watch.day)) or False
    )
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)

    cfg = get_settings()
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)
    # «Reinicio»: no queda estado en memoria; la única memoria es el latido en disco.
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)

    assert sent == ["20261016"]
    assert read_alerted(tmp_path) == {"20261016:MISSED"}


@pytest.mark.asyncio
async def test_tick_reannounces_when_the_verdict_changes(monkeypatch, tmp_path: Path) -> None:
    """Un veredicto nuevo del mismo día SÍ avisa: la marca no silencia información nueva."""
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker, "send_alert_email", lambda settings, watch: bool(sent.append(watch.verdict)) or False
    )
    rows: list[dict] = []
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: rows)
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)

    cfg = get_settings()
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)
    rows.append(_row("20261016", "HARD_ERROR", "API_NOT_READY"))
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)

    assert sent == ["MISSED", "HARD_ERROR"]
    assert read_alerted(tmp_path) == {"20261016:MISSED", "20261016:HARD_ERROR"}


@pytest.mark.asyncio
async def test_failed_delivery_is_not_marked_as_announced(monkeypatch, tmp_path: Path) -> None:
    """Si la entrega falla, la marca NO se guarda: el siguiente tick reintenta."""
    attempts: list[str] = []

    def boom(settings, watch):
        attempts.append(watch.day)
        raise RuntimeError("smtp caído")

    monkeypatch.setattr(watch_worker, "send_alert_email", boom)
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)

    cfg = get_settings()
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)
    await watch_worker._tick(cfg, lookback_days=0, directory=tmp_path, now=_WEEKDAY_AFTER_DUE)

    assert attempts == ["20261016", "20261016"]
    assert read_alerted(tmp_path) == set()


# ---------------------------------------------------------------------------
# CLI autónomo (`pnpm window:watch`) — vigila sin el stack dev
# ---------------------------------------------------------------------------


def test_main_help_and_disabled(monkeypatch, capsys) -> None:
    assert main(["--help"]) == 0
    assert "Vigía diario" in capsys.readouterr().out

    monkeypatch.setenv("WINDOW_DAY_WATCH_ENABLED", "0")
    assert main([]) == 0
    assert "desactivado" in capsys.readouterr().out


def test_main_missed_exit_code_and_latido(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)
    monkeypatch.setattr(watch_worker, "send_alert_email", lambda settings, watch: False)

    code = main(["--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"])
    assert code == ALERT_EXIT_CODE
    payload = json.loads((tmp_path / "day-watch.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "MISSED"
    assert payload["severity"] == "alert"
    assert payload["alerts"] == ["20261016:MISSED"]
    assert payload["alerted"] == ["20261016:MISSED"]
    assert payload["source"] == "cli"


def test_main_does_not_repeat_the_email_across_runs(monkeypatch, tmp_path: Path) -> None:
    """Dos ejecuciones del CLI (la tarea de 20:20) ⇒ UN solo email, y exit 3 en ambas.

    Regresión del ruido: el CLI no consultaba la marca (``_announced``) y reenviaba el aviso
    del mismo día perdido en cada ejecución.
    """
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker,
        "send_alert_email",
        lambda settings, watch: bool(sent.append(alert_key(watch))) or False,
    )
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)

    first = main(["--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"])
    second = main(["--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"])

    assert first == second == ALERT_EXIT_CODE
    assert sent == ["20261016:MISSED"]
    payload = json.loads((tmp_path / "day-watch.json").read_text(encoding="utf-8"))
    assert payload["alerted"] == ["20261016:MISSED"]


def test_main_shares_the_mark_with_the_worker(monkeypatch, tmp_path: Path) -> None:
    """Lo que el worker ya avisó no lo repite el CLI (la marca es la misma)."""
    sent: list[str] = []
    monkeypatch.setattr(
        watch_worker,
        "send_alert_email",
        lambda settings, watch: bool(sent.append(alert_key(watch))) or False,
    )
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)
    write_status(
        [_decide(_WEEKDAY_AFTER_DUE, [])],
        now=_WEEKDAY_AFTER_DUE,
        source="worker",
        directory=tmp_path,
        alerted={"20261016:MISSED"},
    )

    assert main(["--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"]) == ALERT_EXIT_CODE
    assert sent == []


def test_main_veto_is_not_alert(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        watch_worker,
        "read_ledger_rows",
        lambda path: [_row("20261016", "NO_MEDIDO_REGIMEN", "regime_invalid")],
    )
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)

    assert main(["--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"]) == 0
    payload = json.loads((tmp_path / "day-watch.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "VETO"
    assert payload["alerts"] == []


def test_main_no_persist_writes_nothing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(watch_worker, "read_ledger_rows", lambda path: [])
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)
    monkeypatch.setattr(watch_worker, "send_alert_email", lambda settings, watch: False)

    main(["--now", "2026-10-16T20:30:00+02:00", "--no-persist"])
    assert not (tmp_path / "day-watch.json").exists()


def test_main_json_prints_payload(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        watch_worker,
        "read_ledger_rows",
        lambda path: [_row("20261016", "MEDIDO", gate=_MEASURED_GATE)],
    )
    monkeypatch.setattr(watch_worker, "day_is_running", lambda day: False)
    monkeypatch.setattr(watch_worker, "runs_dir", lambda: tmp_path)

    assert main(["--json", "--now", "2026-10-16T20:30:00+02:00", "--lookback-days", "0"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["verdict"] == "OK"
    assert (tmp_path / "day-watch.json").exists()
