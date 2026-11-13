"""Notificación email de Alarmas Estudio (D2 scaffold · off-by-default).

Reutiliza SMTP de Settings; no envía si flag off o SMTP incompleto.
Regla de canal alineada con `opinion-channel-map.ts` §5.2.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Protocol

from bolsa_infrastructure.config import Settings

logger = logging.getLogger(__name__)


class _OpinionLike(Protocol):
    instrument_id: str
    stance: str
    dictamen_stars: int
    as_of_bar_date: Any
    reasons: list[str]


#: Espejo declarado de `packages/shared/src/market-vocabulary.ts`. El cuerpo del
#: email no debe imprimir claves internas (`buy`, `gate_veto`…) ni snake_case: si
#: diverge del glosario TS, el test de cuerpo lo detecta. Una sola dirección:
#: clave del motor → nombre visible.
STANCE_LABELS: dict[str, str] = {
    "buy": "Comprar",
    "hold_watch": "Mantener",
    "overbought": "Sin respaldo",
    "reduce": "Reducir",
    "sell_exit": "Vender",
    "no_trade": "No operar",
    "review_strategy": "Revisar estrategia",
}

#: Causas de `no_trade`, en orden de precedencia (la primera que aparezca manda).
NO_TRADE_CAUSE_LABELS: tuple[tuple[str, str, str], ...] = (
    ("position_unmeasured", "No evaluable", "Cartera sin medir"),
    ("position_closed", "No evaluable", "Posición no confirmada"),
    ("gate_veto", "Operativa bloqueada", "Filtro de riesgo en veto"),
    ("eod_data_stale", "No operar", "Sin cierre de sesión"),
    ("fa_distress", "No operar", "Alerta fundamental"),
)

REASON_LABELS: dict[str, str] = {
    "eod_data_stale": "Sin cierre de sesión",
    "gate_veto": "Filtro de riesgo en veto",
    "stale_top": "Estrategia del Lab desactualizada",
    "no_valid_top": "Sin estrategia del Lab",
    "fa_distress": "Alerta fundamental",
    "strong_buy_signal": "Señal de compra fuerte",
    "neutral_no_position": "Sin señal de entrada",
    "overbought_or_exit": "Señal de salida",
    "holding_position": "Posición abierta: se mantiene",
    "top_high": "Estrategia del Lab con respaldo alto",
    "top_medium": "Estrategia del Lab con respaldo suficiente",
    "top_low": "Estrategia del Lab sin respaldo",
    "io_high": "Calidad de señal alta",
    "io_low": "Calidad de señal baja",
    "io_medium": "Calidad de señal sin señal de compra",
    "position_open": "Ya hay posición abierta",
    "position_closed": "Posición no confirmada",
    "position_unmeasured": "Cartera sin medir",
    "io_unmeasured": "Calidad de señal sin medir",
}

#: Motivos que solo son diagnóstico: no se pintan en el cuerpo de producto.
DIAGNOSTIC_ONLY_REASONS = frozenset({"gate_veto"})


def stance_label(stance: str, reasons: list[str] | None = None) -> str:
    """Denominación visible de la postura; `no_trade` se afina por causa."""
    if stance == "no_trade":
        raw = reasons or []
        for reason, label, _detail in NO_TRADE_CAUSE_LABELS:
            if reason in raw:
                return label
    return STANCE_LABELS.get(stance) or "Sin recomendación"


def stance_detail(stance: str, reasons: list[str] | None = None) -> str | None:
    """Causa declarada de la postura, si la tiene."""
    if stance != "no_trade":
        return None
    raw = reasons or []
    for reason, _label, detail in NO_TRADE_CAUSE_LABELS:
        if reason in raw:
            return detail
    return None


def reason_labels(reasons: list[str] | None) -> list[str]:
    """Motivos traducidos, sin diagnóstico y sin duplicados."""
    out: list[str] = []
    for reason in reasons or []:
        if reason in DIAGNOSTIC_ONLY_REASONS:
            continue
        label = REASON_LABELS.get(str(reason))
        if label and label not in out:
            out.append(label)
    return out


def map_opinion_to_channel(*, stance: str, dictamen_stars: int) -> str:
    """silent | aviso | alarma — espejo de packages/shared opinion-channel-map."""
    stars = min(5, max(1, int(round(dictamen_stars))))
    if stance == "buy":
        if stars >= 4:
            return "alarma"
        if stars >= 2:
            return "aviso"
        return "silent"
    if stance in ("sell_exit", "reduce"):
        return "alarma" if stars >= 3 else "aviso"
    if stance in ("overbought", "review_strategy"):
        return "aviso"
    return "silent"


def filter_alarma_opinions(rows: list[Any]) -> list[Any]:
    out: list[Any] = []
    for row in rows:
        level = map_opinion_to_channel(
            stance=str(row.stance),
            dictamen_stars=int(row.dictamen_stars),
        )
        if level == "alarma":
            out.append(row)
    return out


def smtp_ready(settings: Settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def smtp_auth_ready(settings: Settings) -> bool:
    """Puerto 587/465 exige usuario+password en la práctica (Gmail, Outlook, etc.)."""
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").strip()
    return bool(user and password)


def _send_smtp_message(settings: Settings, message: EmailMessage) -> None:
    """Conecta SMTP con STARTTLS + login cuando hay credenciales."""
    host = (settings.smtp_host or "").strip()
    if not host:
        raise RuntimeError("SMTP_HOST vacío")
    if (settings.smtp_user or "").strip() and not (settings.smtp_password or "").strip():
        raise RuntimeError(
            "SMTP_PASSWORD vacío: el servidor de correo exige contraseña de aplicación "
            "(no la del usuario final). En Gmail: Cuenta → Seguridad → Contraseñas de apps."
        )

    port = int(settings.smtp_port or 587)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        if port != 25:
            smtp.starttls()
            smtp.ehlo()
        if smtp_auth_ready(settings):
            try:
                smtp.login(
                    (settings.smtp_user or "").strip(),
                    (settings.smtp_password or "").strip(),
                )
            except smtplib.SMTPAuthenticationError as exc:
                raise RuntimeError(
                    "SMTP rechazó usuario/contraseña. Usa una App Password (Gmail/Outlook), "
                    "no la contraseña normal de la cuenta. Revisa SMTP_USER / SMTP_PASSWORD "
                    "en .env y reinicia la API."
                ) from exc
        try:
            smtp.send_message(message)
        except smtplib.SMTPSenderRefused as exc:
            raise RuntimeError(
                f"SMTP rechazó el remitente ({settings.smtp_from}). "
                "SMTP_FROM debe coincidir con la cuenta autenticada."
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise RuntimeError("SMTP rechazó el destinatario.") from exc
        except smtplib.SMTPException as exc:
            detail = " ".join(str(x) for x in getattr(exc, "args", ()) if x) or str(exc)
            raise RuntimeError(f"SMTP falló: {detail}") from exc


def send_estudio_alarma_email_sync(
    settings: Settings,
    *,
    recipient: str,
    alarmas: list[Any],
    symbol_by_id: dict[str, str] | None = None,
) -> None:
    if not alarmas:
        return
    if not smtp_ready(settings):
        raise RuntimeError("SMTP no configurado (SMTP_HOST / SMTP_FROM)")

    symbols = symbol_by_id or {}
    lines = [
        "Alarmas Estudio (dictamen diario)",
        f"Total: {len(alarmas)}",
        "",
    ]
    for row in alarmas[:40]:
        sym = symbols.get(row.instrument_id) or row.instrument_id[:8]
        as_of = getattr(row, "as_of_bar_date", "")
        reasons = list(getattr(row, "reasons", None) or [])
        label = stance_label(str(row.stance), reasons)
        detail = stance_detail(str(row.stance), reasons)
        labels = reason_labels(reasons)
        reason_txt = "; ".join(labels[:3]) or "Sin motivo declarado"
        io_score = getattr(row, "io_score", None)
        stars = (
            "Sin medir"
            if io_score is None
            else "★" * min(5, max(0, int(row.dictamen_stars)))
        )
        head = f"- {sym} · {label}"
        if detail:
            head += f" ({detail})"
        lines.append(
            f"{head} {stars} · asOf={as_of} · {reason_txt}"
        )
    if len(alarmas) > 40:
        lines.append(f"… y {len(alarmas) - 40} más")
    lines.append("")
    lines.append("Abre Asesor → Opiniones en la plataforma.")

    message = EmailMessage()
    message["Subject"] = f"[Bolsa] Estudio · {len(alarmas)} alarma(s)"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content("\n".join(lines))

    _send_smtp_message(settings, message)


async def maybe_notify_estudio_alarmas(
    settings: Settings,
    rows: list[Any],
    *,
    symbol_by_id: dict[str, str] | None = None,
    email_to: str | None = None,
    email_enabled: bool | None = None,
) -> dict[str, Any]:
    """Envía email de alarmas si SMTP + destinatario + enable OK.

    ``email_enabled`` / ``email_to`` del cliente (prefs UI) tienen prioridad sobre
    ``ESTUDIO_OPINION_EMAIL_*`` cuando se pasan explícitamente.
    """
    # Prefs UI (email_enabled is not None): destinatario solo del cliente.
    # Sin prefs: flags ESTUDIO_OPINION_EMAIL_* del servidor.
    if email_enabled is not None:
        enabled = bool(email_enabled)
        recipient = (email_to or "").strip()
    else:
        enabled = bool(settings.estudio_opinion_email_enabled)
        recipient = (settings.estudio_opinion_email_to or "").strip()

    result: dict[str, Any] = {
        "email_enabled": enabled,
        "alarma_count": 0,
        "sent": False,
        "skipped_reason": None,
    }
    alarmas = filter_alarma_opinions(rows)
    result["alarma_count"] = len(alarmas)

    if not enabled:
        result["skipped_reason"] = "email_disabled"
        return result
    if not alarmas:
        result["skipped_reason"] = "sin_alarmas"
        return result
    if not recipient:
        result["skipped_reason"] = "email_to vacío"
        return result
    if not smtp_ready(settings):
        result["skipped_reason"] = "SMTP incompleto (SMTP_HOST / SMTP_FROM)"
        logger.info("Estudio email skip: %s", result["skipped_reason"])
        return result

    try:
        await asyncio.to_thread(
            send_estudio_alarma_email_sync,
            settings,
            recipient=recipient,
            alarmas=alarmas,
            symbol_by_id=symbol_by_id,
        )
        result["sent"] = True
    except Exception as exc:
        logger.warning("Estudio alarma email falló to=%s: %s", recipient, exc)
        result["skipped_reason"] = str(exc)
    return result
