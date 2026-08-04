"""R4 — PDF mínimo del resumen operativo (sin deps tipográficas).

Helvetica + WinAnsi; suficiente para adjunto email / descarga.
No reportlab / weasyprint.
"""

from __future__ import annotations

from typing import Any


def _money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}"


def _pdf_escape(text: str) -> str:
    """Escapa para literales PDF (...); fuerza latin-1 (WinAnsi)."""
    cleaned = text.encode("latin-1", errors="replace").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _digest_lines(bundle: Any) -> list[str]:
    s = bundle.summary
    name = getattr(s.account, "name", bundle.account_id)
    as_of = bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)
    lines = [
        "Bolsa V1 — Resumen operativo diario",
        f"Cuenta: {name}",
        f"Fecha: {as_of}",
        "",
        f"Equity: {_money(s.total_equity)}",
        f"Cash: {_money(s.cash)}",
        f"P&L latente: {_money(s.total_unrealized_pnl)}",
        f"Posiciones: {s.positions_count}",
        f"Trades hoy: {len(bundle.trades_today)}",
        f"F3 pendiente: {bundle.f3_pending_count}",
        (
            f"Canales — Alarmas {bundle.channels.get('alarma', 0)} · "
            f"Avisos {bundle.channels.get('aviso', 0)}"
        ),
        "",
        "Operaciones del dia",
        "-" * 48,
    ]
    if not bundle.trades_today:
        lines.append("(sin compras/ventas)")
    for t in bundle.trades_today[:25]:
        sym = t.symbol or (t.instrument_id[:8] if t.instrument_id else "-")
        lines.append(
            f"{t.type.upper():4} {sym:8} qty={_money(t.quantity)}  amt={_money(t.amount)}"
        )
    if len(bundle.trades_today) > 25:
        lines.append(f"... y {len(bundle.trades_today) - 25} mas")

    lines.extend(["", "Canales Estudio (alarma/aviso)", "-" * 48])
    shown = 0
    for o in bundle.opinions:
        ch = str(o.get("channel") or "")
        if ch not in {"alarma", "aviso"}:
            continue
        stars = int(o.get("dictamenStars") or 0)
        sym = o.get("symbol") or str(o.get("instrumentId", ""))[:8]
        lines.append(f"{ch:7} {sym}  *{stars}")
        shown += 1
        if shown >= 20:
            break
    if shown == 0:
        lines.append("(sin alarmas/avisos)")

    lines.extend(["", "Semana (trades/dia)", "-" * 48])
    for d in bundle.week:
        bal = d.get("balanceAfter")
        bal_s = _money(float(bal)) if bal is not None else "-"
        lines.append(f"{d['date']}  trades={int(d['tradeCount'])}  bal={bal_s}")

    lines.extend(
        [
            "",
            "Generado por Bolsa V1 · Asesor Diario · R4 PDF",
            "Abre Asesor → Diario para el detalle interactivo.",
        ]
    )
    return lines


def build_daily_ops_digest_pdf(bundle: Any) -> bytes:
    """PDF 1.4 de una página (o más si hace falta) con el texto del digest."""
    lines = _digest_lines(bundle)
    pages: list[list[str]] = []
    per_page = 52
    for i in range(0, len(lines), per_page):
        pages.append(lines[i : i + per_page])
    if not pages:
        pages = [["(vacio)"]]

    objects: list[bytes] = []
    # 1 Catalog, 2 Pages, 3 Font, then page pairs (content, page)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # Pages kids filled later
    font_obj_num = 3
    objects.append(b"")  # placeholder pages
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    page_obj_nums: list[int] = []
    for page_lines in pages:
        y = 800
        content_parts = ["BT", "/F1 11 Tf", "14 TL", "50 800 Td"]
        first = True
        for line in page_lines:
            esc = _pdf_escape(line)
            if first:
                content_parts.append(f"({esc}) Tj")
                first = False
            else:
                content_parts.append("T*")
                content_parts.append(f"({esc}) Tj")
            y -= 14
        content_parts.append("ET")
        stream = "\n".join(content_parts).encode("latin-1", errors="replace")
        content_num = len(objects) + 1
        page_num = content_num + 1
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_num} 0 R "
                f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>"
            ).encode("ascii")
        )
        page_obj_nums.append(page_num)

    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_nums)} >>".encode(
        "ascii"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def digest_pdf_filename(bundle: Any) -> str:
    as_of = bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)
    return f"bolsa-resumen-operativo-{as_of}.pdf"
