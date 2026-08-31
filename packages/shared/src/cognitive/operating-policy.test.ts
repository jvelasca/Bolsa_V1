import { describe, expect, it } from "vitest";
import {
  formatOperatingPolicyPreview,
  resolveOperatingPolicy,
} from "./operating-policy.js";

describe("resolveOperatingPolicy", () => {
  it("composes conservative template slices", () => {
    const policy = resolveOperatingPolicy("conservative");
    expect(policy.templateId).toBe("conservative");
    expect(policy.exit.t1ReduceFraction).toBe(0.5);
    expect(policy.concentration.maxSectorExposurePct).toBe(20);
    expect(policy.trailing.ratchetOnly).toBe(true);
  });

  it("defaults to moderate", () => {
    const policy = resolveOperatingPolicy(null);
    expect(policy.templateId).toBe("moderate");
    expect(policy.exit.t2ReduceFraction).toBe(0.3);
  });

  it("formatOperatingPolicyPreview is human-readable", () => {
    const preview = formatOperatingPolicyPreview(
      resolveOperatingPolicy("aggressive_swing"),
    );
    expect(preview).toContain("aggressive_swing");
    expect(preview).toContain("trail wide");
  });
});
