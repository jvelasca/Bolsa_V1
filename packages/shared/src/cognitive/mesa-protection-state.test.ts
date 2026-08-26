import { describe, expect, it } from "vitest";
import {
  buildMesaProtectionState,
  stopDistancePct,
} from "./mesa-protection-state.js";

describe("buildMesaProtectionState", () => {
  it("shows discrepancy when proposal without executed", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      protectPlan: { status: "protect_hint", suggestedProtectStop: 182 },
      currentStop: null,
    });
    expect(s.discrepancy).toBe(true);
    expect(s.summaryLabel).toBe("Discrepancia");
  });

  it("confirmed when executed stop present", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      currentStop: 180,
    });
    expect(s.summaryLabel).toBe("Confirmada");
    expect(s.discrepancy).toBe(false);
  });

  it("no plan → Sin protección with — SL/TP layers", () => {
    const s = buildMesaProtectionState({});
    expect(s.summaryLabel).toBe("Sin protección");
    expect(s.plan.formatted).toBe("—");
    expect(s.proposal.formatted).toBe("—");
    expect(s.executed.formatted).toBe("—");
  });

  it("protect_hint without executed → not Confirmada", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      protectPlan: { status: "protect_hint", suggestedProtectStop: 182 },
      currentStop: null,
    });
    expect(s.summaryLabel).not.toBe("Confirmada");
    expect(s.summaryLabel).toBe("Discrepancia");
  });

  it("persist skipped → discrepancy", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      currentStop: 180,
      persistSkipped: true,
    });
    expect(s.discrepancy).toBe(true);
    expect(s.summaryLabel).toBe("Discrepancia");
  });
});

describe("stopDistancePct", () => {
  it("computes distance when price and stop exist", () => {
    expect(stopDistancePct(100, 95)).toBe(5);
  });

  it("returns null without data", () => {
    expect(stopDistancePct(null, 95)).toBeNull();
  });
});
