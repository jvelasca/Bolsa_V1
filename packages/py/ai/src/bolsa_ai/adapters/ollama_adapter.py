"""Ollama local — adapter preferido F1 (RFC-007)."""

from __future__ import annotations

import json
import os
from typing import Any

from bolsa_ai.models import LlmProvider


class OllamaAdapter:
    provider: LlmProvider = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip(
            "/"
        )

    def is_available(self) -> bool:
        if os.getenv("BOLSA_LLM_PROVIDER") == "none":
            return False
        try:
            import httpx
        except ImportError:
            return False
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=1.5)
            return response.status_code == 200
        except Exception:
            return False

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        try:
            import httpx
        except ImportError:
            return None

        # Env override permite smoke tests con modelos pequeños sin editar ART-PROMPT.
        resolved = (
            os.getenv("BOLSA_OLLAMA_MODEL")
            or model
            or "qwen2.5-coder:14b"
        )
        payload = {
            "model": resolved,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content")
            if not content:
                return None
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
