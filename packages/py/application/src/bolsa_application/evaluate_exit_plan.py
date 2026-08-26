"""P3 — advisory ExitPlan desde Position persistida (ADR-033 §4).

No ejecuta. No fusiona Lab EvaluatePositionExits. Thin exitRadar ≠ este objeto.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.exit_permission import check_exit_permission
from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.position_state import position_state_from_dict


def advisory_exit_plan(
    position_state: dict[str, Any] | None,
    *,
    mark_price: float | None,
) -> dict[str, Any] | None:
    """GET cartera: mark vs geometría. Sin ``manual`` — no inventa salida humana."""
    pos = position_state_from_dict(position_state)
    if pos is None:
        return None
    plan = build_exit_plan_from_position(pos, mark_price=mark_price)
    if plan is None:
        return None
    return {
        "status": plan.status,
        "suggestedAction": plan.suggested_action,
        "primaryReason": plan.primary_reason,
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
