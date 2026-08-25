"""P4 — veredicto explícito de sesión → Decision Journal (ADR-033 §7)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_application.journal_writer import JournalWriter, append_journal_event

_SUPPORTED_VERDICTS = frozenset({"no_trade"})


class RecordSessionVerdict:
    """Registra «No operar hoy» u otros veredictos de sesión sin fill."""

    def __init__(self, *, journal_writer: JournalWriter | None) -> None:
        self._journal_writer = journal_writer

    async def execute(
        self,
        *,
        account_id: str,
        verdict: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if not account_id or not account_id.strip():
            raise ValueError("account_id requerido")
        normalized = str(verdict or "").strip().lower()
        if normalized not in _SUPPORTED_VERDICTS:
            raise ValueError(f"verdict no soportado: {verdict}")
        now = datetime.now(UTC)
        day = now.strftime("%Y-%m-%d")
        decision_id = f"SESSION-{account_id.strip()}-{day}"
        payload: dict[str, Any] = {"sessionVerdict": normalized}
        if isinstance(note, str) and note.strip():
            payload["note"] = note.strip()
        await append_journal_event(
            self._journal_writer,
            event_type="session_verdict",
            decision_id=decision_id,
            account_id=account_id.strip(),
            actor="human",
            payload=payload,
        )
        return {
            "decisionId": decision_id,
            "sessionVerdict": normalized,
            "recordedAt": now.isoformat().replace("+00:00", "Z"),
        }
