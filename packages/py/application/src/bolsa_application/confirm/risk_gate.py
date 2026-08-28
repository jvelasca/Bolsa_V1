"""DEX-4 — RiskGate coordinator (risk_signature P2 / V1.26 geometría)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature


def risk_signature_reject_reason(
    *,
    trade_plan: dict[str, Any] | None,
    signed_qty: float,
    signed_price: float,
    override_reason: str | None,
    signed_stop: float | None = None,
) -> str | None:
    """P2: ``risk_signature`` si el tamaño firmado supera el plan sin override.

    V1.26: ``signed_stop`` entra en la firma; geometría inválida no es overrideable.
    """
    verdict = evaluate_risk_signature(
        trade_plan,
        signed_qty=signed_qty,
        signed_price=signed_price,
        signed_stop=signed_stop,
        override_reason=override_reason,
        require_triggered_plan=True,
    )
    if verdict.get("allowed") is True:
        return None
    return "risk_signature"


class RiskGateCoordinator:
    """Firma de riesgo vs TradePlan (≠ OpeningGate / risk_veto)."""

    def reject_reason(
        self,
        *,
        trade_plan: dict[str, Any] | None,
        signed_qty: float,
        signed_price: float,
        override_reason: str | None,
        signed_stop: float | None = None,
    ) -> str | None:
        return risk_signature_reject_reason(
            trade_plan=trade_plan,
            signed_qty=signed_qty,
            signed_price=signed_price,
            override_reason=override_reason,
            signed_stop=signed_stop,
        )
