import { describe, expect, it } from "vitest";
import {
  buildPortfolioRiskSnapshot,
  computePositionOpenRiskR,
  computeSectorExposurePct,
  portfolioRiskLimitR,
  sumPortfolioOpenRiskR,
  sumPortfolioStressRiskR,
  sumPortfolioUnrealizedR,
} from "./portfolio-risk-metrics.js";

describe("portfolio-risk-metrics", () => {
  it("separates PnL R from open risk R", () => {
    const positions = [
      {
        avgCost: 100,
        quantity: 10,
        operational: { currentStop: 95, unrealizedR: 2.0, direction: "long" },
        study: { stop: 95, riskAmount: 500 },
      },
      {
        avgCost: 50,
        quantity: 20,
        operational: { currentStop: 48, unrealizedR: -0.5, direction: "long" },
        study: { stop: 48, riskAmount: 200 },
      },
    ];
    expect(sumPortfolioUnrealizedR(positions)).toBe(1.5);
    expect(sumPortfolioOpenRiskR(positions)).toBe(0.3);
  });

  it("computePositionOpenRiskR returns null without riskAmount (no 1R stub)", () => {
    expect(
      computePositionOpenRiskR({
        avgCost: 100,
        quantity: 10,
        operational: { currentStop: 95, direction: "long" },
      }),
    ).toBeNull();
  });

  it("computePositionOpenRiskR returns 0 at breakeven stop", () => {
    expect(
      computePositionOpenRiskR({
        avgCost: 100,
        quantity: 10,
        operational: { currentStop: 100, direction: "long" },
        study: { riskAmount: 500 },
      }),
    ).toBe(0);
  });

  it("portfolioRiskLimitR from tolerance", () => {
    expect(portfolioRiskLimitR({ riskTolerance: "low" })).toBe(3);
    expect(portfolioRiskLimitR({ riskTolerance: "moderate" })).toBe(5);
    expect(portfolioRiskLimitR({ riskTolerance: "high" })).toBe(8);
  });

  it("buildPortfolioRiskSnapshot", () => {
    const snap = buildPortfolioRiskSnapshot({ positions: [] });
    expect(snap.portfolioStressRiskR).toBe(0);
    expect(snap.portfolioRiskLimitR).toBe(5);
  });

  describe("sumPortfolioStressRiskR (concurrent_stops_v0)", () => {
    it("empty portfolio → 0", () => {
      expect(sumPortfolioStressRiskR([])).toBe(0);
    });

    it("two complete positions → sum of openRiskR", () => {
      const positions = [
        {
          avgCost: 100,
          quantity: 10,
          operational: { currentStop: 95, direction: "long" },
          study: { stop: 95, riskAmount: 500 },
        },
        {
          avgCost: 50,
          quantity: 20,
          operational: { currentStop: 48, direction: "long" },
          study: { stop: 48, riskAmount: 200 },
        },
      ];
      // (5*10)/500 + (2*20)/200 = 0.1 + 0.2 = 0.3
      expect(sumPortfolioStressRiskR(positions)).toBe(0.3);
      expect(sumPortfolioOpenRiskR(positions)).toBe(0.3);
    });

    it("one missing openRiskR → null (no partial cota)", () => {
      const positions = [
        {
          avgCost: 100,
          quantity: 10,
          operational: { currentStop: 95, direction: "long" },
          study: { stop: 95, riskAmount: 500 },
        },
        {
          avgCost: 50,
          quantity: 20,
          operational: { currentStop: 48, direction: "long" },
          // sin riskAmount → openRiskR null
        },
      ];
      expect(computePositionOpenRiskR(positions[1]!)).toBeNull();
      expect(sumPortfolioStressRiskR(positions)).toBeNull();
      // Open risk sigue sumando parciales; stress exige cobertura completa.
      expect(sumPortfolioOpenRiskR(positions)).toBe(0.1);
    });
  });

  it("computeSectorExposurePct weights market value by equity", () => {
    const pct = computeSectorExposurePct(
      [
        { marketValue: 40_000, sector: "Technology" },
        { marketValue: 10_000, sector: "Healthcare" },
        { marketValue: 5_000, sector: "Technology" },
      ],
      100_000,
    );
    expect(pct.Technology).toBe(45);
    expect(pct.Healthcare).toBe(10);
  });
});
