"""P2 — firma de riesgo al confirmar (ADR-033 §6).

TradePlan TRIGGERED sizea; % caja no es autoridad.
No es ``check_opening``. No es OrderIntent.
"""

from __future__ import annotations

from typing import Any

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


def evaluate_risk_signature(
    trade_plan: object | None,
    *,
    signed_qty: float,
    signed_price: float,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """Evalúa qty/precio firmados contra el TradePlan.

    Sin TRIGGERED + quantity>0 → ``no_plan`` (no inventa stop/R; allowed).
    """
    plan = _plan_dict(trade_plan)
    qty = _finite(signed_qty)
    price = _finite(signed_price)
    override = _is_audited_reason(override_reason)

    status = plan.get("status") if plan else None
    plan_qty = _finite(plan.get("quantity") if plan else None)
    if status != "TRIGGERED" or plan_qty is None or plan_qty <= 0:
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
            "allowed": True,
            "excess": None,
            "blockReason": None,
        }

    stop = _finite(plan.get("structuralStop") if plan else None)
    planned_risk = _finite(plan.get("riskAmount") if plan else None)
    initial_risk_r = _finite(plan.get("initialRiskR") if plan else None)

    signed_loss: float | None = None
    if qty is not None and qty > 0 and price is not None and price > 0 and stop is not None:
        signed_loss = _round4(qty * abs(price - stop))

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
