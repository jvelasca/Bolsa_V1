"""Tests ExplainCoreRReviewEvidence (heuristic path)."""

from __future__ import annotations

import asyncio

from bolsa_application.explain_core_r_review import ExplainCoreRReviewEvidence


def test_explain_heuristic_without_llm():
    payload = {
        "listId": "list-1",
        "timeframe": "1d",
        "rows": [
            {
                "instrumentId": "i1",
                "symbol": "TEF",
                "verdict": "review_lab",
                "reason": "Demo/paper PnL -6.0%",
            }
        ],
    }
    result = asyncio.run(ExplainCoreRReviewEvidence().execute(payload))
    assert isinstance(result["payload"]["paragraphs"], list)
    assert len(result["payload"]["paragraphs"]) == 3
    assert result["payload"]["band"] == "attention"
    assert result["evidence"]["schemaVersion"] == "core_r_review_evidence_v1"
    assert result["engine"]  # heuristic or provider_structured_v1
