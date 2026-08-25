import { describe, expect, it } from "vitest";
import { mapProtectPlan } from "./cognitive/protect-plan.js";

describe("mapProtectPlan (Ciclo 5.1 / Golden E)", () => {
  it("Golden E: long MFE ≥ 1R → protect_hint + T1 + suggestedProtectStop=entry", () => {
    const out = mapProtectPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 110,
    });
    expect(out.status).toBe("protect_hint");
    expect(out.target1).toBe(110);
    expect(out.suggestedProtectStop).toBe(100);
    expect(out.rMultiple).toBe(1);
    expect(out.why).toContain("mfe_ge_1r");
  });

  it("long below 1R → none (T1 still computed)", () => {
    const out = mapProtectPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 105,
    });
    expect(out.status).toBe("none");
    expect(out.target1).toBe(110);
    expect(out.suggestedProtectStop).toBeNull();
    expect(out.rMultiple).toBe(0.5);
  });

  it("short MFE ≥ 1R → protect_hint", () => {
    const out = mapProtectPlan({
      direction: "short",
      entry: 100,
      structuralStop: 110,
      lastClose: 90,
    });
    expect(out.status).toBe("protect_hint");
    expect(out.target1).toBe(90);
    expect(out.suggestedProtectStop).toBe(100);
  });

  it("missing inputs → none + missing_inputs", () => {
    const out = mapProtectPlan({
      direction: "long",
      entry: 100,
      structuralStop: null,
      lastClose: 110,
    });
    expect(out.status).toBe("none");
    expect(out.why).toContain("missing_inputs");
    expect(out.target1).toBeNull();
  });

  it("does not mutate conceptual structuralStop (advisory only)", () => {
    const out = mapProtectPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 120,
    });
    expect(out.suggestedProtectStop).toBe(100);
    expect(out).not.toHaveProperty("structuralStop");
  });
});
