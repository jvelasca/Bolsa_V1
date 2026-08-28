import { describe, expect, it } from "vitest";
import {
  adverseExposure,
  validateOperationalLevels,
} from "./cognitive/operational-levels.js";

describe("validateOperationalLevels", () => {
  it("LONG: stop < entry < T1 < T2 is ok", () => {
    const v = validateOperationalLevels({
      direction: "long",
      entry: 100,
      stop: 95,
      target1: 110,
      target2: 120,
    });
    expect(v.ok).toBe(true);
    expect(v.reason).toBeNull();
    expect(v.riskDistance).toBe(5);
  });

  it("LONG: stop above entry is stop_wrong_side", () => {
    const v = validateOperationalLevels({
      direction: "long",
      entry: 100,
      stop: 110,
    });
    expect(v.ok).toBe(false);
    expect(v.reason).toBe("stop_wrong_side");
  });

  it("SHORT: stop below entry is stop_wrong_side", () => {
    const v = validateOperationalLevels({
      direction: "short",
      entry: 100,
      stop: 90,
    });
    expect(v.ok).toBe(false);
    expect(v.reason).toBe("stop_wrong_side");
  });

  it("SHORT: T2 < T1 < entry < stop is ok", () => {
    const v = validateOperationalLevels({
      direction: "short",
      entry: 100,
      stop: 110,
      target1: 90,
      target2: 80,
    });
    expect(v.ok).toBe(true);
    expect(v.riskDistance).toBe(10);
  });

  it("T1 on the wrong side of entry is targets_invalid", () => {
    const v = validateOperationalLevels({
      direction: "long",
      entry: 100,
      stop: 95,
      target1: 90,
    });
    expect(v.ok).toBe(false);
    expect(v.reason).toBe("targets_invalid");
  });

  it("missing direction or non-positive levels is risk_non_positive", () => {
    expect(
      validateOperationalLevels({
        direction: "none",
        entry: 100,
        stop: 95,
      }).reason,
    ).toBe("risk_non_positive");
    expect(
      validateOperationalLevels({
        direction: "long",
        entry: 100,
        stop: 0,
      }).reason,
    ).toBe("risk_non_positive");
  });

  it("adverseExposure is signed, not abs", () => {
    expect(adverseExposure("long", 100, 95)).toBe(5);
    expect(adverseExposure("long", 100, 110)).toBe(0);
    expect(adverseExposure("short", 100, 110)).toBe(10);
    expect(adverseExposure("short", 100, 90)).toBe(0);
  });
});
