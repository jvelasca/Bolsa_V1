/**
 * V1.25 — T-SIZE-07: Confirm y Mesa usan buildPortfolioScenario.
 */

import { describe, expect, it } from "vitest";
import type { TradePlanV1 } from "./trade-plan.js";
import {
  buildConfirmPortfolioScenario,
  buildConfirmScenarioCandidate,
} from "./confirm-portfolio-scenario.js";
import { buildPortfolioScenario } from "./portfolio-scenario.js";

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
    target1: 115.7,
    riskAmount: 315,
    initialRiskR: 1,
    positionValue: 5125,
  };
}

describe("buildConfirmPortfolioScenario (T-SIZE-07)", () => {
  it("matches buildPortfolioScenario for equivalent candidate input", () => {
    const signedQty = 50;
    const signedPrice = 102.5;
    const signedStop = 96.2;
    const equity = 43750;
    const cash = 31500;
    const plan = triggeredPlan();

    const candidate = buildConfirmScenarioCandidate({
      symbol: "AAPL",
      instrumentId: "AAPL",
      signedQty,
      signedPrice,
      signedStop,
      tradePlan: plan,
    });

    const mesaScenario = buildPortfolioScenario({
      candidate,
      positions: [],
      equity,
      cash,
      candidateSector: "Technology",
      maxSectorExposurePct: 40,
      portfolioRiskLimitR: 6,
    });

    const confirmScenario = buildConfirmPortfolioScenario({
      symbol: "AAPL",
      instrumentId: "AAPL",
      signedQty,
      signedPrice,
      signedStop,
      tradePlan: plan,
      positions: [],
      equity,
      cash,
      candidateSector: "Technology",
      maxSectorExposurePct: 40,
      portfolioRiskLimitR: 6,
    });

    expect(confirmScenario.after.openRiskR).toBe(mesaScenario.after.openRiskR);
    expect(confirmScenario.after.cashPct).toBe(mesaScenario.after.cashPct);
    expect(confirmScenario.verdict).toBe(mesaScenario.verdict);
  });
});
