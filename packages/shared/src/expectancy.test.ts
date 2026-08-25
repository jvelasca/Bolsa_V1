import { describe, expect, it } from "vitest";
import { mapExpectancy } from "./cognitive/expectancy.js";

describe("mapExpectancy (Ciclo 8.0)", () => {
  it("missing inputs → none", () => {
    const out = mapExpectancy({});
    expect(out.status).toBe("none");
    expect(out.n).toBe(0);
    expect(out.why).toEqual(["missing_inputs"]);
  });

  it("live proxy thin sample", () => {
    const out = mapExpectancy({
      samples: [{ entrySetup: "breakout", rMultiple: 0.8 }],
      focusSetup: "breakout",
      currentR: 0.8,
    });
    expect(out.status).toBe("thin");
    expect(out.n).toBe(1);
    expect(out.expectancyR).toBe(0.8);
    expect(out.winRate).toBe(1);
    expect(out.why).toContain("live_proxy");
    expect(out.why).toContain("thin_sample");
    expect(out.why).toContain("not_permission");
  });

  it("aggregate mean R ready at n≥5", () => {
    const out = mapExpectancy({
      samples: [
        { entrySetup: "pullback", rMultiple: 1 },
        { entrySetup: "pullback", rMultiple: -0.5 },
        { entrySetup: "pullback", rMultiple: 2 },
        { entrySetup: "pullback", rMultiple: -1 },
        { entrySetup: "pullback", rMultiple: 0.5 },
        { entrySetup: "breakout", rMultiple: 9 },
      ],
      focusSetup: "pullback",
    });
    expect(out.status).toBe("ready");
    expect(out.n).toBe(5);
    expect(out.expectancyR).toBe(0.4);
    expect(out.winRate).toBe(0.6);
    expect(out.why).toContain("aggregated");
    expect(out.why).not.toContain("thin_sample");
  });

  it("ignores entrySetup none", () => {
    const out = mapExpectancy({
      samples: [{ entrySetup: "none", rMultiple: 1 }],
      focusSetup: "none",
      currentR: 1,
    });
    expect(out.status).toBe("none");
  });
});
