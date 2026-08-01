"""Persistencia sync ART-LLM-CALL → llm_calls (callback para bolsa_ai)."""

from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models import LlmCallRow

logger = logging.getLogger(__name__)

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
_LOCK = threading.Lock()


def _sync_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _get_session_factory() -> sessionmaker[Session]:
    global _ENGINE, _SESSION_FACTORY
    with _LOCK:
        if _SESSION_FACTORY is None:
            settings = get_settings()
            _ENGINE = create_engine(
                _sync_database_url(settings.database_url),
                pool_pre_ping=True,
                pool_size=2,
            )
            _SESSION_FACTORY = sessionmaker(bind=_ENGINE, expire_on_commit=False)
        return _SESSION_FACTORY


def pg_audit_enabled() -> bool:
    raw = (os.getenv("BOLSA_LLM_AUDIT_BACKEND") or "").strip().lower()
    return raw in {"pg", "postgres", "both"}


def persist_llm_call_sync(payload: dict[str, Any]) -> None:
    """Insert append-only. Best-effort: no lanza hacia authoring."""
    try:
        factory = _get_session_factory()
        producer = payload.get("producer") or {}
        created_raw = payload.get("timestamp")
        if isinstance(created_raw, str):
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        else:
            created_at = datetime.now(UTC)
        row = LlmCallRow(
            id=str(payload.get("llmCallId") or payload.get("id")),
            provider=str(payload.get("provider") or "none"),
            model=str(payload.get("model") or "n/a"),
            prompt_template_id=str(payload.get("promptTemplateId") or ""),
            prompt_rendered=str(payload.get("promptRendered") or "")[:4000],
            response_raw=(
                str(payload["responseRaw"])[:8000] if payload.get("responseRaw") is not None else None
            ),
            response_parsed=payload.get("responseParsed"),
            validation_passed=bool(payload.get("validationPassed")),
            validation_errors=list(payload.get("validationErrors") or []),
            elapsed_ms=int(payload.get("elapsedMs") or 0),
            cost_usd=Decimal(str(payload.get("costUsd") or 0)),
            status=str(payload.get("status") or "unknown"),
            error=payload.get("error"),
            trace_id=str(payload.get("traceId") or ""),
            causation_id=payload.get("causationId"),
            producer_version=str(producer.get("version") or payload.get("producerVersion") or "0.1.0"),
            payload=payload,
            created_at=created_at,
        )
        with factory() as session:
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("ART-LLM-CALL PG persist failed (best-effort)")


def dispose_llm_call_audit_engine() -> None:
    global _ENGINE, _SESSION_FACTORY
    with _LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None
        _SESSION_FACTORY = None
