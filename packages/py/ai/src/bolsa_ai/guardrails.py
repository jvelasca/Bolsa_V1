"""Guardrails de entrada F1 (RFC-007 §6) — expansión futura en lista configurable."""

from __future__ import annotations

import os
import re

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)

_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "disregard your instructions",
)


def mask_secrets(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def check_input_allowed(user_text: str) -> list[str]:
    """Devuelve lista de errores; vacía si OK."""
    errors: list[str] = []
    lowered = user_text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lowered:
            errors.append(f"posible prompt injection: {marker!r}")
    max_chars = int(os.getenv("BOLSA_LLM_MAX_PROMPT_CHARS", "8000"))
    if len(user_text) > max_chars:
        errors.append(f"prompt demasiado largo (>{max_chars} chars)")
    return errors


def max_cost_usd() -> float:
    return float(os.getenv("BOLSA_LLM_MAX_COST_USD", "0.01"))


def timeout_seconds() -> float:
    return float(os.getenv("BOLSA_LLM_TIMEOUT_SECONDS", "30"))
