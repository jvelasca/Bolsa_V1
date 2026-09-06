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
      liveReconciliationStatus: "clean",
      liveAdapterWired: true,
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_EXPERIMENTAL");
    expect(report.notes).toContain("live_not_accepted");
    expect(report.reasons).not.toContain("live_unavailable");
    expect(report.reasons).not.toContain("live_adapter_not_wired");
  });

  it("live unmeasured recon blocks", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      liveAdapterWired: true,
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_BLOCKED");
    expect(report.reasons).toContain("live_unavailable");
  });

  it("live drift blocks", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      liveReconciliationStatus: "drift",
      liveAdapterWired: true,
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_BLOCKED");
    expect(report.reasons).toContain("live_drift");
  });

  it("live unavailable blocks", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      liveReconciliationStatus: "unavailable",
      liveAdapterWired: true,
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_BLOCKED");
    expect(report.reasons).toContain("live_unavailable");
  });

  it("live adapter null blocks", () => {
    const report = deriveOperationalReadiness({
      brokerVenue: "live",
      portfolioReconciliationStatus: "ok",
      liveReconciliationStatus: "clean",
      liveAdapterWired: null,
      semiPathMark: "PASS",
    });
    expect(report.state).toBe("LIVE_BLOCKED");
    expect(report.reasons).toContain("live_adapter_not_wired");
  });
});

describe("OR-6 executeCtaLabel", () => {
  it("names the venue on execute and keeps protect copy", () => {
    expect(executeCtaLabel("paper")).toBe("Ejecutar en PAPER");
    expect(executeCtaLabel("live")).toBe(
      "Firmar · Ejecutar en LIVE VIRTUAL (simulado)",
    );
    expect(executeCtaLabel("live")).toMatch(/VIRTUAL/i);
    expect(executeCtaLabel("live")).toMatch(/simulado/i);
    expect(executeCtaLabel("live")).not.toMatch(/^Ejecutar en LIVE$/);
    expect(executeCtaLabel("paper", "protect")).toBe("Confirmar protección");
  });
});
