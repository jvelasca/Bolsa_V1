"""Puerto de adaptador LLM (RFC-007)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_ai.models import LlmProvider


class LlmAdapter(Protocol):
    provider: LlmProvider

    def is_available(self) -> bool: ...

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        """Devuelve dict parseado o None si falla."""
        ...
