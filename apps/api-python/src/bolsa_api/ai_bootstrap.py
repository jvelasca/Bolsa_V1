"""Configura AIGovernanceProxy al arrancar la API (sinks JSONL / PG)."""

from __future__ import annotations

import logging
import os

from bolsa_ai import (
    AIGovernanceProxy,
    CallbackAuditSink,
    CompositeAuditSink,
    NullAuditSink,
    build_audit_sink,
    reset_default_proxy,
    set_default_proxy,
)
from bolsa_infrastructure.database.llm_call_audit import pg_audit_enabled, persist_llm_call_sync

logger = logging.getLogger(__name__)


def configure_ai_governance_proxy() -> None:
    sinks = []
    file_sink = build_audit_sink()
    if not isinstance(file_sink, NullAuditSink):
        sinks.append(file_sink)
    if pg_audit_enabled():
        sinks.append(CallbackAuditSink(persist_llm_call_sync))
        logger.info(
            "AIGovernanceProxy: PG audit enabled (BOLSA_LLM_AUDIT_BACKEND=%s)",
            os.getenv("BOLSA_LLM_AUDIT_BACKEND"),
        )
    if not sinks:
        sinks.append(NullAuditSink())
    set_default_proxy(AIGovernanceProxy(audit_sink=CompositeAuditSink(sinks)))


def teardown_ai_governance_proxy() -> None:
    reset_default_proxy()
