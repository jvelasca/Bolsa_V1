"""P1 — nacer PositionState durable tras un fill de apertura (ADR-033 §2).

V1.18 L2a: congela originDecisionPackage write-once si hay sesión/package.
No muta el ledger. Factory H2 intacta (TRIGGERED o override).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.origin_decision_package import (
    ORIGIN_DECISION_PACKAGE_KEY,
    extract_decision_package_from_session_payload,
    freeze_origin_decision_package,
)


class PositionStateStore(Protocol):
    async def get_by_open_transaction_id(
        self, open_transaction_id: str
    ) -> Any | None: ...

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> Any | None: ...

    async def insert(self, **kwargs: Any) -> Any: ...


class DecisionSessionByDecisionId(Protocol):
    async def get_decision_session_by_decision_id(
        self,
        decision_id: str,
        *,
        account_id: str | None = None,
        kind: str | None = "propose",
    ) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class PersistPositionFromFillInput:
    account_id: str
    trade_plan: dict[str, Any] | None
    fill_price: float
    fill_quantity: float
    filled_at: str | None
    open_transaction_id: str
    ledger_position_id: str | None
    override_reason: str | None = None


def ledger_position_id_from_trade(trade: Any, instrument_id: str) -> str | None:
    """Id de holding ledger si el fill lo dejó en el summary."""
    summary = getattr(trade, "summary", None)
    positions = getattr(summary, "positions", None) or []
    for pos in positions:
        if getattr(pos, "instrument_id", None) != instrument_id:
            continue
        pid = getattr(pos, "id", None)
        if isinstance(pid, str) and pid.strip():
            return pid
    return None


def open_transaction_id_from_trade(trade: Any) -> str | None:
    tx_id = getattr(trade, "transaction_id", None) or getattr(
        getattr(trade, "transaction", None), "id", None
    )
    if isinstance(tx_id, str) and tx_id.strip():
        return tx_id
    return None


class PersistPositionFromFill:
    """Inserta PositionState si ``from_fill`` nace; idempotente por transactionId."""

    def __init__(
        self,
        store: PositionStateStore,
        sessions: DecisionSessionByDecisionId | None = None,
    ) -> None:
        self._store = store
        self._sessions = sessions

    async def get_open(self, account_id: str, instrument_id: str) -> Any | None:
        acc = account_id.strip() if account_id else ""
        inst = instrument_id.strip() if instrument_id else ""
        if not acc or not inst:
            return None
        return await self._store.get_open_for_instrument(acc, inst)

    async def _resolve_origin_package(
        self,
        *,
        account_id: str,
        plan: dict[str, Any],
        instrument_id: str,
    ) -> dict[str, Any] | None:
        if self._sessions is None:
            return None
        decision_id = plan.get("decisionId") or plan.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id.strip():
            return None
        # Manual opens use synthetic decisionId — never invent a Package.
        if decision_id.startswith("manual-"):
            return None
        try:
            session = await self._sessions.get_decision_session_by_decision_id(
                decision_id.strip(),
                account_id=account_id,
                kind="propose",
            )
        except Exception:
            return None
        if session is None:
            return None
        payload = getattr(session, "payload", None)
        if isinstance(session, dict):
            payload = session.get("payload")
        package = extract_decision_package_from_session_payload(
            payload if isinstance(payload, dict) else None
        )
        return freeze_origin_decision_package(
            package=package,
            trade_plan=plan,
            decision_id=decision_id.strip(),
            instrument_id=instrument_id,
        )

    async def persist(self, inp: PersistPositionFromFillInput) -> Any | None:
        tx_id = inp.open_transaction_id.strip() if inp.open_transaction_id else ""
        if not tx_id or not inp.account_id.strip():
            return None
        existing = await self._store.get_by_open_transaction_id(tx_id)
        if existing is not None:
            return existing

        plan = inp.trade_plan if isinstance(inp.trade_plan, dict) else None
        instrument_id = ""
        if plan is not None:
            raw_id = plan.get("instrumentId") or plan.get("instrument_id")
            if isinstance(raw_id, str):
                instrument_id = raw_id.strip()
        if instrument_id:
            open_row = await self._store.get_open_for_instrument(
                inp.account_id, instrument_id
            )
            if open_row is not None:
                return open_row

        reason = (inp.override_reason or "").strip()
        override: dict[str, object] | None = {"reason": reason} if reason else None
        state = build_position_state_from_fill(
            plan,
            fill_price=inp.fill_price,
            fill_quantity=inp.fill_quantity,
            filled_at=inp.filled_at,
            position_id=inp.ledger_position_id,
            override=override,
        )
        if state is None:
            return None

        position_state = dict(state.to_dict())
        if plan is not None and instrument_id:
            origin = await self._resolve_origin_package(
                account_id=inp.account_id,
                plan=plan,
                instrument_id=instrument_id,
            )
            if origin is not None:
                position_state[ORIGIN_DECISION_PACKAGE_KEY] = origin

        return await self._store.insert(
            account_id=inp.account_id,
            instrument_id=state.instrument_id,
            ledger_position_id=inp.ledger_position_id,
            open_transaction_id=tx_id,
            trade_plan_id=state.trade_plan_id,
            status=state.status,
            trade_plan_snapshot=dict(plan or {}),
            position_state=position_state,
            birth_override_reason=reason or None,
            position_id=state.position_id,
        )
