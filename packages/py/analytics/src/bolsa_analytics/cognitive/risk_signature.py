"""P2 / V1.26 — firma de riesgo al confirmar (ADR-033 §6).

TradePlan TRIGGERED sizea; % caja no es autoridad.
Geometría: direction + entry + stop (fail-closed; no abs).
No es ``check_opening``. No es OrderIntent.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.operational_invariants import adverse_exposure
from bolsa_analytics.cognitive.operational_levels import validate_operational_levels

QTY_EPS = 1e-9
MONEY_EPS = 0.01


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    n = float(value)
    if n != n or abs(n) == float("inf"):
        return None
    return n


def _round4(n: float) -> float:
    return round(n * 10000) / 10000


def _is_audited_reason(reason: object | None) -> bool:
    return isinstance(reason, str) and bool(reason.strip())


def _plan_dict(trade_plan: object | None) -> dict[str, Any] | None:
    return trade_plan if isinstance(trade_plan, dict) else None


def _empty_plan(*, require_triggered_plan: bool) -> dict[str, Any]:
    return {
        "mode": "no_plan",
        "suggestedQty": None,
        "maxQty": None,
        "stop": None,
        "plannedRiskAmount": None,
        "initialRiskR": None,
        "signedLossAtStop": None,
        "signedR": None,
        "overrideRequired": False,
        "allowed": not require_triggered_plan,
        "excess": None,
        "blockReason": "no_tradeplan" if require_triggered_plan else None,
    }


def _denied_plan(
    *,
    plan_qty: float,
    stop: float | None,
    planned_risk: float | None,
    initial_risk_r: float | None,
    block_reason: str,
    signed_loss: float | None = None,
    signed_r: float | None = None,
) -> dict[str, Any]:
    return {
        "mode": "plan",
        "suggestedQty": plan_qty,
        "maxQty": plan_qty,
        "stop": stop,
        "plannedRiskAmount": planned_risk,
        "initialRiskR": initial_risk_r,
        "signedLossAtStop": signed_loss,
        "signedR": signed_r,
        "overrideRequired": False,
        "allowed": False,
        "excess": None,
        "blockReason": block_reason,
    }


def evaluate_risk_signature(
    trade_plan: object | None,
    *,
    signed_qty: float,
    signed_price: float,
    signed_stop: float | None = None,
    override_reason: str | None = None,
    require_triggered_plan: bool = False,
) -> dict[str, Any]:
    """Evalúa qty/precio/stop firmados contra el TradePlan.

    Sin TRIGGERED + quantity>0 → ``no_plan``.
    Con ``require_triggered_plan=True`` (SEMI apertura): ``no_plan`` → DENY
    ``no_tradeplan`` (manual HTTP no usa este gate).
    ``signed_stop`` omitido (None) → stop del plan.
    ``signed_stop`` presente e inválido (≤0 / no finito) → DENY ``stop_invalid``.
    """
    plan = _plan_dict(trade_plan)
    qty = _finite(signed_qty)
    price = _finite(signed_price)
    override = _is_audited_reason(override_reason)

    status = plan.get("status") if plan else None
    plan_qty = _finite(plan.get("quantity") if plan else None)
    if status != "TRIGGERED" or plan_qty is None or plan_qty <= 0:
        return _empty_plan(require_triggered_plan=require_triggered_plan)

    planned_risk = _finite(plan.get("riskAmount") if plan else None)
    initial_risk_r = _finite(plan.get("initialRiskR") if plan else None)
    plan_stop = _finite(plan.get("structuralStop") if plan else None)

    if signed_stop is not None:
        parsed_stop = _finite(signed_stop)
        if parsed_stop is None or parsed_stop <= 0:
            return _denied_plan(
                plan_qty=plan_qty,
                stop=None,
                planned_risk=planned_risk,
                initial_risk_r=initial_risk_r,
                block_reason="stop_invalid",
            )
        stop = parsed_stop
    else:
        stop = plan_stop

    if stop is None or stop <= 0:
        return _denied_plan(
            plan_qty=plan_qty,
            stop=None,
            planned_risk=planned_risk,
            initial_risk_r=initial_risk_r,
            block_reason="stop_invalid",
        )

    if price is not None and price > 0:
        levels = validate_operational_levels(
            direction=plan.get("direction") if plan else None,
            entry=price,
            stop=stop,
            target1=plan.get("target1") if plan else None,
            target2=plan.get("target2") if plan else None,
        )
        if levels.get("ok") is not True:
            reason = levels.get("reason")
            block = (
                reason
                if reason
                in {"stop_wrong_side", "targets_invalid", "risk_non_positive"}
                else "stop_wrong_side"
            )
            return _denied_plan(
                plan_qty=plan_qty,
                stop=stop,
                planned_risk=planned_risk,
                initial_risk_r=initial_risk_r,
                block_reason=str(block),
            )

    signed_loss: float | None = None
    direction = plan.get("direction") if plan else None
    if (
        qty is not None
        and qty > 0
        and price is not None
        and price > 0
        and direction in ("long", "short")
    ):
        signed_loss = _round4(qty * adverse_exposure(direction, price, stop))

    signed_r: float | None = None
    if signed_loss is not None and planned_risk is not None and planned_risk > MONEY_EPS:
        signed_r = _round4(signed_loss / planned_risk)

    excess: str | None = None
    if qty is not None and qty > plan_qty + QTY_EPS:
        excess = "qty_above_plan"
    elif (
        signed_loss is not None
        and planned_risk is not None
        and planned_risk > 0
        and signed_loss > planned_risk + MONEY_EPS
    ):
        excess = "loss_above_plan"

    override_required = excess is not None
    allowed = (not override_required) or override

    return {
        "mode": "plan",
        "suggestedQty": plan_qty,
        "maxQty": plan_qty,
        "stop": stop,
        "plannedRiskAmount": planned_risk,
        "initialRiskR": initial_risk_r,
        "signedLossAtStop": signed_loss,
        "signedR": signed_r,
        "overrideRequired": override_required,
        "allowed": allowed,
        "excess": excess,
        "blockReason": "override_missing" if not allowed else None,
    }


def apply_signed_levels_to_trade_plan(
    trade_plan: dict[str, Any] | None,
    *,
    signed_qty: float | None = None,
    signed_price: float | None = None,
    signed_stop: float | None = None,
) -> dict[str, Any] | None:
    """Congela qty/entrada/stop firmados sobre el snapshot (nacimiento Position)."""
    if not isinstance(trade_plan, dict):
        return trade_plan
    out = dict(trade_plan)
    qty = _finite(signed_qty)
    if qty is not None and qty > 0:
        out["quantity"] = qty
    price = _finite(signed_price)
    if price is not None and price > 0:
        out["entry"] = price
    stop = _finite(signed_stop)
    if stop is not None and stop > 0:
        out["structuralStop"] = stop
    return out
