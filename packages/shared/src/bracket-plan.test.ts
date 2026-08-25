import { describe, expect, it } from "vitest";
import { mapBracketPlan, mapProtectPlan } from "./cognitive/index.js";

describe("mapBracketPlan (Ciclo 8.2)", () => {
  it("missing inputs → none", () => {
    const out = mapBracketPlan({});
    expect(out.status).toBe("none");
    expect(out.why).toEqual(["missing_inputs"]);
    expect(out.target1).toBeNull();
    expect(out.legT1QtyFrac).toBeNull();
  });

  it("zero R → none", () => {
    const out = mapBracketPlan({
      direction: "long",
      entry: 100,
      structuralStop: 100,
    });
    expect(out.status).toBe("none");
    expect(out.why).toEqual(["missing_inputs"]);
  });

  it("long picture: T1=entry+1R aligns Protect; T2=+2R; display fracs", () => {
    const out = mapBracketPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
    });
    expect(out.status).toBe("picture");
    expect(out.entry).toBe(100);
    expect(out.stop).toBe(90);
    expect(out.target1).toBe(110);
    expect(out.target2).toBe(120);
    expect(out.target1R).toBe(1);
    expect(out.target2R).toBe(2);
    expect(out.legT1QtyFrac).toBe(0.5);
    expect(out.legT2QtyFrac).toBe(0.5);
    expect(out.why).toContain("aligned_protect_t1");
    expect(out.why).toContain("display_only");
    expect(out.why).toContain("not_permission");
    expect(out.why).toContain("hint_only");
    expect(out.why).toContain("no_broker_oco");

    const protect = mapProtectPlan({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 105,
    });
    expect(out.target1).toBe(protect.target1);
  });

  it("short picture mirrors sign", () => {
    const out = mapBracketPlan({
      direction: "short",
      entry: 100,
      structuralStop: 110,
    });
    expect(out.status).toBe("picture");
    expect(out.target1).toBe(90);
    expect(out.target2).toBe(80);
  });
});
