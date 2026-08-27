import { describe, expect, it } from "vitest";
import {
  buildPortfolioRiskSnapshot,
  computePositionOpenRiskR,
  computeSectorExposurePct,
  portfolioRiskLimitR,
  sumPortfolioOpenRiskR,
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
    expect(snap.portfolioStressRiskR).toBeNull();
    expect(snap.portfolioRiskLimitR).toBe(5);
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
