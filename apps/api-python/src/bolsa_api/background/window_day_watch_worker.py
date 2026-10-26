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

V2.88.142 — **«vigía 2.0»: vigilancia VERIFICABLE e independiente del stack** (hallazgo
declarado en ``v2.88.140``: el vigía sólo emitía log —y el log del stack dev NO captura los
loggers ``bolsa_api.*``—, de modo que su vigilancia era **indemostrable desde fuera**; además
sólo miraba el día de HOY, así que un día perdido con el equipo apagado no se avisaba nunca).

Tres piezas nuevas, sin tocar la ventana:

* **Latido durable** (``operability_runs/window-runs/day-watch.json`` + ``day-watch.jsonl``):
  cada tick deja por escrito el veredicto del día, los días comprobados y las alertas. Es el
  **instrumento** que hace falsable «está vigilando» sin depender de logs ni de emails.
* **Arrastre de días perdidos** (``WINDOW_DAY_WATCH_LOOKBACK_DAYS``, default ``7``): además de
  hoy, revisa los días laborables **anteriores** al último día del ledger y avisa de los que
  faltan (equipo apagado, stack caído, tarea no disparada).
* **CLI autónomo** (``python -m bolsa_api.background.window_day_watch_worker --once`` →
  ``pnpm window:watch`` + tarea programada ``BolsaV1_WindowWatch``): evalúa y avisa **sin el
  stack dev**, de modo que la vigilancia no depende de que el API esté levantado.

Reglas duras:

* **On-by-default** (``WINDOW_DAY_WATCH_ENABLED``; se apaga con ``0/false/no/off``): un
  aviso de día perdido no puede depender de una variable ausente.
* **No toca la ventana.** Sólo LEE el ledger y el lock del día; jamás escribe en el
  journal ni en el ledger, ni lanza ``run-day``, ni fuerza el régimen, ni cambia umbrales ni
  pesos A/B. Su única escritura es su **propio** fichero de latido. ``Δ motor = 0``;
  ``Δ decisión = 0``.
* **Un veto NO es una alerta.** ``NO_MEDIDO_REGIMEN`` (p. ej. ``BEAR_TREND``) es una
  declaración **legítima** de mercado: se registra como INFO, no dispara aviso.
* **Honestidad de hueco.** Un día sin fila en el ledger es ``MISSED`` (alerta), nunca un
  ``OK`` fabricado; un ledger ilegible/ausente no se inventa, y el arrastre **no alerta del
  pasado anterior a la primera fila** (baseline): en un ledger vacío no hay días perdidos que
  declarar.
* **Fail-safe por tick**: un error del tick se registra y NO mata el bucle.
* **Idempotente por aviso, con marca DURABLE**: cada par ``(día, veredicto)``
  se anuncia **una sola vez**, y la marca se persiste en el latido (``alerted``) — de modo
  que sobrevive a los reinicios del proceso y la comparte el CLI. Antes el dedupe vivía en
  memoria: cada arranque del stack (y cada ``pnpm window:watch``, que no deduplicaba nada)
  reenviaba el email del mismo día perdido, y el aviso se volvía ruido. El latido sí se
  reescribe en cada tick, para poder probar que el vigía vive.

@see scripts/window-forward-runner.mjs (ledger del día + lock ``.run.lock`` + ``--watch``)
@see docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
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
_ENV_LOOKBACK_DAYS = "WINDOW_DAY_WATCH_LOOKBACK_DAYS"

#: Arrastre por defecto (días naturales hacia atrás). ``0`` desactiva el arrastre.
DEFAULT_LOOKBACK_DAYS = 7
#: Tope defensivo del arrastre (no tiene sentido revisar más atrás que la ventana).
MAX_LOOKBACK_DAYS = 90
#: Latido durable (instrumento de vigilancia): último veredicto + journal de latidos.
STATUS_FILE = "day-watch.json"
STATUS_JOURNAL = "day-watch.jsonl"
#: Código de salida del CLI cuando el día (o un día del arrastre) requiere atención.
ALERT_EXIT_CODE = 3

WindowDayVerdict = Literal[
    "NOT_DUE",
    "NON_MARKET_DAY",
    "RUNNING",
    "OK",
    "VETO",
    "DECLARED",
    "INCONCLUSIVE",
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
    # W-1 (verificación 2026-10-26 §8): un día ``MEDIDO`` cuyo gate no tiene episodios
    # medibles NO es un día ganado para la ventana, aunque el runner lo anote como medido.
    "INCONCLUSIVE": (
        "MEDIDO sin ciclos medibles / gate INCONCLUSIVE: el día no cuenta para la ventana"
    ),
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


def alert_key(watch: WindowDayWatch) -> str:
    """Clave DURABLE de aviso: ``(día evaluado, veredicto)``.

    Un mismo par se anuncia **una sola vez**, aunque el proceso se reinicie o lo evalúe el
    CLI. Si el veredicto del día cambia (p. ej. ``MISSED`` → ``HARD_ERROR``), la clave cambia
    y vuelve a avisar: la marca no silencia información nueva.
    """
    return f"{watch.day}:{watch.verdict}"


def _gate_is_inconclusive(gate: Any) -> bool:
    """W-1 — ¿el gate del día acredita material medible?

    Un día ``MEDIDO`` **no** acredita nada por sí solo: lo que acredita es su gate. La
    ausencia de gate (ledger antiguo, ``null`` o bloque vacío) es AUSENCIA DE EVIDENCIA y
    no puede presentarse como evidencia favorable: devuelve ``True`` (no acredita). Sólo
    un ``verdict`` declarado y distinto de ``INCONCLUSIVE`` —sin un contador de ciclos en
    cero que lo contradiga— o un contador positivo sin veredicto lo acreditan.
    """
    if not isinstance(gate, Mapping):
        return True
    verdict = str(gate.get("verdict") or "").strip().upper()
    if verdict == "INCONCLUSIVE":
        return True
    saw_counter = False
    for key in ("cycles", "measurableCycles", "measurable_cycles"):
        if key not in gate:
            continue
        value = gate.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            saw_counter = True
            if value <= 0:
                return True
    if verdict:
        return False
    return not saw_counter


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
    # W-1 (verificación 2026-10-26 §8) — ``MEDIDO`` no es sinónimo de día ganado: si el
    # gate del día no tiene ciclos medibles (``INCONCLUSIVE``/``cycles=0``) el día NO
    # cuenta para la ventana y hay que avisar. Antes el mapeo directo ``MEDIDO → OK``
    # silenciaba exactamente el caso que mantiene la ventana INCONCLUSIVE.
    if kind == "OK" and _gate_is_inconclusive(latest.get("gate")):
        gate = latest.get("gate")
        detail = (
            "MEDIDO sin gate verificable: la ausencia de evidencia no acredita el día"
            if not isinstance(gate, Mapping)
            else _STATUS_MESSAGE["INCONCLUSIVE"]
        )
        return make(
            "INCONCLUSIVE",
            "alert",
            status=status,
            reason="gate_inconclusive" if isinstance(gate, Mapping) else "gate_missing",
            message=f"día {iso} · {detail}",
        )
    detail = _STATUS_MESSAGE.get(kind, f"día {iso}: {status}")
    if reason:
        detail = f"{detail} ({reason})"
    return make(kind, severity, status=status, reason=reason, message=f"día {iso} · {detail}")


def evaluate_backfill(
    *,
    now: datetime,
    rows: Sequence[Mapping[str, Any]],
    lookback_days: int,
) -> list[WindowDayWatch]:
    """Días laborables **anteriores** sin fila en el ledger (PURA; ``lookback_days`` atrás).

    Cubre el hueco que el vigía de hoy no ve: si a las 20:00 el equipo estaba apagado o el
    stack caído, al día siguiente el veredicto de HOY ya no mira el día perdido. El arrastre
    lo declara ``MISSED`` igual que el día corriente.

    **Baseline (anti-falso-positivo):** sólo se miran días **posteriores a la primera fila**
    del ledger; con el ledger vacío no se declara ningún día perdido (no se inventa pasado
    anterior a la puesta en marcha de la ventana). Fin de semana nunca es día perdido.
    """
    span = max(0, min(int(lookback_days), MAX_LOOKBACK_DAYS))
    if span <= 0:
        return []
    known = {str(row.get("day") or "").strip() for row in rows}
    known.discard("")
    if not known:
        return []
    baseline = min(known)

    today = now.date()
    missed: list[WindowDayWatch] = []
    for offset in range(1, span + 1):
        day_date = today - timedelta(days=offset)
        if day_date.weekday() >= 5:
            continue
        day = day_date.strftime("%Y%m%d")
        if day <= baseline or day in known:
            continue
        iso = day_date.isoformat()
        missed.append(
            WindowDayWatch(
                verdict="MISSED",
                severity="alert",
                day=day,
                day_iso=iso,
                status=None,
                reason="ledger_sin_dia_previo",
                message=(
                    f"el día {iso} NO se ejecutó: no consta en el ledger del runner "
                    "(¿la cadencia diaria no corrió, el equipo estaba apagado o el stack caído?)"
                ),
            )
        )
    return sorted(missed, key=lambda watch: watch.day)


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
# Latido durable (instrumento de vigilancia: probar que el vigía está vivo)
# ---------------------------------------------------------------------------


def runs_dir() -> Path | None:
    """Carpeta de la ventana (``operability_runs/window-runs``) o ``None``."""
    root = repo_root()
    return None if root is None else root / "operability_runs" / "window-runs"


def status_path(directory: Path | None = None) -> Path | None:
    """Ruta del latido (``day-watch.json``) o ``None`` si no hay repo."""
    base = directory or runs_dir()
    return None if base is None else base / STATUS_FILE


def status_journal_path(directory: Path | None = None) -> Path | None:
    """Ruta del journal de latidos (``day-watch.jsonl``) o ``None`` si no hay repo."""
    base = directory or runs_dir()
    return None if base is None else base / STATUS_JOURNAL


def default_lookback_days(settings: Settings | None = None) -> int:
    """Días de arrastre (``WINDOW_DAY_WATCH_LOOKBACK_DAYS`` → settings → 7), acotado."""
    raw = (os.getenv(_ENV_LOOKBACK_DAYS) or "").strip()
    value: int | None = None
    if raw:
        try:
            value = int(raw)
        except ValueError:
            logger.warning(
                "ventana PAPER: %s=%r no es un entero; se usa %s",
                _ENV_LOOKBACK_DAYS,
                raw,
                DEFAULT_LOOKBACK_DAYS,
            )
    if value is None:
        fallback = getattr(settings, "window_day_watch_lookback_days", DEFAULT_LOOKBACK_DAYS)
        value = int(fallback or 0)
    return max(0, min(value, MAX_LOOKBACK_DAYS))


def status_payload(
    checks: Sequence[WindowDayWatch],
    *,
    now: datetime,
    lookback_days: int,
    source: str,
    alerted: Collection[str] | None = None,
) -> dict[str, Any]:
    """Payload del latido (falsable y estable para leer desde fuera).

    ``alerted`` es la marca **durable** de avisos ya emitidos: sin ella el dedupe moría con
    el proceso y cada reinicio del stack reenviaba el mismo correo.
    """
    today = next((check for check in checks if check.day == day_stamp(now)), None)
    return {
        "at": now.isoformat(),
        "day": day_stamp(now),
        "dayIso": now.strftime("%Y-%m-%d"),
        "verdict": today.verdict if today is not None else "SIN_EVALUAR",
        "severity": today.severity if today is not None else "info",
        "status": today.status if today is not None else None,
        "reason": today.reason if today is not None else None,
        "message": today.message if today is not None else "",
        "alerts": [f"{check.day}:{check.verdict}" for check in checks if check.severity == "alert"],
        "alerted": sorted(alerted or ()),
        "checks": [
            {
                "day": check.day,
                "verdict": check.verdict,
                "severity": check.severity,
                "reason": check.reason,
            }
            for check in checks
        ],
        "lookbackDays": int(lookback_days),
        "source": source,
    }


def write_status(
    checks: Sequence[WindowDayWatch],
    *,
    now: datetime,
    lookback_days: int = 0,
    source: str = "worker",
    directory: Path | None = None,
    alerted: Collection[str] | None = None,
) -> Path | None:
    """Escribe el latido (``day-watch.json`` + línea en ``day-watch.jsonl``).

    Best-effort: un fallo de escritura se registra y NO tumba al vigía (el aviso por log y
    email es independiente). Devuelve la ruta escrita o ``None``. ``alerted`` es la marca
    durable de avisos ya emitidos (ver ``read_alerted``).
    """
    path = status_path(directory)
    journal = status_journal_path(directory)
    if path is None or journal is None:
        logger.warning("ventana PAPER: sin raíz de repo; no se pudo escribir el latido")
        return None
    body = json.dumps(
        status_payload(
            checks,
            now=now,
            lookback_days=lookback_days,
            source=source,
            alerted=alerted,
        ),
        ensure_ascii=False,
        sort_keys=True,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{body}\n", encoding="utf-8")
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(f"{body}\n")
    except OSError:
        logger.exception("ventana PAPER: no se pudo escribir el latido en %s", path)
        return None
    return path


def read_alerted(directory: Path | None = None) -> set[str]:
    """Claves ``(día:veredicto)`` ya anunciadas, leídas del latido.

    Best-effort y **fail-open**: un latido ausente, ilegible o sin marcas devuelve un conjunto
    vacío, de modo que el peor caso es repetir un aviso — nunca silenciarlo por un fichero
    corrupto.

    Migración declarada: un latido del **formato anterior** (sin ``alerted``) ya se escribió
    por un proceso que anunció sus ``alerts``; se adoptan como marca para que el primer tick
    tras el despliegue no reenvíe lo mismo que el usuario ya recibió. El tradeoff se declara:
    si aquel email falló, no se reintenta (quedó la línea ``ALERTA`` en el log).
    """
    path = status_path(directory)
    if path is None or not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    raw = payload.get("alerted")
    if not isinstance(raw, list):
        raw = payload.get("alerts")
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if isinstance(item, str) and item.strip()}


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


async def _announce(settings: Settings, watch: WindowDayWatch) -> bool:
    """Avisa de un veredicto: log SIEMPRE; email sólo si es alerta y hay canal.

    Devuelve ``True`` si el aviso quedó emitido por su canal (email enviado, o log cuando no
    hay canal configurado) y ``False`` si la entrega **falló**: en ese caso NO se marca como
    anunciado, para que el siguiente tick lo reintente.
    """
    if watch.severity != "alert":
        logger.info("vigía ventana PAPER · %s: %s", watch.verdict, watch.message)
        return True
    logger.error(
        "ALERTA VENTANA PAPER · %s (%s): %s",
        watch.verdict,
        watch.reason or "n/d",
        watch.message,
    )
    sent = False
    try:
        sent = await asyncio.to_thread(send_alert_email, settings, watch)
    except Exception:
        logger.exception("ventana PAPER: fallo enviando el aviso por email")
        return False
    if not sent:
        logger.warning(
            "ventana PAPER: aviso %s sin email (SMTP/destinatario no configurado); "
            "el aviso queda registrado en el log",
            watch.verdict,
        )
    return True


async def announce_pending(
    settings: Settings,
    checks: Sequence[WindowDayWatch],
    already: Collection[str],
) -> set[str]:
    """Avisa sólo de los ``(día, veredicto)`` que no constan en ``already``.

    Devuelve el conjunto actualizado de marcas. La persistencia la decide el llamante (el
    latido en el bucle, y el mismo latido en el CLI): así el dedupe **sobrevive a los
    reinicios** y lo comparten el worker y ``pnpm window:watch``. Un fallo de entrega no
    añade la marca, de modo que no se pierde el aviso.
    """
    pending = set(already)
    for watch in checks:
        if watch.verdict == "NOT_DUE":
            continue
        key = alert_key(watch)
        if key in pending:
            continue
        if await _announce(settings, watch):
            pending.add(key)
    return pending


async def evaluate_all(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    running: bool | None = None,
    lookback_days: int | None = None,
    persist: bool = False,
    directory: Path | None = None,
    source: str = "worker",
    announce: bool = True,
) -> list[WindowDayWatch]:
    """Evalúa HOY + el arrastre de días perdidos y AVISA de cada veredicto.

    Devuelve los veredictos (hoy primero). ``persist=True`` escribe el latido durable y
    ``announce=False`` deja el aviso al llamante (que es quien deduplica contra la marca
    ``alerted`` del latido vía ``announce_pending``). La forma «todo de golpe» con
    ``announce=True`` se conserva para usos puntuales y tests.
    """
    cfg = settings or get_settings()
    moment = now or datetime.now(MADRID)
    due_hour = int(getattr(cfg, "window_day_watch_hour", 20))
    due_minute = int(getattr(cfg, "window_day_watch_minute", 0))
    ledger = read_ledger_rows(ledger_path()) if rows is None else rows
    span = default_lookback_days(cfg) if lookback_days is None else int(lookback_days)

    today = evaluate_day_watch(
        now=moment,
        due_hour=due_hour,
        due_minute=due_minute,
        rows=ledger,
        running=day_is_running(day_stamp(moment)) if running is None else running,
    )
    checks: list[WindowDayWatch] = [
        today,
        *evaluate_backfill(now=moment, rows=ledger, lookback_days=span),
    ]
    if announce:
        for watch in checks:
            await _announce(cfg, watch)
    if persist:
        write_status(checks, now=moment, lookback_days=span, source=source, directory=directory)
    return checks


async def evaluate_once(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    running: bool | None = None,
    lookback_days: int | None = None,
    persist: bool = False,
    directory: Path | None = None,
    source: str = "worker",
    announce: bool = True,
) -> WindowDayWatch:
    """Veredicto de HOY (y aviso del arrastre). Compatibilidad con el contrato previo."""
    checks = await evaluate_all(
        now=now,
        settings=settings,
        rows=rows,
        running=running,
        lookback_days=lookback_days,
        persist=persist,
        directory=directory,
        source=source,
        announce=announce,
    )
    return checks[0]


async def _tick(
    cfg: Settings,
    *,
    lookback_days: int,
    directory: Path | None = None,
    now: datetime | None = None,
) -> WindowDayWatch:
    """Un tick: evalúa hoy + arrastre, avisa lo NO anunciado y deja el latido.

    El orden importa: primero se evalúa, después se avisa **deduplicando contra el latido** y
    sólo al final se escribe el latido con las marcas nuevas. Si un aviso falla, su marca no
    se guarda y el siguiente tick lo reintenta.
    """
    moment = now or datetime.now(MADRID)
    checks = await evaluate_all(
        now=moment,
        settings=cfg,
        lookback_days=lookback_days,
        persist=False,
        directory=directory,
        source="worker",
        announce=False,
    )
    # La marca durable es la ÚNICA fuente de verdad del dedupe: no hay estado en memoria que
    # se pierda al reiniciar el proceso.
    alerted = await announce_pending(cfg, checks, read_alerted(directory))
    write_status(
        checks,
        now=moment,
        lookback_days=lookback_days,
        source="worker",
        directory=directory,
        alerted=alerted,
    )
    return checks[0]


async def window_day_watch_loop(
    *,
    tick_seconds: float | None = None,
    settings: Settings | None = None,
    lookback_days: int | None = None,
    directory: Path | None = None,
) -> None:
    cfg = settings or get_settings()
    interval = float(tick_seconds) if tick_seconds is not None else float(CHECK_INTERVAL_SECONDS)
    span = default_lookback_days(cfg) if lookback_days is None else int(lookback_days)
    logger.info(
        "WindowDayWatch iniciado (tick=%ss; hora=%02d:%02d Europe/Madrid; arrastre=%sd)",
        interval,
        int(getattr(cfg, "window_day_watch_hour", 20)),
        int(getattr(cfg, "window_day_watch_minute", 0)),
        span,
    )
    while True:
        if _worker_enabled():
            # Primero evalúa y deja el latido, DESPUÉS duerme: al arrancar el stack ya hay
            # veredicto escrito (vigilancia comprobable desde el primer segundo).
            try:
                await _tick(cfg, lookback_days=span, directory=directory)
            except Exception:
                logger.exception("vigía ventana PAPER: tick falló (se reintenta el siguiente)")
        await asyncio.sleep(interval)


def start_window_day_watch(
    session_factory: object = None,
    *,
    tick_seconds: float | None = None,
    settings: Settings | None = None,
    lookback_days: int | None = None,
    directory: Path | None = None,
) -> asyncio.Task[None] | None:
    """Arranca el vigía (``session_factory`` ignorado: el vigía no usa BD). Default ON."""
    if not _worker_enabled():
        logger.info("WindowDayWatch desactivado (%s=false)", _ENV_ENABLED)
        return None
    return asyncio.create_task(
        window_day_watch_loop(
            tick_seconds=tick_seconds,
            settings=settings,
            lookback_days=lookback_days,
            directory=directory,
        )
    )


# ---------------------------------------------------------------------------
# CLI autónomo (`pnpm window:watch`): vigila SIN el stack dev
# ---------------------------------------------------------------------------

_CLI_HELP = """Vigía diario de la ventana PAPER (ADR-046) — evaluación y aviso.

Uso:
  python -m bolsa_api.background.window_day_watch_worker [opciones]

Evalúa el día de hoy y arrastra los días laborables anteriores sin fila en el ledger,
deja el latido en `operability_runs/window-runs/day-watch.json` y AVISA (log + email si
hay SMTP). No toca la ventana: sólo lee el ledger y escribe su propio latido.

Cada par (día, veredicto) se avisa UNA sola vez: la marca se guarda en el campo `alerted`
del latido y la comparten este CLI y el worker del stack (los reinicios no repiten emails).

Opciones:
  --once               (implícito) una única evaluación y salir
  --lookback-days N    días naturales de arrastre (0 desactiva; default 7)
  --now ISO            evalúa como si fuera esa fecha (revisar un día pasado)
  --json               imprime el latido por stdout
  --no-persist         no escribe el latido (dry-run)
  -h, --help           esta ayuda

Salida: 0 = sin alerta (OK/VETO/DECLARADO/...); 3 = hay día perdido/HARD_ERROR.
"""


def _int_flag(args: Sequence[str], name: str, default: int) -> int:
    if name not in args:
        return default
    index = args.index(name)
    raw = args[index + 1] if index + 1 < len(args) else ""
    try:
        return int(raw)
    except ValueError:
        logger.warning("window:watch: %s=%r no es un entero; se usa %s", name, raw, default)
        return default


def _now_flag(args: Sequence[str]) -> datetime | None:
    """``--now ISO`` (opcional): fecha de referencia para revisar un día pasado."""
    if "--now" not in args:
        return None
    index = args.index("--now")
    raw = args[index + 1] if index + 1 < len(args) else ""
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("window:watch: --now=%r no es ISO; se usa la hora actual", raw)
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=MADRID)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI del vigía: evalúa una vez y sale (0 sin alerta; 3 con alerta)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"-h", "--help"} for arg in args):
        print(_CLI_HELP)
        return 0
    if not _worker_enabled():
        print(f"vigía desactivado ({_ENV_ENABLED}=false)")
        return 0

    from bolsa_api.logging_redact import install_log_redact

    logging.basicConfig(level=logging.INFO)
    install_log_redact()

    span = _int_flag(args, "--lookback-days", default_lookback_days())
    persist = "--no-persist" not in args
    moment = _now_flag(args) or datetime.now(MADRID)
    cfg = get_settings()
    checks = asyncio.run(
        evaluate_all(
            now=moment,
            settings=cfg,
            lookback_days=span,
            persist=False,
            source="cli",
            announce=False,
        ),
    )
    # Misma marca durable que el worker: el CLI ya no reenvía lo que el stack dev avisó.
    alerted = asyncio.run(announce_pending(cfg, checks, read_alerted()))
    if persist:
        write_status(
            checks,
            now=moment,
            lookback_days=span,
            source="cli",
            alerted=alerted,
        )
    alerts = [check for check in checks if check.severity == "alert"]
    if "--json" in args:
        payload = status_payload(
            checks,
            now=moment,
            lookback_days=span,
            source="cli",
            alerted=alerted,
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for check in checks:
            print(f"[window:watch] {check.day_iso} · {check.verdict} · {check.message}")
    # El exit 3 sigue declarando «hay día perdido» aunque el email ya se emitiera: es lo que
    # deja la señal en `LastTaskResult` de la tarea programada.
    return ALERT_EXIT_CODE if alerts else 0


if __name__ == "__main__":  # pragma: no cover — entrada del CLI/tarea programada
    raise SystemExit(main())


__all__ = [
    "ALERT_EXIT_CODE",
    "CHECK_INTERVAL_SECONDS",
    "DEFAULT_LOOKBACK_DAYS",
    "MAX_LOOKBACK_DAYS",
    "STATUS_FILE",
    "STATUS_JOURNAL",
    "WindowDayWatch",
    "alert_key",
    "alert_recipient",
    "announce_pending",
    "day_is_running",
    "day_stamp",
    "default_lookback_days",
    "evaluate_all",
    "evaluate_backfill",
    "evaluate_day_watch",
    "evaluate_once",
    "ledger_path",
    "main",
    "read_alerted",
    "read_ledger_rows",
    "repo_root",
    "runs_dir",
    "send_alert_email",
    "start_window_day_watch",
    "status_journal_path",
    "status_path",
    "status_payload",
    "window_day_watch_loop",
    "write_status",
]
