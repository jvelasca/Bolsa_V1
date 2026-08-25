import { describe, expect, it } from "vitest";
import { mapThesisHealth } from "./cognitive/thesis-health.js";

describe("mapThesisHealth (Ciclo 5.0 / Golden F)", () => {
  it("Golden F: degraded confidence + long price above stop → review", () => {
    const out = mapThesisHealth({
      confidence: 0.3,
      direction: "long",
      lastClose: 100,
      structuralStop: 90,
    });
    expect(out.hint).toBe("reduce");
    expect(out.status).toBe("review");
    expect(out.why).toContain("confidence_degraded");
    expect(out.why).toContain("stop_intact");
  });

  it("degraded but stop broken → ok (not Golden F)", () => {
    const out = mapThesisHealth({
      confidence: 0.2,
      direction: "long",
      lastClose: 85,
      structuralStop: 90,
    });
    expect(out.hint).toBe("exit");
    expect(out.status).toBe("ok");
    expect(out.why).not.toContain("stop_intact");
  });

  it("hold + stop intact → ok", () => {
    const out = mapThesisHealth({
      confidence: 0.8,
      direction: "long",
      lastClose: 100,
      structuralStop: 90,
    });
    expect(out.hint).toBe("hold");
    expect(out.status).toBe("ok");
  });

  it("short: stop intact when price below stop", () => {
    const out = mapThesisHealth({
      confidence: 0.3,
      direction: "short",
      lastClose: 80,
      structuralStop: 90,
    });
    expect(out.status).toBe("review");
  });

  it("missing stop → never invents review from price", () => {
    const out = mapThesisHealth({
      confidence: 0.2,
      direction: "long",
      lastClose: 100,
      structuralStop: null,
    });
    expect(out.status).toBe("ok");
    expect(out.hint).toBe("exit");
  });

  it("does not use TradePlan REVIEW ladder semantics", () => {
    const out = mapThesisHealth({
      confidence: 0.1,
      direction: "long",
      lastClose: 110,
      structuralStop: 100,
      hardExit: true,
    });
    expect(out.status).toBe("review");
    expect(out.hint).toBe("exit");
    // Advisory status only — callers must not map this to TradePlan.status.
    expect(out).not.toHaveProperty("tradePlanStatus");
  });
});
