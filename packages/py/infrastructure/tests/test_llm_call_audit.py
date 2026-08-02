"""Unit: mapping ART-LLM-CALL dict → LlmCallRow (sin DB real)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from bolsa_infrastructure.database.llm_call_audit import persist_llm_call_sync


def test_persist_llm_call_sync_maps_payload() -> None:
    payload = {
        "llmCallId": "llm_test123",
        "provider": "none",
        "model": "heuristic",
        "promptTemplateId": "prompt_strategy_authoring_v1",
        "promptRendered": "cruce SMA",
        "responseRaw": None,
        "responseParsed": None,
        "validationPassed": False,
        "validationErrors": [],
        "elapsedMs": 0,
        "costUsd": 0,
        "status": "skipped",
        "error": "BOLSA_LLM_PROVIDER=none",
        "traceId": "tr_abc",
        "causationId": "req_1",
        "producer": {"name": "bolsa_ai", "version": "0.1.0"},
        "timestamp": "2026-07-21T12:00:00+00:00",
    }
    session = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    factory = MagicMock(return_value=context)
    with patch(
        "bolsa_infrastructure.database.llm_call_audit._get_session_factory",
        return_value=factory,
    ):
        persist_llm_call_sync(payload)
    row = session.add.call_args[0][0]
    assert row.id == "llm_test123"
    assert row.provider == "none"
    assert row.trace_id == "tr_abc"
    assert row.causation_id == "req_1"
    assert row.cost_usd == Decimal(0)
    assert session.commit.called
