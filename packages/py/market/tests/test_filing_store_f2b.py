"""F2b lite — filing store + extract + heuristic summary."""

from __future__ import annotations

from pathlib import Path

from bolsa_analytics.knowledge.filing_summary import heuristic_filing_summary

from bolsa_market.filing_store import (
    FILING_STORE_VERSION,
    delete_filing,
    extract_text_from_bytes,
    list_filings,
    prefer_summary_excerpt,
    read_filing_text,
    save_filing,
    update_filing_summary,
)


def test_save_list_delete_txt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    meta = save_filing(
        instrument_id="inst-a",
        kind="10-K",
        original_name="acme-10k.txt",
        content_type="text/plain",
        content=b"ITEM 1A. RISK FACTORS\nDebt and competition.\nITEM 7. MD&A\nRevenue grew.",
    )
    assert meta["id"].startswith("fil_")
    assert meta["extractStatus"] == "ok"
    assert meta["charCount"] > 0
    assert list_filings("inst-a")[0]["originalName"] == "acme-10k.txt"
    text = read_filing_text("inst-a", meta["id"])
    assert text and "RISK FACTORS" in text
    assert delete_filing("inst-a", meta["id"]) is True
    assert list_filings("inst-a") == []


def test_reject_bad_kind(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    try:
        save_filing(
            instrument_id="inst-a",
            kind="8-K",
            original_name="x.txt",
            content_type="text/plain",
            content=b"hello",
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_prefer_risk_factors_anchor() -> None:
    text = "Intro fluff.\n\nITEM 1A. RISK FACTORS\nLiquidity risk.\n"
    excerpt = prefer_summary_excerpt(text, max_chars=80)
    assert excerpt.lower().startswith("item 1a")


def test_pdf_extract_status_is_controlled() -> None:
    """Sin pypdf → unavailable; con pypdf sobre PDF inválido → empty/error."""
    text, status = extract_text_from_bytes(
        content=b"%PDF-1.4 fake",
        content_type="application/pdf",
        original_name="x.pdf",
    )
    assert status in {"unavailable", "empty", "error"}
    if status == "unavailable":
        assert text == ""


def test_heuristic_summary_with_extract() -> None:
    filing = {
        "kind": "10-K",
        "originalName": "a.txt",
        "extractStatus": "ok",
        "charCount": 100,
    }
    out = heuristic_filing_summary(
        ticker="AAPL",
        filing=filing,
        text="ITEM 1A. RISK FACTORS\nSupply chain and FX.",
    )
    assert len(out["paragraphs"]) == 3
    assert "AAPL" in out["paragraphs"][0]
    assert "Score_FUND" in out["paragraphs"][2]


def test_update_last_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    meta = save_filing(
        instrument_id="inst-b",
        kind="10-Q",
        original_name="q.txt",
        content_type="text/plain",
        content=b"Quarterly update text.",
    )
    updated = update_filing_summary(
        "inst-b",
        meta["id"],
        {
            "engine": "heuristic",
            "paragraphs": ["a", "b", "c"],
            "disclaimer": "d",
            "summarizedAt": "2026-07-30T00:00:00+00:00",
        },
    )
    assert updated is not None
    assert updated["lastSummary"]["engine"] == "heuristic"
    assert FILING_STORE_VERSION == "instrument_filings_v1"
