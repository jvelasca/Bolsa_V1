"""P3 — advisory ExitPlan desde Position persistida (ADR-033 §4).

No ejecuta. No fusiona Lab EvaluatePositionExits. Thin exitRadar ≠ este objeto.
V1.29 — ExitPolicy del perfil activo parametriza suggestedQty/suggestedStop.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.exit_permission import check_exit_permission
from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.exit_policy import resolve_exit_policy
from bolsa_analytics.cognitive.position_state import position_state_from_dict


def advisory_exit_plan(
    position_state: dict[str, Any] | None,
    *,
    mark_price: float | None,
    template_id: str | None = None,
    exit_policy: Any | None = None,
) -> dict[str, Any] | None:
    """GET cartera: mark vs geometría. Sin ``manual`` — no inventa salida humana."""
    pos = position_state_from_dict(position_state)
    if pos is None:
        return None
    policy = exit_policy if exit_policy is not None else resolve_exit_policy(template_id)
    plan = build_exit_plan_from_position(
        pos, mark_price=mark_price, exit_policy=policy
    )
    if plan is None:
        return None
    tid = template_id if isinstance(template_id, str) and template_id.strip() else "moderate"
    if tid not in ("conservative", "moderate", "aggressive_swing"):
        tid = "moderate"
    return {
        "status": plan.status,
        "suggestedAction": plan.suggested_action,
        "primaryReason": plan.primary_reason,
        "suggestedQty": plan.suggested_qty,
        "suggestedStop": plan.suggested_stop,
        "policyTemplateId": tid,
        "trailWidth": policy.trail_width,
    }


def semi_exit_permission(
    position_state: dict[str, Any] | None,
    *,
    mark_price: float | None,
) -> Any:
    """Confirm SEMI: firma humana = ``manual``. Kill switch no niega desriesgo."""
    pos = position_state_from_dict(position_state)
    if pos is None:
        return check_exit_permission(None)
    plan = build_exit_plan_from_position(
        pos,
        mark_price=mark_price,
        manual=True,
    )
    return check_exit_permission(
        plan,
        auto_execute=False,
        position_closed=pos.status == "CLOSED",
    )


def semi_protect_permission(
    position_state: dict[str, Any] | None,
    *,
    suggested_stop: float,
) -> Any:
    """Confirm SEMI protect: ExitPlan ARMED/protect sin fill ledger."""
    pos = position_state_from_dict(position_state)
    if pos is None:
        return check_exit_permission(None)
    plan = build_exit_plan_from_position(
        pos,
        trail_hint=True,
        trail_stop=suggested_stop,
    )
    return check_exit_permission(
        plan,
        auto_execute=False,
        position_closed=pos.status == "CLOSED",
    )


def auto_exit_permission(
    exit_plan: Any,
    *,
    paper_d_execute: bool,
    data_stale: bool | None = False,
    market_closed: bool | None = False,
    portfolio_drift: bool | None = False,
    immediate_risk: bool = False,
    require_jit_context: bool = True,
    position_closed: bool = False,
    kill_switch: bool = False,
    at: str | None = None,
) -> Any:
    """V1.45 — permiso AUTO (JIT + PAPER_D). ≠ SEMI human."""
    return check_exit_permission(
        exit_plan,
        kill_switch=kill_switch,
        auto_execute=True,
        paper_d_execute=paper_d_execute,
        position_closed=position_closed,
        data_stale=data_stale,
        market_closed=market_closed,
        portfolio_drift=portfolio_drift,
        immediate_risk=immediate_risk,
        require_jit_context=require_jit_context,
        at=at,
    )
