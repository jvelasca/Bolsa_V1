"""ExecutionRecord — resultado de un intento de envío (ADR-034 OI-3).

UNKNOWN ≠ ERROR. Excepción tras intentar enviar ≠ no-ejecutado.
≠ ExecutionPlan (F4) ≠ ExecuteTrade ≠ broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionOutcome = Literal["not_executed", "executed", "error", "unknown"]

EXECUTION_RECORD_KEY = "executionRecord"


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Foto honesta del intento de fill. filled gana a exception (OI-1)."""

    outcome: ExecutionOutcome
    reason: str | None
    transaction_id: str | None
    send_attempted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "reason": self.reason,
            "transactionId": self.transaction_id,
            "sendAttempted": self.send_attempted,
        }


def build_execution_record(
    *,
    filled: bool = False,
    send_attempted: bool = False,
    transaction_id: str | None = None,
    exception: str | None = None,
    not_executed_reason: str | None = None,
) -> ExecutionRecord:
    """Kernel: filled → executed; send without fill → unknown;

    pre-send exception → error; else not_executed.
    """
    tx = _non_empty(transaction_id)
    exc = _non_empty(exception)
    skip_reason = _non_empty(not_executed_reason)

    if filled:
        return ExecutionRecord(
            outcome="executed",
            reason=None,
            transaction_id=tx,
            send_attempted=True,
        )
    if send_attempted:
        return ExecutionRecord(
            outcome="unknown",
            reason=exc or "execute_exception",
            transaction_id=None,
            send_attempted=True,
        )
    if exc:
        return ExecutionRecord(
            outcome="error",
            reason=exc,
            transaction_id=None,
            send_attempted=False,
        )
    return ExecutionRecord(
        outcome="not_executed",
        reason=skip_reason,
        transaction_id=None,
        send_attempted=False,
    )


def execution_outcome_copy(outcome: ExecutionOutcome) -> str:
    """Copy de mesa: unknown nunca se lee como «no se ejecutó»."""
    if outcome == "executed":
        return "Ejecutado"
    if outcome == "not_executed":
        return "No se envió"
    if outcome == "error":
        return "Error antes de enviar (no ejecutado)"
    return "Resultado desconocido — no asumir que no se ejecutó"
