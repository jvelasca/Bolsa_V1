"""F2b++ — chunk index + TF-IDF retrieval (sin vectores)."""

from __future__ import annotations

from pathlib import Path

from bolsa_market.filing_rag import (
    FILING_RAG_VERSION,
    chunk_text,
    ensure_chunk_index,
    format_context_for_prompt,
    retrieve_chunks,
    save_chunk_index,
)
from bolsa_market.filing_store import read_filing_text, save_filing


def test_chunk_and_retrieve_risk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    body = (
        "ITEM 1. BUSINESS\n"
        "We sell widgets worldwide.\n\n"
        "ITEM 1A. RISK FACTORS\n"
        "Liquidity risk and rising interest rates may hurt refinancing.\n"
        "Competition could reduce margins.\n\n"
        "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\n"
        "Revenue grew due to volume. Operating cash flow improved.\n"
    ) * 3
    meta = save_filing(
        instrument_id="inst-rag",
        kind="10-K",
        original_name="demo-10k.txt",
        content_type="text/plain",
        content=body.encode("utf-8"),
    )
    assert meta.get("chunkCount", 0) >= 1
    text = read_filing_text("inst-rag", meta["id"])
    assert text
    index = ensure_chunk_index("inst-rag", meta["id"])
    assert index is not None
    assert index["indexVersion"] == FILING_RAG_VERSION
    assert index["chunkCount"] >= 1

    hits = retrieve_chunks(index, "liquidity risk interest rates", top_k=3)
    assert hits
    joined = " ".join(h["text"].lower() for h in hits)
    assert "liquidity" in joined or "interest" in joined
    ctx = format_context_for_prompt(hits)
    assert "[1]" in ctx


def test_chunk_empty_and_save(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    assert chunk_text("") == []
    payload = save_chunk_index("inst-x", "fil_empty", "")
    assert payload["chunkCount"] == 0
    assert retrieve_chunks(payload, "anything") == []
