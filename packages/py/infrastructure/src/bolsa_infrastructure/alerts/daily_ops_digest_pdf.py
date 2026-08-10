"""R4 — PDF presentación del resumen operativo diario.

Diseño centrado en **operativa del día**: cabecera, KPIs, tabla de trades,
gráfico de actividad semanal y sparkline de balance. Solo stdlib (Helvetica).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Paleta (RGB 0–1) — slate + teal financiero
C_INK = (0.07, 0.09, 0.15)
C_MUTED = (0.39, 0.45, 0.55)
C_HEADER = (0.06, 0.09, 0.16)
C_ACCENT = (0.05, 0.58, 0.53)
C_CARD = (0.95, 0.96, 0.98)
C_LINE = (0.86, 0.89, 0.93)
C_POS = (0.02, 0.59, 0.41)
C_NEG = (0.88, 0.11, 0.28)
C_WHITE = (1.0, 1.0, 1.0)
C_BAR = (0.08, 0.72, 0.65)
C_BAR_DIM = (0.78, 0.84, 0.88)


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def _pdf_escape(text: str) -> str:
    cleaned = text.encode("latin-1", errors="replace").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb(ops: list[str], color: tuple[float, float, float], *, fill: bool) -> None:
    r, g, b = color
    ops.append(f"{r:.3f} {g:.3f} {b:.3f} {'rg' if fill else 'RG'}")


@dataclass
class _Page:
    ops: list[str] = field(default_factory=list)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: tuple[float, float, float] | None = None,
        stroke: tuple[float, float, float] | None = None,
        width: float = 0.6,
    ) -> None:
        if fill:
            _rgb(self.ops, fill, fill=True)
        if stroke:
            self.ops.append(f"{width:.2f} w")
            _rgb(self.ops, stroke, fill=False)
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            self.ops.append("B")
        elif fill:
            self.ops.append("f")
        else:
            self.ops.append("S")

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: tuple[float, float, float] = C_LINE,
        width: float = 0.7,
    ) -> None:
        self.ops.append(f"{width:.2f} w")
        _rgb(self.ops, color, fill=False)
        self.ops.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        size: float = 10,
        bold: bool = False,
        color: tuple[float, float, float] = C_INK,
    ) -> None:
        font = "F2" if bold else "F1"
        _rgb(self.ops, color, fill=True)
        self.ops.append("BT")
        self.ops.append(f"/{font} {size:.1f} Tf")
        self.ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        self.ops.append(f"({_pdf_escape(text)}) Tj")
        self.ops.append("ET")

    def poly(
        self,
        points: list[tuple[float, float]],
        *,
        color: tuple[float, float, float],
        width: float = 1.5,
        close: bool = False,
    ) -> None:
        if len(points) < 2:
            return
        self.ops.append(f"{width:.2f} w")
        _rgb(self.ops, color, fill=False)
        x0, y0 = points[0]
        self.ops.append(f"{x0:.2f} {y0:.2f} m")
        for x, y in points[1:]:
            self.ops.append(f"{x:.2f} {y:.2f} l")
        if close:
            self.ops.append("h")
        self.ops.append("S")


def _as_of(bundle: Any) -> str:
    return bundle.as_of.isoformat() if hasattr(bundle.as_of, "isoformat") else str(bundle.as_of)


def _account_name(bundle: Any) -> str:
    return str(getattr(bundle.summary.account, "name", bundle.account_id))


def _exec_summary(bundle: Any) -> str:
    n = len(bundle.trades_today)
    buys = sum(1 for t in bundle.trades_today if str(t.type).lower() == "buy")
    sells = sum(1 for t in bundle.trades_today if str(t.type).lower() == "sell")
    pnl = float(bundle.summary.total_unrealized_pnl)
    alarma = int(bundle.channels.get("alarma", 0))
    aviso = int(bundle.channels.get("aviso", 0))
    if n == 0:
        ops = "Sin compras/ventas en el día."
    else:
        ops = f"{n} operación(es): {buys} compra(s), {sells} venta(s)."
    tone = "P&L latente positivo" if pnl >= 0 else "P&L latente negativo"
    return f"{ops} {tone} ({_money(pnl)}). Canales: {alarma} alarma(s), {aviso} aviso(s)."


def _draw_kpi(
    page: _Page,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    *,
    value_color: tuple[float, float, float] = C_INK,
) -> None:
    page.rect(x, y, w, h, fill=C_CARD, stroke=C_LINE, width=0.5)
    page.rect(x, y + h - 3, w, 3, fill=C_ACCENT)
    page.text(x + 8, y + h - 18, label.upper(), size=7, bold=True, color=C_MUTED)
    page.text(x + 8, y + 10, value, size=12, bold=True, color=value_color)


def _draw_trades_table(page: _Page, bundle: Any, *, x: float, y_top: float, width: float) -> float:
    """Devuelve y inferior tras la tabla."""
    page.text(x, y_top, "Operativa del día", size=12, bold=True, color=C_INK)
    page.rect(x, y_top - 4, 98, 2, fill=C_ACCENT)

    headers = [("TIPO", 36), ("SÍMBOLO", 70), ("CANTIDAD", 80), ("IMPORTE", 90), ("NOTA", 120)]
    col_x = [x]
    for _, w in headers[:-1]:
        col_x.append(col_x[-1] + w)

    y = y_top - 22
    page.rect(x, y - 4, width, 16, fill=(0.90, 0.93, 0.96))
    for i, (label, _) in enumerate(headers):
        page.text(col_x[i] + 4, y, label, size=7, bold=True, color=C_MUTED)

    trades = list(bundle.trades_today)[:14]
    y -= 18
    if not trades:
        page.text(x + 4, y, "Sin compras ni ventas registradas este día.", size=9, color=C_MUTED)
        return y - 12

    for idx, t in enumerate(trades):
        if idx % 2 == 1:
            page.rect(x, y - 3, width, 14, fill=(0.97, 0.98, 0.99))
        typ = str(t.type).upper()
        sym = t.symbol or (t.instrument_id[:8] if t.instrument_id else "—")
        typ_color = C_POS if typ == "BUY" else C_NEG if typ == "SELL" else C_INK
        page.text(col_x[0] + 4, y, typ, size=8, bold=True, color=typ_color)
        page.text(col_x[1] + 4, y, str(sym)[:12], size=8, color=C_INK)
        page.text(col_x[2] + 4, y, _money(float(t.quantity)), size=8, color=C_INK)
        page.text(col_x[3] + 4, y, _money(float(t.amount)), size=8, color=C_INK)
        note = ""
        if getattr(t, "note", None):
            note = str(t.note)[:28]
        page.text(col_x[4] + 4, y, note, size=7, color=C_MUTED)
        y -= 14
        page.line(x, y + 10, x + width, y + 10, color=C_LINE, width=0.3)

    if len(bundle.trades_today) > 14:
        y -= 4
        page.text(
            x + 4,
            y,
            f"… y {len(bundle.trades_today) - 14} operaciones más (ver Asesor → Diario)",
            size=7,
            color=C_MUTED,
        )
        y -= 10
    return y


def _draw_week_bars(
    page: _Page,
    week: list[dict[str, Any]],
    *,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    page.text(x, y + h + 14, "Actividad semanal (trades/día)", size=10, bold=True, color=C_INK)
    page.rect(x, y, w, h, fill=C_CARD, stroke=C_LINE, width=0.5)
    if not week:
        page.text(x + 8, y + h / 2, "Sin datos", size=8, color=C_MUTED)
        return

    counts = [int(d.get("tradeCount") or 0) for d in week]
    max_c = max(1, max(counts))
    n = len(week)
    pad = 10
    gap = 6
    usable = w - pad * 2 - gap * (n - 1)
    bar_w = usable / n
    base = y + 16
    top = y + h - 10
    chart_h = top - base

    for i, d in enumerate(week):
        c = counts[i]
        bx = x + pad + i * (bar_w + gap)
        bh = (c / max_c) * chart_h if max_c else 0
        by = base
        color = C_BAR if c > 0 else C_BAR_DIM
        page.rect(bx, by, bar_w, max(2.0, bh), fill=color)
        label = str(d.get("date", ""))[5:]  # MM-DD
        page.text(bx, y + 4, label, size=6, color=C_MUTED)
        if c > 0:
            page.text(bx + max(0, bar_w / 2 - 4), by + bh + 2, str(c), size=7, bold=True, color=C_INK)


def _draw_balance_sparkline(
    page: _Page,
    week: list[dict[str, Any]],
    *,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    page.text(x, y + h + 14, "Balance (semana)", size=10, bold=True, color=C_INK)
    page.rect(x, y, w, h, fill=C_CARD, stroke=C_LINE, width=0.5)

    bals: list[tuple[int, float]] = []
    for i, d in enumerate(week):
        bal = d.get("balanceAfter")
        if bal is not None:
            bals.append((i, float(bal)))
    if len(bals) < 2:
        page.text(x + 8, y + h / 2 - 4, "Pocos puntos de balance esta semana.", size=8, color=C_MUTED)
        return

    vals = [v for _, v in bals]
    lo, hi = min(vals), max(vals)
    span = max(1e-6, hi - lo)
    pad = 12
    pts: list[tuple[float, float]] = []
    n = max(1, len(week) - 1)
    for i, v in bals:
        px = x + pad + (i / n) * (w - pad * 2)
        py = y + pad + ((v - lo) / span) * (h - pad * 2)
        pts.append((px, py))

    page.poly(pts, color=C_ACCENT, width=1.8)
    # extremos
    page.text(x + 6, y + h - 12, _money(hi), size=6, color=C_MUTED)
    page.text(x + 6, y + 4, _money(lo), size=6, color=C_MUTED)
    last = vals[-1]
    page.text(x + w - 70, y + h - 12, f"Último {_money(last)}", size=7, bold=True, color=C_INK)


def _draw_channels_panel(
    page: _Page,
    bundle: Any,
    *,
    x: float,
    y: float,
    w: float,
) -> float:
    page.text(x, y, "Pendientes y canales Estudio", size=10, bold=True, color=C_INK)
    y -= 8
    page.rect(x, y - 52, w, 52, fill=C_CARD, stroke=C_LINE, width=0.5)

    alarma = int(bundle.channels.get("alarma", 0))
    aviso = int(bundle.channels.get("aviso", 0))
    f3 = int(bundle.f3_pending_count)

    boxes = [
        (x + 8, "F3 cola", str(f3), C_INK),
        (x + 8 + w / 3, "Alarmas", str(alarma), C_NEG if alarma else C_INK),
        (x + 8 + 2 * w / 3, "Avisos", str(aviso), C_ACCENT if aviso else C_INK),
    ]
    for bx, lab, val, col in boxes:
        page.text(bx, y - 16, lab.upper(), size=7, bold=True, color=C_MUTED)
        page.text(bx, y - 36, val, size=16, bold=True, color=col)

    y -= 64
    # Mini tabla opiniones (alarma/aviso)
    rows = [
        o
        for o in bundle.opinions
        if str(o.get("channel") or "") in {"alarma", "aviso"}
    ][:8]
    if rows:
        page.text(x, y, "Dictámenes canalizados", size=9, bold=True, color=C_INK)
        y -= 14
        page.text(x + 4, y, "CANAL", size=7, bold=True, color=C_MUTED)
        page.text(x + 60, y, "SÍMBOLO", size=7, bold=True, color=C_MUTED)
        page.text(x + 140, y, "STARS", size=7, bold=True, color=C_MUTED)
        page.text(x + 190, y, "STANCE", size=7, bold=True, color=C_MUTED)
        y -= 12
        for o in rows:
            ch = str(o.get("channel") or "")
            col = C_NEG if ch == "alarma" else C_ACCENT
            page.text(x + 4, y, ch, size=8, bold=True, color=col)
            page.text(
                x + 60,
                y,
                str(o.get("symbol") or str(o.get("instrumentId", ""))[:8]),
                size=8,
                color=C_INK,
            )
            stars = int(o.get("dictamenStars") or 0)
            page.text(x + 140, y, "*" * max(0, min(5, stars)), size=8, color=C_INK)
            page.text(x + 190, y, str(o.get("stance") or "—")[:18], size=8, color=C_MUTED)
            y -= 11
    return y


def _build_pages(bundle: Any) -> list[_Page]:
    pages: list[_Page] = []
    page = _Page()
    pages.append(page)

    # Cabecera full-bleed
    page.rect(0, 732, 612, 60, fill=C_HEADER)
    page.rect(0, 732, 6, 60, fill=C_ACCENT)
    page.text(24, 768, "BOLSA V1", size=9, bold=True, color=C_ACCENT)
    page.text(24, 750, "Operativa diaria", size=18, bold=True, color=C_WHITE)
    page.text(
        24,
        736,
        f"{_account_name(bundle)}  ·  {_as_of(bundle)}",
        size=9,
        color=(0.70, 0.75, 0.82),
    )

    # Resumen ejecutivo
    page.text(24, 710, "Resumen", size=9, bold=True, color=C_MUTED)
    # wrap roughly
    summary = _exec_summary(bundle)
    page.text(24, 696, summary[:95], size=9, color=C_INK)
    if len(summary) > 95:
        page.text(24, 684, summary[95:190], size=9, color=C_INK)

    # KPIs
    s = bundle.summary
    pnl = float(s.total_unrealized_pnl)
    kpi_y = 610
    kpi_h = 48
    gap = 10
    kpi_w = (612 - 48 - 3 * gap) / 4
    _draw_kpi(page, 24, kpi_y, kpi_w, kpi_h, "Equity", _money(float(s.total_equity)))
    _draw_kpi(page, 24 + kpi_w + gap, kpi_y, kpi_w, kpi_h, "Cash", _money(float(s.cash)))
    _draw_kpi(
        page,
        24 + 2 * (kpi_w + gap),
        kpi_y,
        kpi_w,
        kpi_h,
        "P&L latente",
        _money(pnl),
        value_color=C_POS if pnl >= 0 else C_NEG,
    )
    _draw_kpi(
        page,
        24 + 3 * (kpi_w + gap),
        kpi_y,
        kpi_w,
        kpi_h,
        "Trades hoy",
        str(len(bundle.trades_today)),
        value_color=C_ACCENT,
    )
    page.text(
        24,
        kpi_y - 14,
        f"Posiciones abiertas: {int(s.positions_count)}",
        size=8,
        color=C_MUTED,
    )

    # Tabla operativa
    y = _draw_trades_table(page, bundle, x=24, y_top=kpi_y - 36, width=564)

    # Charts fila
    chart_h = 88
    chart_y = min(y - 30 - chart_h, 220)
    if chart_y < 40:
        # segunda página
        page.text(24, 28, "Bolsa V1 · Asesor Diario · continua…", size=7, color=C_MUTED)
        page = _Page()
        pages.append(page)
        page.rect(0, 762, 612, 30, fill=C_HEADER)
        page.text(24, 772, "Operativa diaria · detalle", size=11, bold=True, color=C_WHITE)
        chart_y = 640

    half = (564 - 12) / 2
    _draw_week_bars(page, list(bundle.week), x=24, y=chart_y, w=half, h=chart_h)
    _draw_balance_sparkline(
        page, list(bundle.week), x=24 + half + 12, y=chart_y, w=half, h=chart_h
    )

    y2 = chart_y - 28
    y2 = _draw_channels_panel(page, bundle, x=24, y=y2, w=564)

    page.text(
        24,
        28,
        "Bolsa V1 · Asesor → Diario · informe R4  ·  Abre la app para el detalle interactivo.",
        size=7,
        color=C_MUTED,
    )
    page.line(24, 38, 588, 38, color=C_LINE, width=0.4)
    _ = y2
    return pages


def build_daily_ops_digest_pdf(bundle: Any) -> bytes:
    """PDF 1.4 presentación (1–2 páginas) centrada en operativa diaria."""
    pages = _build_pages(bundle)

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")  # placeholder Pages
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    font_reg, font_bold = 3, 4

    page_obj_nums: list[int] = []
    for page in pages:
        stream = "\n".join(page.ops).encode("latin-1", errors="replace")
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
                f"/Resources << /Font << /F1 {font_reg} 0 R /F2 {font_bold} 0 R >> >> >>"
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
    return f"bolsa-resumen-operativo-{_as_of(bundle)}.pdf"
