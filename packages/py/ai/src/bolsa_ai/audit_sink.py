"""Persistencia append-only ART-LLM-CALL (JSONL + callbacks / PG vía infra)."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from bolsa_ai.models import LlmCallV1, llm_call_to_dict


class LlmCallAuditSink(Protocol):
    def append(self, call: LlmCallV1) -> None: ...


class NullAuditSink:
    def append(self, call: LlmCallV1) -> None:
        return None


class JsonlAuditSink:
    """Append-only JSONL. Sin purge automático (RFC-007 §5)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, call: LlmCallV1) -> None:
        line = json.dumps(llm_call_to_dict(call), ensure_ascii=False) + "\n"
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)


class CallbackAuditSink:
    """Delega a un callback sync (p.ej. insert PG en infrastructure)."""

    def __init__(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._callback = callback

    def append(self, call: LlmCallV1) -> None:
        self._callback(llm_call_to_dict(call))


class CompositeAuditSink:
    def __init__(self, sinks: list[LlmCallAuditSink]) -> None:
        self._sinks = list(sinks)

    def append(self, call: LlmCallV1) -> None:
        for sink in self._sinks:
            try:
                sink.append(call)
            except OSError:
                continue


def default_audit_path() -> Path | None:
    raw = (os.getenv("BOLSA_LLM_AUDIT_PATH") or "").strip()
    if not raw:
        return None
    if raw.lower() in {"0", "false", "off", "none"}:
        return None
    return Path(raw)


def build_audit_sink(path: str | Path | None = None) -> LlmCallAuditSink:
    resolved = Path(path) if path is not None else default_audit_path()
    if resolved is None:
        return NullAuditSink()
    return JsonlAuditSink(resolved)
