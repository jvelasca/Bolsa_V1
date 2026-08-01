"""FIE F2b lite — almacén local de filings (PDF/TXT) por instrumento.

Diseño:
- Bytes en disco bajo ``BOLSA_FILINGS_DIR`` (default ``./data/filings``).
- Metadatos en ``index.json`` por instrumento (no JSONB Yahoo).
- **No** escribe ``profile_snapshot.fundamentals`` ni altera Score_FUND / gate.

@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

FILING_STORE_VERSION = "instrument_filings_v1"
ALLOWED_KINDS = frozenset({"10-K", "10-Q", "annual-report", "other"})
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_EXTRACT_CHARS = 80_000

ExtractStatus = Literal["ok", "empty", "skipped", "unavailable", "error"]


def filings_root() -> Path:
    """Raíz del almacén; override con ``BOLSA_FILINGS_DIR``."""
    raw = (os.getenv("BOLSA_FILINGS_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.cwd() / "data" / "filings").resolve()


def instrument_filings_dir(instrument_id: str) -> Path:
    """Directorio por instrumento bajo el almacén local."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", instrument_id.strip())[:128]
    return filings_root() / safe


def _instrument_dir(instrument_id: str) -> Path:
    return instrument_filings_dir(instrument_id)


def _index_path(instrument_id: str) -> Path:
    return _instrument_dir(instrument_id) / "index.json"


def _read_index(instrument_id: str) -> list[dict[str, Any]]:
    path = _index_path(instrument_id)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = raw.get("filings") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def _write_index(instrument_id: str, filings: list[dict[str, Any]]) -> None:
    directory = _instrument_dir(instrument_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "storeVersion": FILING_STORE_VERSION,
        "instrumentId": instrument_id,
        "filings": filings,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _index_path(instrument_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_filings(instrument_id: str) -> list[dict[str, Any]]:
    """Lista metadatos (más reciente primero)."""
    items = _read_index(instrument_id)
    items.sort(key=lambda x: str(x.get("uploadedAt") or ""), reverse=True)
    return items


def get_filing(instrument_id: str, filing_id: str) -> dict[str, Any] | None:
    for item in _read_index(instrument_id):
        if item.get("id") == filing_id:
            return item
    return None


def extract_text_from_bytes(
    *,
    content: bytes,
    content_type: str,
    original_name: str,
) -> tuple[str, ExtractStatus]:
    """
    Extrae texto. ``.txt`` / ``text/plain`` siempre.
    HTML SEC → texto vía ``html_to_text``.
    PDF: usa ``pypdf`` si está instalado; si no → ``unavailable``.
    """
    name_l = original_name.lower()
    ctype = (content_type or "").lower()
    is_html = "html" in ctype or name_l.endswith(".htm") or name_l.endswith(".html")
    if is_html:
        from bolsa_market.sec_edgar import html_to_text

        html = content.decode("utf-8", errors="replace")
        text = html_to_text(html).strip()
        if not text:
            return "", "empty"
        return text[:MAX_EXTRACT_CHARS], "ok"

    is_text = ctype.startswith("text/") or name_l.endswith(".txt")
    if is_text:
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            return "", "empty"
        return text[:MAX_EXTRACT_CHARS], "ok"

    is_pdf = ctype == "application/pdf" or name_l.endswith(".pdf")
    if not is_pdf:
        return "", "skipped"

    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return "", "unavailable"

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                page_text = ""
            if page_text.strip():
                parts.append(page_text)
            joined = "\n".join(parts)
            if len(joined) >= MAX_EXTRACT_CHARS:
                break
        text = "\n".join(parts).strip()[:MAX_EXTRACT_CHARS]
        if not text:
            return "", "empty"
        return text, "ok"
    except Exception:  # noqa: BLE001
        return "", "error"


def prefer_summary_excerpt(text: str, *, max_chars: int = 12_000) -> str:
    """Prioriza bloques de riesgos / MD&A si aparecen; si no, cabeza del doc."""
    if not text:
        return ""
    lower = text.lower()
    anchors = (
        "item 1a",
        "item 1a.",
        "risk factors",
        "item 7",
        "management's discussion",
        "management’s discussion",
    )
    start = 0
    for anchor in anchors:
        idx = lower.find(anchor)
        if idx >= 0:
            start = idx
            break
    return text[start : start + max_chars].strip()


def find_filing_by_accession(instrument_id: str, accession_number: str) -> dict[str, Any] | None:
    """Dedup F2b+ — mismo accession EDGAR ya importado."""
    want = (accession_number or "").strip()
    if not want:
        return None
    for item in _read_index(instrument_id):
        if str(item.get("accessionNumber") or "") == want:
            return item
    return None


def save_filing(
    *,
    instrument_id: str,
    kind: str,
    original_name: str,
    content_type: str,
    content: bytes,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persiste archivo + extract + entrada en index.

    ``extra`` opcional (F2b+): source, cik, accessionNumber, filingDate, documentUrl…
    """
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"kind no permitido: {kind}")
    if not content:
        raise ValueError("archivo vacío")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"archivo supera {MAX_UPLOAD_BYTES} bytes")

    filing_id = f"fil_{uuid.uuid4().hex[:16]}"
    digest = hashlib.sha256(content).hexdigest()
    directory = _instrument_dir(instrument_id)
    directory.mkdir(parents=True, exist_ok=True)

    name_l = original_name.lower()
    if content_type.startswith("text/") or name_l.endswith(".txt") or name_l.endswith(".htm") or name_l.endswith(".html"):
        ext = ".txt" if content_type.startswith("text/plain") or name_l.endswith(".txt") else ".htm"
        if content_type.startswith("text/plain"):
            ext = ".txt"
    elif name_l.endswith(".pdf") or content_type == "application/pdf":
        ext = ".pdf"
    else:
        ext = ".bin"
    blob_path = directory / f"{filing_id}{ext}"
    blob_path.write_bytes(content)

    text, extract_status = extract_text_from_bytes(
        content=content,
        content_type=content_type,
        original_name=original_name,
    )
    text_path = directory / f"{filing_id}.txt"
    if text:
        text_path.write_text(text, encoding="utf-8")
    elif text_path.exists():
        text_path.unlink()

    chunk_count = 0
    if text:
        from bolsa_market.filing_rag import save_chunk_index

        chunk_count = int(save_chunk_index(instrument_id, filing_id, text).get("chunkCount") or 0)

    meta: dict[str, Any] = {
        "id": filing_id,
        "instrumentId": instrument_id,
        "kind": kind,
        "originalName": original_name[:256],
        "contentType": content_type or "application/octet-stream",
        "byteSize": len(content),
        "sha256": digest,
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
        "extractStatus": extract_status,
        "charCount": len(text),
        "chunkCount": chunk_count,
        "storedPath": str(blob_path.name),
        "lastSummary": None,
        "source": "upload",
    }
    if extra:
        for key, value in extra.items():
            if value is not None:
                meta[key] = value
    filings = _read_index(instrument_id)
    filings.append(meta)
    _write_index(instrument_id, filings)
    return meta

def read_filing_text(instrument_id: str, filing_id: str) -> str | None:
    text_path = _instrument_dir(instrument_id) / f"{filing_id}.txt"
    if not text_path.is_file():
        return None
    try:
        return text_path.read_text(encoding="utf-8")
    except OSError:
        return None


def update_filing_summary(
    instrument_id: str,
    filing_id: str,
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    """Guarda lastSummary en el index (disco); no toca PostgreSQL/Yahoo."""
    filings = _read_index(instrument_id)
    found: dict[str, Any] | None = None
    for item in filings:
        if item.get("id") == filing_id:
            item["lastSummary"] = summary
            found = item
            break
    if found is None:
        return None
    _write_index(instrument_id, filings)
    return found


def delete_filing(instrument_id: str, filing_id: str) -> bool:
    filings = _read_index(instrument_id)
    kept = [f for f in filings if f.get("id") != filing_id]
    if len(kept) == len(filings):
        return False
    directory = _instrument_dir(instrument_id)
    for path in directory.glob(f"{filing_id}.*"):
        try:
            path.unlink()
        except OSError:
            pass
    _write_index(instrument_id, kept)
    return True
