"""SubmitIntentStore — puerto durable OR-2 (ADR-035).

Sin Alembic: InMemory (tests + singleton de proceso). Tabla PG = parked.
"""

from __future__ import annotations

from typing import Protocol

from bolsa_analytics.cognitive.submit_intent import DurableSubmitIntent


class SubmitIntentStore(Protocol):
    """get/put por decision_id. Durabilidad = implementación."""

    async def get(self, decision_id: str) -> DurableSubmitIntent | None: ...

    async def put(self, intent: DurableSubmitIntent) -> None: ...

    async def delete(self, decision_id: str) -> None: ...


class InMemorySubmitIntentStore:
    """Store de proceso. Retry mismo worker; no sobrevive al PID."""

    def __init__(self) -> None:
        self._by_decision: dict[str, DurableSubmitIntent] = {}

    async def get(self, decision_id: str) -> DurableSubmitIntent | None:
        key = (decision_id or "").strip()
        if not key:
            return None
        return self._by_decision.get(key)

    async def put(self, intent: DurableSubmitIntent) -> None:
        key = (intent.decision_id or "").strip()
        if not key:
            return
        self._by_decision[key] = intent

    async def delete(self, decision_id: str) -> None:
        key = (decision_id or "").strip()
        if not key:
            return
        self._by_decision.pop(key, None)


_PROCESS_STORE = InMemorySubmitIntentStore()


def process_submit_intent_store() -> InMemorySubmitIntentStore:
    """Singleton de proceso para Confirm en API (OR-2 D5)."""
    return _PROCESS_STORE
