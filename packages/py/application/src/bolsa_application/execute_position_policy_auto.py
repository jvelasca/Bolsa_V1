"""V1.45 — ExecutePositionPolicyAuto: Policy → JIT Permission → protect | sell.

Canónico mesa/paper. ≠ Lab EvaluatePositionExits. ≠ Confirm SEMI.
PAPER_D_EXECUTE default off (gate vía check_exit_permission + caller).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from bolsa_analytics.cognitive.exit_permission import ExitPermission, check_exit_permission
from bolsa_analytics.cognitive.exit_plan import ExitPlan
from bolsa_analytics.cognitive.operating_policy import OperatingPolicy
from bolsa_analytics.cognitive.position_policy_decision import (
    PositionPolicyDecision,
    decide_position_policy,
)
from bolsa_analytics.cognitive.position_revision import revision_origin_from_exit_reason
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    position_state_from_dict,
)
from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExit,
    PersistPositionFromExitInput,
)
from bolsa_application.persist_position_from_protect import (
    PersistPositionFromProtect,
    PersistPositionFromProtectInput,
)

ExecutePositionPolicyAutoStatus = Literal[
    "held",
    "denied",
    "protected",
    "reduced",
    "exited",
    "sell_skipped",
    "error",
]


@dataclass(frozen=True, slots=True)
class PaperPositionSellResult:
    status: Literal["trade_executed", "skipped", "blocked"]
    reason: str | None = None
    fill_quantity: float | None = None
    fill_price: float | None = None
    transaction_id: str | None = None


class PaperPositionSellPort(Protocol):
    """Puerto de sell PAPER (Router u otro adapter)."""

    async def sell(
        self,
        *,
        account_id: str,
        instrument_id: str,
        quantity: float,
        price: float,
        full_exit: bool,
        idempotency_key: str | None = None,
        event_kind: str | None = None,
        position_id: str | None = None,
        as_of: str | None = None,
    ) -> PaperPositionSellResult: ...


@dataclass(frozen=True, slots=True)
class ExecutePositionPolicyAutoInput:
    account_id: str
    instrument_id: str
    exit_plan: ExitPlan
    operating_policy: OperatingPolicy
    mark_price: float
    paper_d_execute: bool
    position: PositionState | dict[str, Any] | None = None
    data_stale: bool | None = False
    market_closed: bool | None = False
    portfolio_drift: bool | None = False
    immediate_risk: bool = False
    require_jit_context: bool = True
    kill_switch: bool = False
    session: Literal["open", "closed"] | None = None
    stale: bool | None = None
    stop_touched: bool | None = None
    as_of: str | None = None
    existing_intent_keys: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class ExecutePositionPolicyAutoResult:
    status: ExecutePositionPolicyAutoStatus
    decision: PositionPolicyDecision | None
    permission: ExitPermission | None
    reason: str | None = None
    position_row: Any | None = None
    sell: PaperPositionSellResult | None = None
    event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "decision": self.decision.to_dict() if self.decision else None,
            "permission": self.permission.to_dict() if self.permission else None,
            "reason": self.reason,
            "sell": (
                {
                    "status": self.sell.status,
                    "reason": self.sell.reason,
                    "fillQuantity": self.sell.fill_quantity,
                    "fillPrice": self.sell.fill_price,
                    "transactionId": self.sell.transaction_id,
                }
                if self.sell
                else None
            ),
        }


def _resolve_position(
    raw: PositionState | dict[str, Any] | None,
) -> PositionState | None:
    if isinstance(raw, PositionState):
        return raw
    if isinstance(raw, dict):
        return position_state_from_dict(raw)
    return None


class ExecutePositionPolicyAuto:
    """Orquestador V1.45 — no sustituye Confirm; no enciende env."""

    def __init__(
        self,
        *,
        protect: PersistPositionFromProtect,
        exit_persist: PersistPositionFromExit,
        sell: PaperPositionSellPort,
    ) -> None:
        self._protect = protect
        self._exit_persist = exit_persist
        self._sell = sell

    async def execute(
        self, inp: ExecutePositionPolicyAutoInput
    ) -> ExecutePositionPolicyAutoResult:
        position = _resolve_position(inp.position)
        if position is None:
            # Try open row from protect store.
            row = await self._protect.get_open(inp.account_id, inp.instrument_id)
            if row is not None:
                from bolsa_application.persist_position_from_exit import row_position_state

                position = position_state_from_dict(row_position_state(row))

        session = inp.session
        if session is None and inp.market_closed is True:
            session = "closed"
        if session is None and inp.market_closed is False:
            session = "open"
        stale_flag = inp.stale if inp.stale is not None else inp.data_stale

        decision = decide_position_policy(
            position,
            inp.exit_plan,
            inp.operating_policy,
            session=session,
            stale=stale_flag is True,
            stop_touched=inp.stop_touched is True,
            as_of=inp.as_of,
        )

        if decision.verdict == "HOLD":
            return ExecutePositionPolicyAutoResult(
                status="held",
                decision=decision,
                permission=None,
                reason=decision.defer_reason,
            )

        permission = check_exit_permission(
            inp.exit_plan,
            kill_switch=inp.kill_switch,
            auto_execute=True,
            paper_d_execute=inp.paper_d_execute,
            position_closed=position.status == "CLOSED" if position else False,
            data_stale=inp.data_stale,
            market_closed=inp.market_closed,
            portfolio_drift=inp.portfolio_drift,
            immediate_risk=inp.immediate_risk
            or (inp.stop_touched is True)
            or (
                decision.reason_code
                in ("STRUCTURAL_STOP", "THESIS_INVALIDATION", "PORTFOLIO_RISK")
            ),
            require_jit_context=inp.require_jit_context,
            at=inp.as_of,
        )
        if not permission.allowed:
            return ExecutePositionPolicyAutoResult(
                status="denied",
                decision=decision,
                permission=permission,
                reason=",".join(permission.reasons) or "denied",
            )

        if decision.verdict in ("PROTECT", "TRAIL"):
            stop = decision.new_stop
            if stop is None or stop <= 0:
                return ExecutePositionPolicyAutoResult(
                    status="error",
                    decision=decision,
                    permission=permission,
                    reason="missing_new_stop",
                )
            origin = revision_origin_from_exit_reason(decision.reason_code)
            row = await self._protect.persist(
                PersistPositionFromProtectInput(
                    account_id=inp.account_id,
                    instrument_id=inp.instrument_id,
                    suggested_stop=float(stop),
                    origin=origin,
                    reason=(
                        "trail_auto"
                        if origin == "trail"
                        else (decision.reason_code or "protect_auto")
                    ),
                    applied_at=inp.as_of,
                    decision_id=(position.decision_id or position.trade_plan_id)
                    if position
                    else None,
                    policy_id=inp.operating_policy.template_id,
                )
            )
            return ExecutePositionPolicyAutoResult(
                status="protected",
                decision=decision,
                permission=permission,
                position_row=row,
            )

        # REDUCE | EXIT — solo EXIT puede asumir remaining; REDUCE sin qty = error.
        full_exit = decision.verdict == "EXIT"
        qty = decision.quantity
        if qty is None or qty <= 0:
            if not full_exit:
                return ExecutePositionPolicyAutoResult(
                    status="error",
                    decision=decision,
                    permission=permission,
                    reason="missing_reduce_quantity",
                )
            if position is None:
                return ExecutePositionPolicyAutoResult(
                    status="error",
                    decision=decision,
                    permission=permission,
                    reason="missing_quantity",
                )
            qty = float(position.remaining_quantity)
        price = float(inp.mark_price)
        if price <= 0:
            return ExecutePositionPolicyAutoResult(
                status="error",
                decision=decision,
                permission=permission,
                reason="invalid_mark_price",
            )

        event_kind = "UNKNOWN"
        if decision.event is not None:
            event_kind = str(decision.event.kind)
        elif decision.reason_code:
            event_kind = str(decision.reason_code)
        action = "exit" if full_exit else "reduce"
        pos_id = position.position_id if position is not None else inp.instrument_id
        claimed = await self._protect.claim_sell_event(
            account_id=inp.account_id,
            instrument_id=inp.instrument_id,
            event_type=event_kind,
            action=action,
            as_of=inp.as_of,
            quantity=float(qty),
        )
        if claimed is None:
            return ExecutePositionPolicyAutoResult(
                status="error",
                decision=decision,
                permission=permission,
                reason="event_claim_failed",
            )
        idem_key = claimed.event_id
        event_id = claimed.event_id
        keys = inp.existing_intent_keys or frozenset()
        if event_id and event_id in keys:
            return ExecutePositionPolicyAutoResult(
                status="sell_skipped",
                decision=decision,
                permission=permission,
                reason="intent_unresolved",
                event_id=event_id,
            )

        sell = await self._sell.sell(
            account_id=inp.account_id,
            instrument_id=inp.instrument_id,
            quantity=float(qty),
            price=price,
            full_exit=full_exit,
            idempotency_key=idem_key,
            event_kind=event_kind,
            position_id=pos_id,
            as_of=inp.as_of,
        )
        if sell.status != "trade_executed":
            fail_which = (
                "t1"
                if decision.reason_code == "TARGET_1"
                else "t2"
                if decision.reason_code == "TARGET_2"
                else None
            )
            reason_raw = (sell.reason or "").lower()
            status_raw = (sell.status or "").lower()
            hard_reject = status_raw == "blocked" or "rejected" in reason_raw
            if fail_which is not None and hard_reject:
                await self._protect.patch_target_leg(
                    account_id=inp.account_id,
                    instrument_id=inp.instrument_id,
                    which=fail_which,
                    status="failed",
                    at=inp.as_of,
                    event_id=event_id,
                )
            return ExecutePositionPolicyAutoResult(
                status="sell_skipped",
                decision=decision,
                permission=permission,
                reason=sell.reason or sell.status,
                sell=sell,
                event_id=event_id,
            )

        fill_qty = float(sell.fill_quantity or qty)
        fill_price = float(sell.fill_price or price)
        tx = (sell.transaction_id or "").strip() or f"auto-{inp.instrument_id}-{decision.as_of}"
        mark_t1 = decision.reason_code == "TARGET_1"
        mark_t2 = decision.reason_code == "TARGET_2"
        row = await self._exit_persist.persist(
            PersistPositionFromExitInput(
                account_id=inp.account_id,
                instrument_id=inp.instrument_id,
                fill_quantity=fill_qty,
                fill_price=fill_price,
                exit_transaction_id=tx,
                filled_at=inp.as_of,
                mark_target1_achieved=mark_t1,
                mark_target2_achieved=mark_t2,
                decision_id=(position.decision_id or position.trade_plan_id)
                if position
                else None,
                policy_id=inp.operating_policy.template_id,
                event_id=event_id,
            )
        )
        if row is None and (mark_t1 or mark_t2):
            await self._protect.patch_target_leg(
                account_id=inp.account_id,
                instrument_id=inp.instrument_id,
                which="t1" if mark_t1 else "t2",
                status="failed",
                at=inp.as_of,
                event_id=event_id,
                fill_id=tx,
            )
        return ExecutePositionPolicyAutoResult(
            status="exited" if full_exit or (row and getattr(row, "status", None) == "CLOSED")
            or (
                isinstance(row, dict) and row.get("status") == "CLOSED"
            )
            else "reduced",
            decision=decision,
            permission=permission,
            position_row=row,
            sell=sell,
            event_id=event_id,
        )
