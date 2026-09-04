import { describe, expect, it } from "vitest";
import {
  aggregateMesaProtectionKpi,
  buildMesaProtectionState,
  stopDistancePct,
} from "./mesa-protection-state.js";

describe("buildMesaProtectionState V2.29", () => {
  it("sugerido without executed → Planificado + discrepancy (no propuesta thin)", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      protectPlan: { status: "protect_hint", suggestedProtectStop: 182 },
      currentStop: null,
    });
    expect(s.discrepancy).toBe(true);
    expect(s.summaryLabel).toBe("Planificado");
    expect(s.proposal.label).toBe("Sugerido");
  });

  it("executed stop → Protegido", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      currentStop: 180,
    });
    expect(s.summaryLabel).toBe("Protegido");
    expect(s.discrepancy).toBe(false);
    expect(s.executed.label).toBe("Ejecución");
  });

  it("no plan → Sin protección with — SL/TP layers", () => {
    const s = buildMesaProtectionState({});
    expect(s.summaryLabel).toBe("Sin protección");
    expect(s.plan.formatted).toBe("—");
    expect(s.proposal.formatted).toBe("—");
    expect(s.executed.formatted).toBe("—");
  });

  it("protect_hint without executed → not Protegido", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      protectPlan: { status: "protect_hint", suggestedProtectStop: 182 },
      currentStop: null,
    });
    expect(s.summaryLabel).not.toBe("Protegido");
    expect(s.summaryLabel).not.toBe("Confirmada");
    expect(s.summaryLabel).toBe("Planificado");
  });

  it("persist skipped → Enviado + discrepancy", () => {
    const s = buildMesaProtectionState({
      study: { hasOperationalPlan: true, stop: 180 },
      currentStop: 180,
      persistSkipped: true,
    });
    expect(s.discrepancy).toBe(true);
    expect(s.summaryLabel).toBe("Enviado");
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

describe("aggregateMesaProtectionKpi", () => {
  it("counts Protegido and discrepancies", () => {
    const kpi = aggregateMesaProtectionKpi([
      buildMesaProtectionState({ currentStop: 10 }),
      buildMesaProtectionState({}),
      buildMesaProtectionState({
        protectPlan: { status: "protect_hint", suggestedProtectStop: 9 },
        currentStop: null,
      }),
    ]);
    expect(kpi).toEqual({
      protected: 1,
      open: 3,
      discrepancies: 1,
      pct: 33,
    });
  });

  it("empty portfolio → zeros and null pct", () => {
    expect(aggregateMesaProtectionKpi([])).toEqual({
      protected: 0,
      open: 0,
      discrepancies: 0,
      pct: null,
    });
  });
});
