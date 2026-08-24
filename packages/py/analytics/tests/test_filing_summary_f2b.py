"""F2b — variables + heurística de resumen (sin Ollama)."""

from bolsa_analytics.knowledge.filing_summary import (
    build_filing_summary_variables,
    heuristic_filing_summary,
)


def test_build_variables_excerpt_truncated() -> None:
    vars_ = build_filing_summary_variables(
        ticker="MSFT",
        sector="Technology",
        filing={
            "kind": "10-K",
            "originalName": "msft.txt",
            "charCount": 12,
            "extractStatus": "ok",
        },
        excerpt="x" * 20_000,
    )
    assert vars_["ticker"] == "MSFT"
    assert len(vars_["excerpt"]) <= 12_000


def test_heuristic_empty_extract() -> None:
    out = heuristic_filing_summary(
        ticker="X",
        filing={"kind": "10-K", "originalName": "x.pdf", "extractStatus": "unavailable"},
        text=None,
    )
    assert "pypdf" in out["paragraphs"][0] or "texto" in out["paragraphs"][0].lower()


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
