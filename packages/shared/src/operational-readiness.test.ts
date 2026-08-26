/**
 * OR-6 — deriveOperationalReadiness + executeCtaLabel mirror tests.
 */

import { describe, expect, it } from "vitest";
import {
  deriveOperationalReadiness,
  executeCtaLabel,
} from "./cognitive/operational-readiness.js";

describe("OR-6 deriveOperationalReadiness", () => {
  it("paper ready when recon ok and SEMI path", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "paper",
      portfolioReconciliationStatus: "ok",
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("PAPER_READY");
    expect(report.reasons).toEqual([]);
  });

  it("does not average portfolio drift into a percent", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "paper",
      portfolioReconciliationStatus: "drift",
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("PAPER_DEGRADED");
    expect(report.reasons).toContain("portfolio_drift");
    expect(report.rule.includes("%")).toBe(false);
  });

  it("live clean is experimental never READY", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_EXPERIMENTAL");
    expect(report.notes).toContain("live_not_accepted");
  });

  it("live unavailable blocks", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      liveReconciliationStatus: "unavailable",
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_BLOCKED");
    expect(report.reasons).toContain("live_unavailable");
  });
});

describe("OR-6 executeCtaLabel", () => {
  it("names the venue on execute and keeps protect copy", () => {
    expect(executeCtaLabel("paper")).toBe("Ejecutar en PAPER");
    expect(executeCtaLabel("live")).toBe("Ejecutar en LIVE");
    expect(executeCtaLabel("paper", "protect")).toBe("Confirmar protección");
  });
});
