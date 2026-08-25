import { describe, expect, it } from "vitest";
import { mapExpectancy, sampleQualityFromN } from "./cognitive/expectancy.js";

function nSamples(n: number, setup = "pullback") {
  return Array.from({ length: n }, (_, i) => ({
    entrySetup: setup,
    rMultiple: i % 2 === 0 ? 1 : -0.5,
  }));
}

describe("sampleQualityFromN (Ciclo C5)", () => {
  it("honesty bands independent of ready threshold", () => {
    expect(sampleQualityFromN(0)).toBe("insufficient");
    expect(sampleQualityFromN(19)).toBe("insufficient");
    expect(sampleQualityFromN(20)).toBe("preliminary");
    expect(sampleQualityFromN(49)).toBe("preliminary");
    expect(sampleQualityFromN(50)).toBe("developing");
    expect(sampleQualityFromN(99)).toBe("developing");
    expect(sampleQualityFromN(100)).toBe("useful");
  });
});

describe("mapExpectancy (Ciclo 8.0)", () => {
  it("missing inputs → none", () => {
    const out = mapExpectancy({});
    expect(out.status).toBe("none");
    expect(out.n).toBe(0);
    expect(out.why).toEqual(["missing_inputs"]);
    expect(out.sampleQuality).toBe("insufficient");
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
    expect(out.sampleQuality).toBe("insufficient");
  });

  it("aggregate mean R ready at n≥5 is still statistically insufficient", () => {
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
    expect(out.sampleQuality).toBe("insufficient");
  });

  it("ignores entrySetup none", () => {
    const out = mapExpectancy({
      samples: [{ entrySetup: "none", rMultiple: 1 }],
      focusSetup: "none",
      currentR: 1,
    });
    expect(out.status).toBe("none");
    expect(out.sampleQuality).toBe("insufficient");
  });

  it("sampleQuality bands via n", () => {
    expect(mapExpectancy({ samples: nSamples(20) }).sampleQuality).toBe(
      "preliminary",
    );
    expect(mapExpectancy({ samples: nSamples(50) }).sampleQuality).toBe(
      "developing",
    );
    expect(mapExpectancy({ samples: nSamples(100) }).sampleQuality).toBe(
      "useful",
    );
    expect(mapExpectancy({ samples: nSamples(20) }).status).toBe("ready");
  });
});
