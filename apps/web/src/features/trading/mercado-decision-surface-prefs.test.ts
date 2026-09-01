import { beforeEach, describe, expect, it } from "vitest";
import {
  MERCADO_DECISION_SURFACE_PREFS_KEY,
  defaultMercadoDecisionSurfacePrefs,
  loadMercadoDecisionSurfacePrefs,
  normalizeMercadoDecisionSurfacePrefs,
  patchMercadoDecisionSurfacePrefs,
  saveMercadoDecisionSurfacePrefs,
} from "@/features/trading/mercado-decision-surface-prefs";

describe("mercado-decision-surface-prefs (V1.63)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("GP-V163-01: defaults to panel placement", () => {
    const d = defaultMercadoDecisionSurfacePrefs();
    expect(d.placement).toBe("panel");
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("panel");
  });

  it("GP-V163-01: load/save round-trip", () => {
    saveMercadoDecisionSurfacePrefs({ placement: "chart" });
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("chart");
    expect(
      JSON.parse(localStorage.getItem(MERCADO_DECISION_SURFACE_PREFS_KEY)!)
        .placement,
    ).toBe("chart");
  });

  it("GP-V163-01: normalizes invalid placement to panel", () => {
    const n = normalizeMercadoDecisionSurfacePrefs({ placement: "invalid" });
    expect(n.placement).toBe("panel");
  });

  it("GP-V163-06: patch updates persisted value", () => {
    patchMercadoDecisionSurfacePrefs({ placement: "chart" });
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("chart");
    patchMercadoDecisionSurfacePrefs({ placement: "panel" });
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("panel");
  });
});
