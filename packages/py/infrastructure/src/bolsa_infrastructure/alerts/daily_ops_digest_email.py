"""R3 — Email HTML del resumen operativo diario (off-by-default).

Sibling de `estudio_opinion_email`: mismo SMTP; destinatario = prefs Alarmas.
No toca Camino D / PAPER_D_EXECUTE.

``bundle`` es duck-typed (`DailyOpsReportBundle`) — sin import
infrastructure → application.
"""

from __future__ import annotations

import asyncio
import html
import logging
from email.message import EmailMessage
from typing import Any

from bolsa_infrastructure.alerts.estudio_opinion_email import _send_smtp_message, smtp_ready
from bolsa_infrastructure.config import Settings

logger = logging.getLogger(__name__)


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else "—"))


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def build_daily_ops_digest_text(bundle: Any) -> str:
    """Cuerpo text/plain (fallback clientes sin HTML)."""
    s = bundle.summary
    name = getattr(s.account, "name", bundle.account_id)
    as_of = bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)
    lines = [
        f"Resumen operativo · {as_of}",
        f"Cuenta: {name}",
        "",
        f"Equity: {_money(s.total_equity)}",
        f"Cash: {_money(s.cash)}",
        f"P&L latente: {_money(s.total_unrealized_pnl)}",
        f"Posiciones: {s.positions_count}",
        f"Trades hoy: {len(bundle.trades_today)}",
        f"F3 pendiente: {bundle.f3_pending_count}",
        (
            f"Canales · Alarmas {bundle.channels.get('alarma', 0)} · "
            f"Avisos {bundle.channels.get('aviso', 0)}"
        ),
        "",
    ]
    for t in bundle.trades_today[:20]:
        sym = t.symbol or (t.instrument_id[:8] if t.instrument_id else "—")
        lines.append(f"- {t.type.upper()} {sym} · qty={t.quantity} · {_money(t.amount)}")
    if len(bundle.trades_today) > 20:
        lines.append(f"… y {len(bundle.trades_today) - 20} más")
    lines.append("")
    lines.append("Abre Asesor → Diario en la plataforma.")
    return "\n".join(lines)


def build_daily_ops_digest_html(bundle: Any) -> str:
    """HTML email-safe (tablas + estilos inline)."""
    s = bundle.summary
    name = getattr(s.account, "name", bundle.account_id)
    as_of = bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)
    pnl = float(s.total_unrealized_pnl)
    pnl_color = "#059669" if pnl >= 0 else "#e11d48"

    trade_rows = ""
    for t in bundle.trades_today[:15]:
        sym = t.symbol or (t.instrument_id[:8] if t.instrument_id else "—")
        trade_rows += (
            "<tr>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0'>{_esc(t.type.upper())}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0'>{_esc(sym)}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>"
            f"{_esc(_money(t.quantity))}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>"
            f"{_esc(_money(t.amount))}</td>"
            "</tr>"
        )
    if not trade_rows:
        trade_rows = (
            "<tr><td colspan='4' style='padding:8px;color:#64748b'>"
            "Sin compras/ventas hoy.</td></tr>"
        )

    week_cells = ""
    for d in bundle.week:
        week_cells += (
            "<td style='padding:4px;text-align:center;font-size:11px'>"
            f"<div style='color:#64748b'>{_esc(str(d['date'])[5:])}</div>"
            f"<div style='font-weight:600'>{int(d['tradeCount'])}</div>"
            "</td>"
        )

    opinion_rows = ""
    for o in bundle.opinions[:12]:
        ch = str(o.get("channel") or "none")
        if ch not in {"alarma", "aviso"}:
            continue
        badge_bg = "#ffe4e6" if ch == "alarma" else "#e0f2fe"
        badge_fg = "#9f1239" if ch == "alarma" else "#075985"
        stars = "★" * max(0, min(5, int(o.get("dictamenStars") or 0)))
        opinion_rows += (
            "<tr>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0'>"
            f"<span style='background:{badge_bg};color:{badge_fg};padding:2px 6px;"
            f"border-radius:4px;font-size:10px;text-transform:uppercase'>{_esc(ch)}</span> "
            f"{_esc(o.get('symbol') or str(o.get('instrumentId', ''))[:8])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>"
            f"{_esc(stars)}</td>"
            "</tr>"
        )
    if not opinion_rows:
        opinion_rows = (
            "<tr><td colspan='2' style='padding:8px;color:#64748b'>"
            "Sin Alarmas/Avisos en Estudio para asOf.</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Resumen operativo {_esc(as_of)}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
        <tr>
          <td style="background:linear-gradient(135deg,#0f172a 0%,#134e4a 45%,#0c4a6e 100%);padding:28px 24px;color:#fff">
            <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#99f6e4;opacity:0.9">Resumen operativo</div>
            <div style="font-size:26px;font-weight:600;margin-top:6px">{_esc(name)}</div>
            <div style="font-size:13px;color:#cbd5e1;margin-top:6px">{_esc(as_of)} · DEMO</div>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 24px">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:25%;padding:8px;background:#f8fafc;border-radius:8px">
                  <div style="font-size:10px;color:#64748b;text-transform:uppercase">Equity</div>
                  <div style="font-size:18px;font-weight:600">{_esc(_money(s.total_equity))}</div>
                </td>
                <td style="width:8px"></td>
                <td style="width:25%;padding:8px;background:#f8fafc;border-radius:8px">
                  <div style="font-size:10px;color:#64748b;text-transform:uppercase">Cash</div>
                  <div style="font-size:18px;font-weight:600">{_esc(_money(s.cash))}</div>
                </td>
                <td style="width:8px"></td>
                <td style="width:25%;padding:8px;background:#f8fafc;border-radius:8px">
                  <div style="font-size:10px;color:#64748b;text-transform:uppercase">P&amp;L</div>
                  <div style="font-size:18px;font-weight:600;color:{pnl_color}">{_esc(_money(pnl))}</div>
                </td>
                <td style="width:8px"></td>
                <td style="width:25%;padding:8px;background:#f8fafc;border-radius:8px">
                  <div style="font-size:10px;color:#64748b;text-transform:uppercase">Pos.</div>
                  <div style="font-size:18px;font-weight:600">{_esc(s.positions_count)}</div>
                </td>
              </tr>
            </table>

            <div style="margin-top:20px;font-size:12px;color:#475569">
              Trades hoy <strong>{len(bundle.trades_today)}</strong>
              · F3 pendiente <strong>{bundle.f3_pending_count}</strong>
              · Alarmas <strong style="color:#be123c">{bundle.channels.get("alarma", 0)}</strong>
              · Avisos <strong style="color:#0369a1">{bundle.channels.get("aviso", 0)}</strong>
            </div>

            <h2 style="font-size:14px;margin:22px 0 8px">Operaciones del día</h2>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;border:1px solid #e2e8f0;border-radius:8px">
              <tr style="background:#f8fafc;color:#64748b;text-align:left">
                <th style="padding:6px 8px">Tipo</th>
                <th style="padding:6px 8px">Símbolo</th>
                <th style="padding:6px 8px;text-align:right">Qty</th>
                <th style="padding:6px 8px;text-align:right">Importe</th>
              </tr>
              {trade_rows}
            </table>

            <h2 style="font-size:14px;margin:22px 0 8px">Canales Estudio</h2>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;border:1px solid #e2e8f0;border-radius:8px">
              {opinion_rows}
            </table>

            <h2 style="font-size:14px;margin:22px 0 8px">Semana · trades/día</h2>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:8px">
              <tr>{week_cells}</tr>
            </table>

            <p style="margin:24px 0 0;font-size:12px;color:#64748b">
              Abre <strong>Asesor → Diario</strong> en la plataforma para el detalle interactivo.
              Digest R3 · PDF adjunto R4 (opt-in).
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_daily_ops_digest_email_sync(
    settings: Settings,
    *,
    recipient: str,
    bundle: Any,
    attach_pdf: bool = False,
) -> bool:
    """Envía digest. Devuelve True si adjuntó PDF."""
    if not smtp_ready(settings):
        raise RuntimeError("SMTP no configurado (SMTP_HOST / SMTP_FROM)")

    from bolsa_infrastructure.alerts.daily_ops_digest_pdf import (
        build_daily_ops_digest_pdf,
        digest_pdf_filename,
    )

    plain = build_daily_ops_digest_text(bundle)
    html_body = build_daily_ops_digest_html(bundle)
    name = getattr(bundle.summary.account, "name", bundle.account_id)
    as_of = bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)

    message = EmailMessage()
    message["Subject"] = f"[Bolsa] Resumen operativo · {as_of} · {name}"
    message["From"] = settings.smtp_from  # type: ignore[arg-type]
    message["To"] = recipient
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")

    pdf_attached = False
    if attach_pdf:
        pdf_bytes = build_daily_ops_digest_pdf(bundle)
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=digest_pdf_filename(bundle),
        )
        pdf_attached = True

    _send_smtp_message(settings, message)
    return pdf_attached


async def maybe_notify_daily_ops_digest(
    settings: Settings,
    bundle: Any | None,
    *,
    email_to: str | None = None,
    digest_enabled: bool | None = None,
    attach_pdf: bool | None = None,
) -> dict[str, Any]:
    """Envía digest HTML (+ PDF R4 opcional) si prefs + SMTP OK.

    ``digest_enabled`` / ``email_to`` / ``attach_pdf`` del cliente tienen prioridad
    sobre flags ``DAILY_OPS_DIGEST_*``.
    """
    if digest_enabled is not None:
        enabled = bool(digest_enabled)
        recipient = (email_to or "").strip()
    else:
        enabled = bool(getattr(settings, "daily_ops_digest_email_enabled", False))
        recipient = (email_to or getattr(settings, "estudio_opinion_email_to", None) or "").strip()

    if attach_pdf is not None:
        want_pdf = bool(attach_pdf)
    else:
        want_pdf = bool(getattr(settings, "daily_ops_digest_pdf_enabled", False))

    as_of: str | None = None
    if bundle is not None:
        as_of = (
            bundle.as_of.isoformat()
            if hasattr(bundle.as_of, "isoformat")
            else str(bundle.as_of)
        )

    result: dict[str, Any] = {
        "digest_enabled": enabled,
        "sent": False,
        "skipped_reason": None,
        "as_of": as_of,
        "pdf_attached": False,
    }

    if not enabled:
        result["skipped_reason"] = "digest_disabled"
        return result
    if bundle is None:
        result["skipped_reason"] = "sin_account_id"
        return result
    if not recipient:
        result["skipped_reason"] = "email_to vacío"
        return result
    if not smtp_ready(settings):
        result["skipped_reason"] = "SMTP incompleto (SMTP_HOST / SMTP_FROM)"
        logger.info("Daily ops digest skip: %s", result["skipped_reason"])
        return result

    try:
        pdf_attached = await asyncio.to_thread(
            send_daily_ops_digest_email_sync,
            settings,
            recipient=recipient,
            bundle=bundle,
            attach_pdf=want_pdf,
        )
        result["sent"] = True
        result["pdf_attached"] = bool(pdf_attached)
    except Exception as exc:
        logger.warning("Daily ops digest falló to=%s: %s", recipient, exc)
        result["skipped_reason"] = str(exc)
    return result
