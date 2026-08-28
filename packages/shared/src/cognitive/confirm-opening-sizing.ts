/**
 * V1.25 — sizing único en openings supervisados (Confirm).
 * TradePlan TRIGGERED = única autoridad; % caja no es mandato.
 */

import type { TradePlanV1 } from "./trade-plan.js";

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

/** Cantidad canónica para apertura supervisada (null = sin prefill de mandato). */
export function resolveSupervisedOpeningQuantity(input: {
  tradePlan?: TradePlanV1 | null;
  serverSuggestedQuantity?: number | null;
}): number | null {
  const plan = input.tradePlan;
  if (plan?.status === "TRIGGERED" && finitePositive(plan.quantity)) {
    return plan.quantity;
  }
  return null;
}

/** Qty mínima para API propose cuando aún no hay plan TRIGGERED. */
export function supervisedProposeQuantityPlaceholder(
  tradePlan?: TradePlanV1 | null,
): number {
  const resolved = resolveSupervisedOpeningQuantity({
    tradePlan,
    serverSuggestedQuantity: null,
  });
  return resolved ?? 1;
}

/** Tras propose: alinear suggestedQuantity con plan TRIGGERED. */
export function applySupervisedOpeningQuantity<
  T extends {
    tradePlan?: TradePlanV1 | null;
    suggestedQuantity?: number | null;
  },
>(payload: T): T {
  const qty = resolveSupervisedOpeningQuantity({
    tradePlan: payload.tradePlan,
    serverSuggestedQuantity: payload.suggestedQuantity,
  });
  if (qty != null) {
    return { ...payload, suggestedQuantity: qty };
  }
  return payload;
}

/** Riesgo % cartera firmado vs equity (recalculado al editar qty/stop). */
export function computeSignedPortfolioRiskPct(input: {
  signedLossAtStop: number | null;
  equity: number | null;
  planRiskPct?: number | null;
}): number | null {
  const { signedLossAtStop, equity, planRiskPct } = input;
  if (signedLossAtStop != null && equity != null && equity > 0) {
    return Math.round((signedLossAtStop / equity) * 10000) / 100;
  }
  if (typeof planRiskPct === "number" && Number.isFinite(planRiskPct)) {
    return planRiskPct;
  }
  return null;
}
