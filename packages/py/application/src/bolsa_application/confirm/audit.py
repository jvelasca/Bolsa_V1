"""DEX-4 — escritura de la sesión de auditoría del confirm.

Extraído de ``confirm_recommendation`` (el orquestador debe quedar fino): el orquestador
sólo necesita saber si la sesión se persistió o no. Aquí vive el detalle del reintento.

Reglas (bloque crítico de /mercado/operativa):
- El ``DecisionSessionRecord`` se construye UNA vez: el reintento reusa el mismo id y no
  puede duplicar la sesión si la primera escritura sí llegó a la BD.
- Un append que falló puede haber llegado a la BD (commit con error de red): antes de
  reintentar se comprueba la existencia del id.
- Si el segundo intento falla, se eleva; ``execute`` lo declara en ``auditPersist``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.cognitive.decision_session import (
    attach_execution_to_payload,
    build_auto_session,
)
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_application.cognitive_persistence import (
    CognitiveStore,
    decision_session_to_record,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

__all__ = ["SessionAuditWriter"]

logger = logging.getLogger(__name__)


class SessionAuditWriter:
    """Persiste (update o append) la sesión de auditoría de un confirm."""

    def __init__(self, store: CognitiveStore) -> None:
        self._store = store

    async def persist(
        self,
        *,
        session_id: str | None,
        rec: Recommendation,
        account_id: str,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        if session_id:
            existing = await self._store.get_decision_session(session_id)
            if existing is not None and existing.payload:
                payload = attach_execution_to_payload(
                    existing.payload,
                    execution,
                    kind="confirm",
                    extra_lineage={"confirmedAt": now, "confirmLinked": True},
                )
                updated = DecisionSessionRecord(
                    id=existing.id,
                    kind="confirm",
                    status=existing.status,
                    instrument_id=existing.instrument_id,
                    created_at=existing.created_at,
                    account_id=existing.account_id or account_id,
                    symbol=existing.symbol,
                    recommendation_id=existing.recommendation_id,
                    decision_id=existing.decision_id,
                    payload=payload,
                )
                await self._write_with_retry(updated, update=True)
                return payload

        session = build_auto_session(
            kind="confirm",
            instrument_id=rec.instrument_id,
            account_id=account_id,
            symbol=rec.symbol,
            recommendation=rec.to_dict(),
            execution=execution,
            lineage={"confirmedAt": now, "orphanConfirm": True},
            decision_id=rec.decision_id or None,
            parent_session_id=session_id,
        )
        record = decision_session_to_record(session)
        await self._write_with_retry(record, update=False)
        return session.to_dict()

    async def _write_with_retry(
        self,
        record: DecisionSessionRecord,
        *,
        update: bool,
    ) -> None:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                if update:
                    await self._store.update_decision_session(record)
                else:
                    await self._store.append_decision_session(record)
                return
            except Exception as exc:  # noqa: BLE001 — se reintenta y, si no, se declara
                last_exc = exc
                logger.warning(
                    "confirm_recommendation: decision_session_write_failed "
                    "session_id=%s attempt=%d update=%s",
                    record.id,
                    attempt + 1,
                    update,
                    exc_info=True,
                )
                if not update:
                    try:
                        found = await self._store.get_decision_session(record.id)
                    except Exception:  # noqa: BLE001 — sondeo best-effort
                        found = None
                    if found is not None:
                        return
        if last_exc is not None:
            raise last_exc
