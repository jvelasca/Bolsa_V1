import { describe, expect, it } from "vitest";
import { mapTrailPlan } from "./cognitive/trail-plan.js";

describe("mapTrailPlan (Ciclo 8.1)", () => {
  it("missing inputs → none", () => {
    const out = mapTrailPlan({});
    expect(out.status).toBe("none");
    expect(out.why).toEqual(["missing_inputs"]);
    expect(out.suggestedTrailStop).toBeNull();
  });

  it("peak below 1.5R → none with mfe_lt_1_5r", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      peakMfeR: 1.2,
    });
    expect(out.status).toBe("none");
    expect(out.peakMfeR).toBe(1.2);
    expect(out.why).toContain("mfe_lt_1_5r");
    expect(out.why).toContain("not_permission");
    expect(out.why).toContain("hint_only");
  });

  it("peak 1.5R → tip aligned with Exit Radar (lock 0.5R)", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      peakMfeR: 1.5,
      currentR: 1.2,
    });
    expect(out.status).toBe("tip");
    expect(out.lockedR).toBe(0.5);
    expect(out.suggestedTrailStop).toBe(105);
    expect(out.trailDistanceR).toBe(1);
    expect(out.why).toContain("aligned_exit_radar_tip");
    expect(out.why).toContain("hint_only");
  });

  it("peak 2.5R → ratchet continuous lock", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      peakMfeR: 2.5,
    });
    expect(out.status).toBe("ratchet");
    expect(out.lockedR).toBe(1.5);
    expect(out.suggestedTrailStop).toBe(115);
    expect(out.why).toContain("ratchet_lock");
  });

  it("short ratchet mirrors sign", () => {
    const out = mapTrailPlan({
      direction: "short",
      entry: 100,
      structuralStop: 110,
      peakMfeR: 2.0,
    });
    expect(out.status).toBe("ratchet");
    expect(out.lockedR).toBe(1);
    expect(out.suggestedTrailStop).toBe(90);
  });

  it("falls back to currentR as peak proxy", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      currentR: 1.8,
    });
    expect(out.status).toBe("tip");
    expect(out.peakMfeR).toBe(1.8);
    expect(out.lockedR).toBe(0.8);
    expect(out.suggestedTrailStop).toBe(108);
  });

  it("V1.29 — tight trailWidth shortens distance", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      peakMfeR: 2.0,
      trailWidth: "tight",
    });
    expect(out.trailDistanceR).toBe(0.75);
    expect(out.lockedR).toBe(1.25);
    expect(out.suggestedTrailStop).toBe(112.5);
  });

  it("V1.29 — clamps trail that would worsen currentStop", () => {
    const out = mapTrailPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      peakMfeR: 1.5,
      currentStop: 108,
    });
    // raw tip would be 105; clamp keeps 108
    expect(out.suggestedTrailStop).toBe(108);
    expect(out.why).toContain("clamped_not_worsen");
  });
});
