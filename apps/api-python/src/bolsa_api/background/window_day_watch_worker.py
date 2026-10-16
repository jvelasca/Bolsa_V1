"""V2.88.140 — vigía diario de la ventana PAPER (alerta de «día perdido»).

La operación diaria de la ventana PAPER (ADR-046) exige **un ``run-day`` por día de
mercado** (preflight → forward → journal → ventana → auditoría): el cubo de calendario
sale del **reloj de pared** (``sim_fill_finance_context.created_at``), así que un día no
ejecutado es un día **perdido** para el gate ``>=4 días / >=2 episodios / >=32 ciclos``.
Hasta ahora **nada avisaba** si ese día no se corría: ni el scheduler ni la tarea de
Windows emitían señal, de modo que un fallo silencioso podía costar días de ventana sin
que nadie se enterara (hallazgo declarado al instalar la cadencia diaria).

Este worker CIERRA ese hueco desde el proceso dedicado de crons
(``bolsa_api.workers.scheduler_worker``): una vez por día laborable, **después** de la
hora del ``run-day``, lee el **ledger del runner** y decide —de forma pura y falsable—
si el día se ejecutó. Si **no** consta (``MISSED``) o quedó en ``HARD_ERROR``, AVISA:
log estructurado ``ALERTA`` **siempre** y email por el canal SMTP ya existente cuando
está configurado (nunca en silencio).

Reglas duras:

* **On-by-default** (``WINDOW_DAY_WATCH_ENABLED``; se apaga con ``0/false/no/off``): un
  aviso de día perdido no puede depender de una variable ausente.
* **No toca la ventana.** Sólo LEE el ledger y el lock del día; jamás escribe en el
  journal, ni lanza ``run-day``, ni fuerza el régimen, ni cambia umbrales ni pesos A/B.
  ``Δ motor = 0``; ``Δ decisión = 0``.
* **Un veto NO es una alerta.** ``NO_MEDIDO_REGIMEN`` (p. ej. ``BEAR_TREND``) es una
  declaración **legítima** de mercado: se registra como INFO, no dispara aviso.
* **Honestidad de hueco.** Un día sin fila en el ledger es ``MISSED`` (alerta), nunca un
  ``OK`` fabricado; un ledger ilegible/ausente no se inventa.
* **Fail-safe por tick**: un error del tick se registra y NO mata el bucle.
* **Idempotente por día**: una única evaluación por fecha local (guard en proceso).

@see scripts/window-forward-runner.mjs (ledger del día + lock ``.run.lock``)
@see docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from bolsa_infrastructure.config import Settings, get_settings

logger = logging.getLogger(__name__)

MADRID = ZoneInfo("Europe/Madrid")
#: Cadencia del bucle (la evaluación real es una vez al día; el tick sólo la dispara).
CHECK_INTERVAL_SECONDS = 15 * 60
_ENV_ENABLED = "WINDOW_DAY_WATCH_ENABLED"
_ENV_LEDGER_PATH = "WINDOW_LEDGER_PATH"

WindowDayVerdict = Literal[
    "NOT_DUE",
    "NON_MARKET_DAY",
    "RUNNING",
    "OK",
    "VETO",
    "DECLARED",
    "HARD_ERROR",
    "MISSED",
]
Severity = Literal["ok", "info", "alert"]

#: Estados terminales del ledger del runner → veredicto/severidad del vigía.
_STATUS_VERDICT: dict[str, tuple[WindowDayVerdict, Severity]] = {
    "MEDIDO": ("OK", "ok"),
    "NO_MEDIDO_REGIMEN": ("VETO", "info"),
    "DECLARADO": ("DECLARED", "info"),
    "HARD_ERROR": ("HARD_ERROR", "alert"),
}

_STATUS_MESSAGE: dict[WindowDayVerdict, str] = {
    "OK": "MEDIDO: la ventana avanzó un día de calendario",
    "VETO": "veto de régimen declarado (NO_MEDIDO_REGIMEN): no es alerta",
    "DECLARED": "declarado sin material medible (DECLARADO): no es alerta",
    "HARD_ERROR": "HARD_ERROR: el día requiere atención",
}


@dataclass(frozen=True, slots=True)
class WindowDayWatch:
    """Veredicto del vigía para un día. Cada campo tiene una fuente dura (ledger/reloj)."""

    verdict: WindowDayVerdict
    severity: Severity
    day: str
    day_iso: str
    status: str | None
    reason: str | None
    message: str


def day_stamp(moment: datetime) -> str:
    """Sello ``YYYYMMDD`` (mismo formato que las carpetas del runner)."""
    return moment.strftime("%Y%m%d")


def evaluate_day_watch(
    *,
    now: datetime,
    due_hour: int,
    due_minute: int,
    rows: Sequence[Mapping[str, Any]],
    running: bool,
) -> WindowDayWatch:
    """Evalúa el día (PURA): reloj y datos se INYECTAN (sin I/O, sin BD, sin red).

    Orden de precedencia (primero gana): fin de semana → no vencido → en curso →
    estado del ledger. ``MISSED`` sólo cuando es día laborable, ya venció la hora y el
    ledger no tiene fila **y** no hay run en curso.
    """
    day = day_stamp(now)
    iso = now.strftime("%Y-%m-%d")

    def make(
        kind: WindowDayVerdict,
        severity: Severity,
        *,
        status: str | None = None,
        reason: str | None = None,
        message: str = "",
    ) -> WindowDayWatch:
        return WindowDayWatch(kind, severity, day, iso, status, reason, message)

    if now.weekday() >= 5:
        return make("NON_MARKET_DAY", "ok", message="fin de semana: no es día de mercado")

    if (now.hour, now.minute) < (int(due_hour), int(due_minute)):
        return make("NOT_DUE", "ok", message="aún no vence la hora del run-day")

    if running:
        return make("RUNNING", "info", message="run-day del día en curso (lock vivo)")

    latest: Mapping[str, Any] | None = None
    for row in rows:
        if str(row.get("day") or "").strip() == day:
            latest = row  # el ledger anexa: la última fila del día gana
    if latest is None:
        return make(
            "MISSED",
            "alert",
            reason="ledger_sin_dia",
            message=(
                f"el día {iso} NO se ejecutó: no consta en el ledger del runner "
                "(¿la cadencia diaria no corrió?)"
            ),
        )

    status = str(latest.get("status") or "").strip() or None
    reason = str(latest.get("reason") or "").strip() or None
    mapped = _STATUS_VERDICT.get(status or "")
    if mapped is None:
        return make(
            "DECLARED",
            "info",
            status=status,
            reason=reason,
            message=f"día {iso} con estado no reconocido: {status or 'n/d'} (declarado)",
        )
    kind, severity = mapped
    detail = _STATUS_MESSAGE.get(kind, f"día {iso}: {status}")
    if reason:
        detail = f"{detail} ({reason})"
    return make(kind, severity, status=status, reason=reason, message=f"día {iso} · {detail}")


# ---------------------------------------------------------------------------
# Lectura del ledger y del lock del día (I/O, read-only)
# ---------------------------------------------------------------------------


def repo_root() -> Path | None:
    """Raíz del repo (marcador: ``scripts/lib/window-forward.mjs``) o ``None``."""
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / "scripts" / "lib" / "window-forward.mjs").exists():
            return parent
    return None


def ledger_path() -> Path | None:
    """Ruta del ledger del runner (override por ``WINDOW_LEDGER_PATH``)."""
    override = (os.getenv(_ENV_LEDGER_PATH) or "").strip()
    if override:
        return Path(override)
    root = repo_root()
    if root is None:
        return None
    return root / "operability_runs" / "window-runs" / "ledger.jsonl"


def read_ledger_rows(path: Path | None) -> list[Mapping[str, Any]]:
    """Filas del ledger (JSONL). Ausente/ilegible ⇒ ``[]`` (nunca se inventa)."""
    if path is None or not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[Mapping[str, Any]] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue  # fila corrupta: se ignora
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def day_is_running(day: str) -> bool:
    """¿Hay un ``run-day`` en curso para ``day``? (lock presente ⇒ en curso).

    Conservador a propósito: el runner libera el lock en un ``try/finally``, de modo que
    un lock presente señala un run **arrancado**; se prefiere callar a avisar en falso
    mientras el ``run-day`` aún no ha anexado su fila al ledger.
    """
    root = repo_root()
    if root is None:
        return False
    lock_dir = root / "operability_runs" / "window-runs" / day / ".run.lock"
    return lock_dir.exists()


# ---------------------------------------------------------------------------
# Aviso (log + email por el canal SMTP existente)
# ---------------------------------------------------------------------------


def alert_recipient(settings: Settings) -> str:
    """Destinatario del aviso: overrides del vigía → digest estudio → cuenta SMTP."""
    for candidate in (
        getattr(settings, "window_day_watch_email_to", None),
        getattr(settings, "estudio_opinion_email_to", None),
        getattr(settings, "smtp_user", None),
        getattr(settings, "smtp_from", None),
    ):
        value = (candidate or "").strip()
        if value:
            return value
    return ""


def send_alert_email(settings: Settings, watch: WindowDayWatch) -> bool:
    """Envía el aviso por SMTP si está configurado. ``False`` si no hay canal (no es error)."""
    from bolsa_infrastructure.alerts.estudio_opinion_email import (
        _send_smtp_message,
        smtp_ready,
    )

    if not smtp_ready(settings):
        return False
    recipient = alert_recipient(settings)
    if not recipient:
        return False

    message = EmailMessage()
    message["Subject"] = f"[Bolsa] ALERTA ventana PAPER · {watch.day_iso} · {watch.verdict}"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        "Vigía diario de la ventana PAPER (ADR-046).\n\n"
        f"{watch.message}\n\n"
        f"día: {watch.day} ({watch.day_iso})\n"
        f"veredicto: {watch.verdict}\n"
        f"estado del ledger: {watch.status or 'n/d'}\n"
        f"motivo: {watch.reason or 'n/d'}\n\n"
        "Acción sugerida: `pnpm window:status` y, si procede, `pnpm window:run-day`.\n"
        "Este aviso NO cambia la ventana: sólo informa (no baja umbrales ni fuerza régimen).\n"
    )
    _send_smtp_message(settings, message)
    return True


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def evaluate_once(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    running: bool | None = None,
) -> WindowDayWatch:
    """Evalúa el día y, si procede, AVISA (log siempre; email si está configurado)."""
    cfg = settings or get_settings()
    moment = now or datetime.now(MADRID)
    watch = evaluate_day_watch(
        now=moment,
        due_hour=int(getattr(cfg, "window_day_watch_hour", 20)),
        due_minute=int(getattr(cfg, "window_day_watch_minute", 0)),
        rows=read_ledger_rows(ledger_path()) if rows is None else rows,
        running=day_is_running(day_stamp(moment)) if running is None else running,
    )

    if watch.severity == "alert":
        logger.error(
            "ALERTA VENTANA PAPER · %s (%s): %s",
            watch.verdict,
            watch.reason or "n/d",
            watch.message,
        )
        sent = False
        try:
            sent = await asyncio.to_thread(send_alert_email, cfg, watch)
        except Exception:
            logger.exception("ventana PAPER: fallo enviando el aviso por email")
        if not sent:
            logger.warning(
                "ventana PAPER: aviso %s sin email (SMTP/destinatario no configurado); "
                "el aviso queda registrado en el log",
                watch.verdict,
            )
    else:
        logger.info("vigía ventana PAPER · %s: %s", watch.verdict, watch.message)
    return watch


_last_eval_day: str | None = None


async def window_day_watch_loop(
    *, tick_seconds: float | None = None, settings: Settings | None = None
) -> None:
    global _last_eval_day

    cfg = settings or get_settings()
    interval = float(tick_seconds) if tick_seconds is not None else float(CHECK_INTERVAL_SECONDS)
    logger.info(
        "WindowDayWatch iniciado (tick=%ss; hora=%02d:%02d Europe/Madrid)",
        interval,
        int(getattr(cfg, "window_day_watch_hour", 20)),
        int(getattr(cfg, "window_day_watch_minute", 0)),
    )
    while True:
        await asyncio.sleep(interval)
        if not _worker_enabled():
            continue
        now = datetime.now(MADRID)
        if _last_eval_day == day_stamp(now):
            continue
        try:
            watch = await evaluate_once(now=now, settings=cfg)
            if watch.verdict != "NOT_DUE":
                _last_eval_day = day_stamp(now)
        except Exception:
            logger.exception("vigía ventana PAPER: tick falló (se reintenta el siguiente)")


def start_window_day_watch(
    session_factory: object = None,
    *,
    tick_seconds: float | None = None,
    settings: Settings | None = None,
) -> asyncio.Task[None] | None:
    """Arranca el vigía (``session_factory`` ignorado: el vigía no usa BD). Default ON."""
    if not _worker_enabled():
        logger.info("WindowDayWatch desactivado (%s=false)", _ENV_ENABLED)
        return None
    return asyncio.create_task(window_day_watch_loop(tick_seconds=tick_seconds, settings=settings))


__all__ = [
    "CHECK_INTERVAL_SECONDS",
    "WindowDayWatch",
    "alert_recipient",
    "day_is_running",
    "day_stamp",
    "evaluate_day_watch",
    "evaluate_once",
    "ledger_path",
    "read_ledger_rows",
    "repo_root",
    "send_alert_email",
    "start_window_day_watch",
    "window_day_watch_loop",
]
