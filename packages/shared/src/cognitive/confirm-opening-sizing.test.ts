/**
 * V1.25 — contrato sizing único (T-SIZE-01, T-SIZE-06).
 */

import { describe, expect, it } from "vitest";
import type { TradePlanV1 } from "./trade-plan.js";
import {
  applySupervisedOpeningQuantity,
  computeSignedPortfolioRiskPct,
  resolveSupervisedOpeningQuantity,
} from "./confirm-opening-sizing.js";

function triggeredPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-1",
    instrumentId: "MSFT",
    direction: "long",
    status: "TRIGGERED",
    quantity: 42,
    riskPct: 0.72,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    riskAmount: 210,
    initialRiskR: 1,
    ...overrides,
  };
}

describe("resolveSupervisedOpeningQuantity (T-SIZE-01, T-SIZE-06)", () => {
  it("T-SIZE-01: TRIGGERED → plan.quantity", () => {
    expect(
      resolveSupervisedOpeningQuantity({
        tradePlan: triggeredPlan({ quantity: 42 }),
        serverSuggestedQuantity: 99,
      }),
    ).toBe(42);
  });

  it("T-SIZE-06: sin TRIGGERED → null (no mandato % caja)", () => {
    expect(
      resolveSupervisedOpeningQuantity({
        tradePlan: triggeredPlan({ status: "WATCH", quantity: 42 }),
        serverSuggestedQuantity: 99,
      }),
    ).toBeNull();
    expect(
      resolveSupervisedOpeningQuantity({
        tradePlan: null,
        serverSuggestedQuantity: 99,
      }),
    ).toBeNull();
  });
});

describe("applySupervisedOpeningQuantity", () => {
  it("aligns suggestedQuantity with TRIGGERED plan", () => {
    const out = applySupervisedOpeningQuantity({
      tradePlan: triggeredPlan({ quantity: 35 }),
      suggestedQuantity: 99,
    });
    expect(out.suggestedQuantity).toBe(35);
  });
});

describe("computeSignedPortfolioRiskPct", () => {
  it("recalculates from signed loss and equity", () => {
    expect(
      computeSignedPortfolioRiskPct({
        signedLossAtStop: 315,
        equity: 43750,
        planRiskPct: 0.72,
      }),
    ).toBeCloseTo(0.72, 1);
  });
});
