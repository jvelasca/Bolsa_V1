/**
 * V1.25 — finalizeSupervisedProposePayload (propose paths).
 */

import { describe, expect, it } from "vitest";
import type { TradePlanV1 } from "@bolsa/shared";
import { finalizeSupervisedProposePayload } from "./supervised-opening-sizing";

function triggeredPlan(): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "AAPL",
    direction: "long",
    status: "TRIGGERED",
    quantity: 50,
    riskPct: 0.72,
    whyNot: [],
    executionAllowed: true,
    entry: 102.5,
    structuralStop: 96.2,
    riskAmount: 315,
    initialRiskR: 1,
  };
}

describe("finalizeSupervisedProposePayload", () => {
  it("replaces cash-sized qty with plan qty when TRIGGERED", () => {
    const out = finalizeSupervisedProposePayload({
      instrumentId: "AAPL",
      recommendationId: "r1",
      action: "recommend_long",
      suggestedQuantity: 200,
      tradePlan: triggeredPlan(),
    });
    expect(out.suggestedQuantity).toBe(50);
  });
});
