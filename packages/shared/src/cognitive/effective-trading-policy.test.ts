import { describe, expect, it } from "vitest";
import {
  effectiveMaxSectorExposurePct,
  formatPortfolioFitPreview,
  resolveEffectiveTradingPolicy,
} from "./effective-trading-policy.js";
import { MODERATE_TRADING_POLICY } from "./trading-policy-templates.js";

describe("resolveEffectiveTradingPolicy", () => {
  it("falls back to moderate when template missing", () => {
    const policy = resolveEffectiveTradingPolicy(null);
    expect(policy.templateId).toBe("moderate");
    expect(policy.exposure.maxSectorExposurePct).toBe(30);
  });

  it("maps conservative and aggressive_swing", () => {
    expect(
      resolveEffectiveTradingPolicy("conservative").exposure
        .maxSectorExposurePct,
    ).toBe(20);
    expect(
      resolveEffectiveTradingPolicy("aggressive_swing").exposure
        .maxSectorExposurePct,
    ).toBe(40);
  });

  it("effectiveMaxSectorExposurePct matches template", () => {
    expect(effectiveMaxSectorExposurePct("moderate")).toBe(30);
    expect(effectiveMaxSectorExposurePct(undefined)).toBe(30);
  });

  it("formatPortfolioFitPreview surfaces exposure limits", () => {
    expect(formatPortfolioFitPreview(MODERATE_TRADING_POLICY)).toBe(
      "Encaja: max sector 30% · max posición 12% · 12 pos. abiertas",
    );
  });
});
