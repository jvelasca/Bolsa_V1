import { describe, expect, it } from "vitest";
import { mapExitRadar } from "./cognitive/exit-radar.js";

describe("mapExitRadar (Ciclo 5.2)", () => {
  it("priority: exit_hint beats trail when thesis exits", () => {
    const out = mapExitRadar({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 120,
      thesisHint: "exit",
      rMultiple: 2,
    });
    expect(out.status).toBe("exit_hint");
    expect(out.why).toContain("thesis_exit");
    expect(out.why).toContain("mfe_ge_1_5r");
  });

  it("beyond target1 → exit_hint", () => {
    const out = mapExitRadar({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 110,
      target1: 110,
    });
    expect(out.status).toBe("exit_hint");
    expect(out.why).toContain("beyond_target1");
  });

  it("expired → time_stop_hint", () => {
    const out = mapExitRadar({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 101,
      expiresAt: "2026-08-01T00:00:00Z",
      nowIso: "2026-08-25T00:00:00Z",
    });
    expect(out.status).toBe("time_stop_hint");
    expect(out.why).toContain("expired");
  });

  it("MFE ≥ 1.5R → trail_hint with suggestedTrailStop", () => {
    const out = mapExitRadar({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 115,
    });
    expect(out.status).toBe("trail_hint");
    expect(out.suggestedTrailStop).toBe(105);
    expect(out.why).toContain("mfe_ge_1_5r");
  });

  it("below thresholds → none", () => {
    const out = mapExitRadar({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 105,
    });
    expect(out.status).toBe("none");
    expect(out.suggestedTrailStop).toBeNull();
  });
});
