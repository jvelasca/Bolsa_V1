"""AIGovernanceProxy — único entrypoint LLM (RFC-007)."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Literal

from bolsa_ai.adapters.ollama_adapter import OllamaAdapter
from bolsa_ai.adapters.openai_adapter import OpenAIAdapter
from bolsa_ai.audit_sink import LlmCallAuditSink, NullAuditSink, build_audit_sink
from bolsa_ai.guardrails import check_input_allowed, mask_secrets, timeout_seconds
from bolsa_ai.models import PRODUCER_VERSION, LlmCallV1, LlmProvider, StructuredCompletion
from bolsa_ai.registry import PromptRegistry

CallStatus = Literal["success", "error", "timeout", "validation_failed", "skipped"]


def _resolve_provider_preference() -> LlmProvider:
    raw = (os.getenv("BOLSA_LLM_PROVIDER") or "").strip().lower()
    if raw in {"ollama", "openai", "none"}:
        return raw  # type: ignore[return-value]
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "ollama"


class AIGovernanceProxy:
    """Router + guardrails + audit (memoria + sink append-only). No hot path EXECUTION."""

    def __init__(
        self,
        *,
        registry: PromptRegistry | None = None,
        ollama: OllamaAdapter | None = None,
        openai: OpenAIAdapter | None = None,
        audit_sink: LlmCallAuditSink | None = None,
    ) -> None:
        self._registry = registry or PromptRegistry()
        self._ollama = ollama or OllamaAdapter()
        self._openai = openai or OpenAIAdapter()
        self._audit_sink: LlmCallAuditSink = (
            audit_sink if audit_sink is not None else build_audit_sink()
        )
        self._calls: list[LlmCallV1] = []

    @property
    def audit_log(self) -> tuple[LlmCallV1, ...]:
        return tuple(self._calls)

    def get_status(self) -> dict[str, Any]:
        preferred = _resolve_provider_preference()
        sink_path = getattr(self._audit_sink, "path", None)
        return {
            "preferredProvider": preferred,
            "ollamaAvailable": self._ollama.is_available(),
            "openaiAvailable": self._openai.is_available(),
            "callsRecorded": len(self._calls),
            "mode": "none" if preferred == "none" else preferred,
            "auditSink": str(sink_path) if sink_path is not None else "memory",
            "producerVersion": PRODUCER_VERSION,
        }

    def complete_structured(
        self,
        *,
        prompt_template_id: str,
        variables: dict[str, Any],
        trace_id: str | None = None,
        causation_id: str | None = None,
        allow_cloud: bool = True,
    ) -> StructuredCompletion | None:
        """
        Intenta LLM estructurado. None → caller debe usar heurística (fallback).

        Nunca lanza hacia OMS; solo authoring.
        """
        trace = trace_id or f"tr_{uuid.uuid4().hex}"
        prompt = self._registry.get(prompt_template_id)
        user_raw = self._registry.render_user(prompt_template_id, variables)
        user_text = mask_secrets(user_raw)

        input_errors = check_input_allowed(user_text)
        if input_errors:
            self._record_call(
                provider="none",
                model="n/a",
                prompt_template_id=prompt_template_id,
                prompt_rendered=user_text,
                response_raw=None,
                response_parsed=None,
                validation_passed=False,
                validation_errors=tuple(input_errors),
                elapsed_ms=0,
                status="validation_failed",
                error="; ".join(input_errors),
                trace_id=trace,
                causation_id=causation_id,
            )
            return None

        preferred = _resolve_provider_preference()
        if preferred == "none":
            self._record_call(
                provider="none",
                model="heuristic",
                prompt_template_id=prompt_template_id,
                prompt_rendered=user_text,
                response_raw=None,
                response_parsed=None,
                validation_passed=False,
                validation_errors=(),
                elapsed_ms=0,
                status="skipped",
                error="BOLSA_LLM_PROVIDER=none",
                trace_id=trace,
                causation_id=causation_id,
            )
            return None

        adapters: list[tuple[LlmProvider, Any, str]] = []
        if preferred == "ollama":
            adapters.append(("ollama", self._ollama, prompt.default_model))
            if allow_cloud:
                adapters.append(
                    ("openai", self._openai, os.getenv("BOLSA_LLM_MODEL", "gpt-4o-mini"))
                )
        elif preferred == "openai":
            if allow_cloud:
                adapters.append(
                    ("openai", self._openai, os.getenv("BOLSA_LLM_MODEL", "gpt-4o-mini"))
                )
            adapters.append(("ollama", self._ollama, prompt.default_model))

        timeout = timeout_seconds()
        last_error: str | None = None
        for provider, adapter, model in adapters:
            if not adapter.is_available():
                continue
            started = time.perf_counter()
            parsed = adapter.complete_json(
                system=prompt.system_prompt,
                user=user_text,
                model=model,
                temperature=prompt.temperature,
                timeout_seconds=timeout,
            )
            elapsed = int((time.perf_counter() - started) * 1000)
            if parsed is None:
                last_error = f"{provider} failed"
                self._record_call(
                    provider=provider,
                    model=model,
                    prompt_template_id=prompt_template_id,
                    prompt_rendered=user_text,
                    response_raw=None,
                    response_parsed=None,
                    validation_passed=False,
                    validation_errors=(),
                    elapsed_ms=elapsed,
                    status="error",
                    error=last_error,
                    trace_id=trace,
                    causation_id=causation_id,
                )
                continue

            call = self._record_call(
                provider=provider,
                model=model,
                prompt_template_id=prompt_template_id,
                prompt_rendered=user_text,
                response_raw=str(parsed),
                response_parsed=parsed,
                validation_passed=True,
                validation_errors=(),
                elapsed_ms=elapsed,
                status="success",
                error=None,
                trace_id=trace,
                causation_id=causation_id,
            )
            return StructuredCompletion(
                payload=parsed,
                llm_call=call,
                provider=provider,
                model_name=model,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
            )

        if last_error is None:
            self._record_call(
                provider="none",
                model="n/a",
                prompt_template_id=prompt_template_id,
                prompt_rendered=user_text,
                response_raw=None,
                response_parsed=None,
                validation_passed=False,
                validation_errors=(),
                elapsed_ms=0,
                status="skipped",
                error="no LLM provider available",
                trace_id=trace,
                causation_id=causation_id,
            )
        return None

    def _record_call(
        self,
        *,
        provider: LlmProvider,
        model: str,
        prompt_template_id: str,
        prompt_rendered: str,
        response_raw: str | None,
        response_parsed: dict[str, Any] | None,
        validation_passed: bool,
        validation_errors: tuple[str, ...],
        elapsed_ms: int,
        status: CallStatus,
        error: str | None,
        trace_id: str,
        causation_id: str | None = None,
    ) -> LlmCallV1:
        call = LlmCallV1(
            llm_call_id=f"llm_{uuid.uuid4().hex}",
            provider=provider,
            model=model,
            prompt_template_id=prompt_template_id,
            prompt_rendered=prompt_rendered[:4000],
            response_raw=response_raw[:8000] if response_raw else None,
            response_parsed=response_parsed,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            elapsed_ms=elapsed_ms,
            cost_usd=0.0,
            status=status,
            error=error,
            trace_id=trace_id,
            causation_id=causation_id,
        )
        self._calls.append(call)
        try:
            self._audit_sink.append(call)
        except OSError:
            # Persistencia best-effort: no tumbar authoring por disco.
            pass
        return call


_DEFAULT: AIGovernanceProxy | None = None


def get_default_proxy() -> AIGovernanceProxy:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AIGovernanceProxy()
    return _DEFAULT


def set_default_proxy(proxy: AIGovernanceProxy) -> None:
    """API lifespan / tests — inyecta Proxy con sinks compuestos."""
    global _DEFAULT
    _DEFAULT = proxy


def reset_default_proxy() -> None:
    """Tests only."""
    global _DEFAULT
    _DEFAULT = None


__all__ = [
    "AIGovernanceProxy",
    "NullAuditSink",
    "get_default_proxy",
    "reset_default_proxy",
    "set_default_proxy",
]
