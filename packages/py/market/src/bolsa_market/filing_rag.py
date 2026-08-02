"""FIE F2b++ — indexación local + retrieval sobre extractos de filings.

Sin Chroma/FAISS/embeddings: chunks en disco + TF-IDF stdlib.
No escribe profile_snapshot.fundamentals ni altera Score_FUND / gate.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from bolsa_market.filing_store import instrument_filings_dir, read_filing_text

FILING_RAG_VERSION = "filing_rag_tfidf_v1"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
DEFAULT_TOP_K = 4
MAX_CHUNK_CHARS_IN_PROMPT = 1_400

_TOKEN_RE = re.compile(r"[a-z0-9áéíóúñü]+", re.IGNORECASE)
_ITEM_RE = re.compile(
    r"(?im)^\s*(item\s+\d+[a-z]?\.?|risk factors|management'?s?\s+discussion)",
)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _label_for_offset(text: str, start: int) -> str | None:
    window = text[max(0, start - 200) : start + 80]
    match = _ITEM_RE.search(window)
    if not match:
        head = text[start : start + 60].strip().replace("\n", " ")
        return head[:48] + ("…" if len(head) > 48 else "") if head else None
    return match.group(0).strip()[:64]


def chunk_text(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Parte el extracto en ventanas con solape; etiquetas Item si aparecen."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    chunk_size = max(chunk_size, 200)
    if overlap < 0 or overlap >= chunk_size:
        overlap = max(0, chunk_size // 6)

    chunks: list[dict[str, Any]] = []
    start = 0
    n = len(cleaned)
    idx = 0
    while start < n:
        end = min(n, start + chunk_size)
        # Preferir corte en salto de línea cercano al final.
        if end < n:
            nl = cleaned.rfind("\n", start + chunk_size // 2, end)
            if nl > start:
                end = nl
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(
                {
                    "id": f"chk_{idx:04d}",
                    "start": start,
                    "end": end,
                    "label": _label_for_offset(cleaned, start),
                    "text": piece,
                }
            )
            idx += 1
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunks_path(instrument_id: str, filing_id: str) -> Path:
    return instrument_filings_dir(instrument_id) / f"{filing_id}.chunks.json"


def build_chunk_index(text: str) -> dict[str, Any]:
    chunks = chunk_text(text)
    return {
        "indexVersion": FILING_RAG_VERSION,
        "chunkCount": len(chunks),
        "chunks": chunks,
    }


def save_chunk_index(instrument_id: str, filing_id: str, text: str) -> dict[str, Any]:
    """Escribe ``{filingId}.chunks.json``. Vacío si no hay texto."""
    payload = build_chunk_index(text)
    path = chunks_path(instrument_id, filing_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_chunk_index(instrument_id: str, filing_id: str) -> dict[str, Any] | None:
    path = chunks_path(instrument_id, filing_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def ensure_chunk_index(instrument_id: str, filing_id: str) -> dict[str, Any] | None:
    """Carga índice o lo construye desde el extract ``.txt``."""
    existing = load_chunk_index(instrument_id, filing_id)
    if existing and isinstance(existing.get("chunks"), list) and existing["chunks"]:
        return existing
    text = read_filing_text(instrument_id, filing_id)
    if not text:
        return existing
    return save_chunk_index(instrument_id, filing_id, text)


def _tf(tokens: list[str]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    n = float(len(tokens) or 1)
    return {t: c / n for t, c in counts.items()}


def _idf(docs: list[list[str]]) -> dict[str, float]:
    n_docs = len(docs) or 1
    df: dict[str, int] = {}
    for tokens in docs:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    return {t: math.log((1.0 + n_docs) / (1.0 + d)) + 1.0 for t, d in df.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def retrieve_chunks(
    index: dict[str, Any],
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Top-k chunks por similitud coseno TF-IDF (query vs chunk)."""
    q = (query or "").strip()
    chunks = index.get("chunks") if isinstance(index, dict) else None
    if not q or not isinstance(chunks, list) or not chunks:
        return []

    q_tokens = tokenize(q)
    if not q_tokens:
        return []

    doc_tokens = [tokenize(str(c.get("text") or "")) for c in chunks]
    idf = _idf([q_tokens, *doc_tokens])
    q_tf = _tf(q_tokens)
    q_vec = {t: q_tf.get(t, 0.0) * idf.get(t, 0.0) for t in q_tf}

    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk, tokens in zip(chunks, doc_tokens, strict=False):
        if not isinstance(chunk, dict) or not tokens:
            continue
        tf = _tf(tokens)
        vec = {t: tf.get(t, 0.0) * idf.get(t, 0.0) for t in tf}
        score = _cosine(q_vec, vec)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    k = max(1, min(top_k, 8))
    out: list[dict[str, Any]] = []
    for score, chunk in scored[:k]:
        text = str(chunk.get("text") or "")
        if len(text) > MAX_CHUNK_CHARS_IN_PROMPT:
            text = text[: MAX_CHUNK_CHARS_IN_PROMPT - 1] + "…"
        out.append(
            {
                "id": chunk.get("id"),
                "label": chunk.get("label"),
                "start": chunk.get("start"),
                "end": chunk.get("end"),
                "score": round(float(score), 4),
                "text": text,
            }
        )
    return out


def format_context_for_prompt(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "—"
    parts: list[str] = []
    for i, hit in enumerate(hits, start=1):
        label = hit.get("label") or hit.get("id") or f"chunk-{i}"
        score = hit.get("score")
        header = f"[{i}] {label}"
        if score is not None:
            header += f" (score={score})"
        parts.append(f"{header}\n{hit.get('text') or ''}")
    return "\n\n---\n\n".join(parts)
