"""F2b++ — heuristic ask + variables."""

from __future__ import annotations

from bolsa_analytics.knowledge.filing_ask import (
    build_filing_ask_variables,
    heuristic_filing_answer,
)


def test_build_ask_variables() -> None:
    vars_ = build_filing_ask_variables(
        ticker="AAPL",
        sector="Technology",
        filing={"kind": "10-K", "originalName": "a.txt"},
        question="¿Cuáles son los riesgos de liquidez?",
        context="[1] RISK\nLiquidity risk...",
    )
    assert vars_["ticker"] == "AAPL"
    assert "liquidez" in vars_["question"].lower()
    assert "Liquidity" in vars_["context"]


def test_heuristic_with_and_without_hits() -> None:
    empty = heuristic_filing_answer(ticker="X", question="deuda", hits=[])
    assert "No hay pasajes" in empty["answer"]
    with_hits = heuristic_filing_answer(
        ticker="X",
        question="deuda",
        hits=[{"label": "ITEM 1A", "text": "Debt covenants and leverage.", "score": 0.5}],
    )
    assert "Debt covenants" in with_hits["answer"]
    assert "disclaimer" in with_hits
