/**
 * V1.32 — firma de tamaño en salida SEMI (simétrico a risk_signature de apertura).
 * Qty firmada ≤ plannedQty del ExitPlan / enqueue; exceso exige override.
 * ≠ check_opening · ≠ TradePlan · ≠ ExitPermission.
 */

export const EXIT_QTY_EPS = 1e-9;

export type ExitRiskSignatureV1 = {
  mode: "exit" | "no_plan";
  plannedQty: number | null;
  maxQty: number | null;
  overrideRequired: boolean;
  allowed: boolean;
  excess: number | null;
  blockReason: "qty_exceeds_plan" | "qty_invalid" | null;
};

function finite(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function auditedReason(reason: unknown): boolean {
  return typeof reason === "string" && reason.trim().length > 0;
}

export function evaluateExitRiskSignature(input: {
  plannedQty: number | null | undefined;
  signedQty: number;
  overrideReason?: string | null;
}): ExitRiskSignatureV1 {
  const signed = finite(input.signedQty);
  if (signed == null || signed <= 0) {
    return {
      mode: "exit",
      plannedQty: finite(input.plannedQty),
      maxQty: finite(input.plannedQty),
      overrideRequired: false,
      allowed: false,
      excess: null,
      blockReason: "qty_invalid",
    };
  }

  const planned = finite(input.plannedQty);
  if (planned == null || planned <= 0) {
    // Sin plan de qty (legado): no bloquea por firma de tamaño.
    return {
      mode: "no_plan",
      plannedQty: null,
      maxQty: null,
      overrideRequired: false,
      allowed: true,
      excess: null,
      blockReason: null,
    };
  }

  const excess = signed - planned;
  const exceeds = excess > EXIT_QTY_EPS;
  const override = auditedReason(input.overrideReason);

  return {
    mode: "exit",
    plannedQty: planned,
    maxQty: planned,
    overrideRequired: exceeds,
    allowed: !exceeds || override,
    excess: exceeds ? excess : null,
    blockReason: exceeds && !override ? "qty_exceeds_plan" : null,
  };
}
