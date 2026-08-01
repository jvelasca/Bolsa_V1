"""F1+ — persistencia JSONL append-only ART-LLM-CALL."""

from __future__ import annotations

import json
from pathlib import Path

from bolsa_ai.audit_sink import JsonlAuditSink, NullAuditSink, build_audit_sink
from bolsa_ai.proxy import AIGovernanceProxy, reset_default_proxy


def test_jsonl_sink_appends_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    path = tmp_path / "llm_calls.jsonl"
    sink = JsonlAuditSink(path)
    proxy = AIGovernanceProxy(audit_sink=sink)
    proxy.complete_structured(
        prompt_template_id="prompt_strategy_authoring_v1",
        variables={"user_input": "compra cruce SMA"},
        causation_id="req_test_1",
    )
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["artifactType"] == "ART-LLM-CALL"
    assert row["schemaVersion"] == "1.0.0"
    assert row["status"] == "skipped"
    assert row["causationId"] == "req_test_1"
    assert row["producer"]["name"] == "bolsa_ai"
    assert row["traceId"]


def test_jsonl_is_append_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    path = tmp_path / "llm_calls.jsonl"
    sink = JsonlAuditSink(path)
    proxy = AIGovernanceProxy(audit_sink=sink)
    for _ in range(3):
        proxy.complete_structured(
            prompt_template_id="prompt_strategy_authoring_v1",
            variables={"user_input": "ok"},
        )
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_build_sink_from_env(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("BOLSA_LLM_AUDIT_PATH", str(path))
    monkeypatch.setenv("BOLSA_LLM_PROVIDER", "none")
    reset_default_proxy()
    sink = build_audit_sink()
    assert isinstance(sink, JsonlAuditSink)
    assert sink.path == path
    monkeypatch.setenv("BOLSA_LLM_AUDIT_PATH", "off")
    assert isinstance(build_audit_sink(), NullAuditSink)
