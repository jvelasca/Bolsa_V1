"""Contratos F1 alineados a RFC-007 (Draft / LLMCall)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

LlmProvider = Literal["ollama", "openai", "none"]
PRODUCER_VERSION = "0.1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class LlmCallV1:
    """ART-LLM-CALL — auditoría append-only de una invocación."""

    llm_call_id: str
    provider: LlmProvider
    model: str
    prompt_template_id: str
    prompt_rendered: str
    response_raw: str | None
    response_parsed: dict[str, Any] | None
    validation_passed: bool
    validation_errors: tuple[str, ...]
    elapsed_ms: int
    cost_usd: float
    status: Literal["success", "error", "timeout", "validation_failed", "skipped"]
    error: str | None
    trace_id: str
    timestamp: datetime = field(default_factory=_utc_now)
    causation_id: str | None = None
    producer_version: str = PRODUCER_VERSION


def llm_call_to_dict(call: LlmCallV1) -> dict[str, Any]:
    """Serialización estable para JSONL / futuros repos PG."""
    return {
        "artifactType": "ART-LLM-CALL",
        "schemaVersion": "1.0.0",
        "llmCallId": call.llm_call_id,
        "provider": call.provider,
        "model": call.model,
        "promptTemplateId": call.prompt_template_id,
        "promptRendered": call.prompt_rendered,
        "responseRaw": call.response_raw,
        "responseParsed": call.response_parsed,
        "validationPassed": call.validation_passed,
        "validationErrors": list(call.validation_errors),
        "elapsedMs": call.elapsed_ms,
        "costUsd": call.cost_usd,
        "status": call.status,
        "error": call.error,
        "traceId": call.trace_id,
        "causationId": call.causation_id,
        "producer": {"name": "bolsa_ai", "version": call.producer_version},
        "timestamp": call.timestamp.isoformat(),
    }


@dataclass(frozen=True, slots=True)
class StructuredCompletion:
    """Resultado estructurado del Proxy (antes de mapear a Strategy/Indicator draft)."""

    payload: dict[str, Any]
    llm_call: LlmCallV1
    provider: LlmProvider
    model_name: str
    prompt_id: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class DraftV1:
    """ART-DRAFT — borrador generado; promoción humana fuera de este paquete."""

    draft_id: str
    draft_type: Literal["strategy", "indicator", "feature"]
    prompt_id: str
    prompt_version: str
    provider: LlmProvider
    model_name: str
    schema_version: str
    content: dict[str, Any]
    validation_status: Literal["pending", "validated", "rejected"]
    validation_errors: tuple[str, ...]
    trace_id: str
    llm_call_id: str
