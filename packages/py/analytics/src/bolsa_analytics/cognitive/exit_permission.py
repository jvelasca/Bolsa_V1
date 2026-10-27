"""ExitPermission — veto de salida / mutación de stop (ADR-032).

Simétrico a check_opening (apertura), distinto de él.
≠ ExitPlan ≠ ExecutionPlan ≠ auto-exit ≠ ExecuteTrade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from bolsa_analytics.cognitive.execution_plan import ExecutionPlan
from bolsa_analytics.cognitive.exit_plan import ExitPlan

ExitPermissionVerdict = Literal["ALLOW", "DENY"]
ExitPermissionReason = Literal[
    "not_actionable",
    "position_closed",
    "kill_switch",
    "broker_not_allowed",
    "paper_auto_env_blocked",
    "execution_blocked",
    "missing_exit_plan",
    "data_stale",
    "market_closed",
    "portfolio_drift",
]
ExitPermissionAction = Literal["full_exit", "reduce", "protect", "none"]

EXIT_PERMISSION_KEY = "exitPermission"


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class ExitPermission:
    """Veredicto de permiso de salida (F5)."""

    verdict: ExitPermissionVerdict
    allowed: bool
    reasons: tuple[ExitPermissionReason, ...]
    exit_plan_id: str | None
    position_id: str | None
    action: ExitPermissionAction
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "exitPlanId": self.exit_plan_id,
            "positionId": self.position_id,
            "action": self.action,
            "createdAt": self.created_at,
        }


#: Qué sugerencia del plan convierte en ACCIÓN ejecutable según su estado.
#:
#: ``HINT`` admite ``full_exit``/``reduce`` porque un plan **vencido** (``TIME_STOP``) es una
#: instrucción de salida real y no un aviso: el propio plan ya declara ``suggested_action =
#: full_exit``. Antes se exigía ``TRIGGERED`` y la misma condición se leía «no accionable» en F5
#: mientras el AUTO vendía la posición completa (S-1): el status dice *cuán urgente* es la
#: salida, no *si* hay salida.
#:
#: La tabla es deliberadamente estrecha: ``protect`` sigue exigiendo ``ARMED`` —proteger sin
#: stop de trailing sería una acción sin argumento— y ``hold`` no es accionable en ningún estado.
_ACTIONABLE_BY_STATUS: dict[str, frozenset[str]] = {
    "TRIGGERED": frozenset({"full_exit", "reduce"}),
    "ARMED": frozenset({"protect"}),
    "HINT": frozenset({"full_exit", "reduce"}),
}


def _resolve_action(exit_plan: ExitPlan | None) -> ExitPermissionAction:
    if exit_plan is None:
        return "none"
    allowed = _ACTIONABLE_BY_STATUS.get(exit_plan.status)
    if allowed is None or exit_plan.suggested_action not in allowed:
        return "none"
    return cast("ExitPermissionAction", exit_plan.suggested_action)


def _deny(
    reasons: list[ExitPermissionReason],
    exit_plan: ExitPlan | None,
    at: str | None,
) -> ExitPermission:
    return ExitPermission(
        verdict="DENY",
        allowed=False,
        reasons=tuple(reasons),
        exit_plan_id=exit_plan.exit_plan_id if exit_plan else None,
        position_id=exit_plan.position_id if exit_plan else None,
        action=_resolve_action(exit_plan),
        created_at=_now_iso(at),
    )


def _is_protective(exit_plan: ExitPlan, immediate_risk: bool) -> bool:
    reason = exit_plan.primary_reason
    if reason in ("STRUCTURAL_STOP", "THESIS_INVALIDATION", "PORTFOLIO_RISK"):
        return True
    return immediate_risk


def _jit_deny_reason(
    exit_plan: ExitPlan,
    *,
    auto_execute: bool,
    data_stale: bool | None,
    market_closed: bool | None,
    portfolio_drift: bool | None,
    immediate_risk: bool,
    require_jit_context: bool,
) -> ExitPermissionReason | None:
    if not auto_execute:
        return None
    protective = _is_protective(exit_plan, immediate_risk)
    if data_stale is True and not protective:
        return "data_stale"
    if require_jit_context and data_stale is None and not protective:
        return "data_stale"
    if market_closed is True and not protective:
        return "market_closed"
    if require_jit_context and market_closed is None and not protective:
        return "market_closed"
    if portfolio_drift is True and not protective:
        return "portfolio_drift"
    if require_jit_context and portfolio_drift is None and not protective:
        return "portfolio_drift"
    return None


def check_exit_permission(
    exit_plan: ExitPlan | None,
    *,
    kill_switch: bool = False,
    broker_requested: bool = False,
    auto_execute: bool = False,
    paper_d_execute: bool = False,
    position_closed: bool = False,
    execution_plan: ExecutionPlan | None = None,
    at: str | None = None,
    data_stale: bool | None = None,
    market_closed: bool | None = None,
    portfolio_drift: bool | None = None,
    immediate_risk: bool = False,
    require_jit_context: bool = False,
) -> ExitPermission:
    """Gate F5: ¿podemos salir / mutar stop ahora? No ejecuta."""
    if exit_plan is None:
        return _deny(["missing_exit_plan"], None, at)

    if position_closed:
        return _deny(["position_closed"], exit_plan, at)

    action = _resolve_action(exit_plan)
    human_derisk = (not auto_execute) and action in (
        "full_exit",
        "reduce",
        "protect",
    )
    if kill_switch and not human_derisk:
        return _deny(["kill_switch"], exit_plan, at)

    if broker_requested:
        return _deny(["broker_not_allowed"], exit_plan, at)
    if execution_plan is not None and (
        execution_plan.venue == "BROKER"
        or execution_plan.blocked_reason == "broker_not_allowed"
    ):
        return _deny(["broker_not_allowed"], exit_plan, at)

    if auto_execute and not paper_d_execute:
        return _deny(["paper_auto_env_blocked"], exit_plan, at)

    jit = _jit_deny_reason(
        exit_plan,
        auto_execute=auto_execute,
        data_stale=data_stale,
        market_closed=market_closed,
        portfolio_drift=portfolio_drift,
        immediate_risk=immediate_risk,
        require_jit_context=require_jit_context,
    )
    if jit is not None:
        return _deny([jit], exit_plan, at)

    if execution_plan is not None and execution_plan.status == "BLOCKED":
        return _deny(["execution_blocked"], exit_plan, at)

    if action == "none":
        return _deny(["not_actionable"], exit_plan, at)

    return ExitPermission(
        verdict="ALLOW",
        allowed=True,
        reasons=(),
        exit_plan_id=exit_plan.exit_plan_id,
        position_id=exit_plan.position_id,
        action=action,
        created_at=_now_iso(at),
    )
