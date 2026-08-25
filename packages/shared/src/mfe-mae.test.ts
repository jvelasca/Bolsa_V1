import { describe, expect, it } from "vitest";
import { mapMfeMae } from "./cognitive/mfe-mae.js";

describe("mapMfeMae (Ciclo 5.3)", () => {
  it("peak from bars: favorable MFE and MAE", () => {
    const out = mapMfeMae({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 108,
      bars: [
        { high: 105, low: 98 },
        { high: 118, low: 99 },
      ],
    });
    expect(out.status).toBe("favorable");
    expect(out.mfeR).toBe(1.8);
    expect(out.maeR).toBe(0.2);
    expect(out.currentR).toBe(0.8);
    expect(out.why).toContain("peak_from_bars");
    expect(out.why).toContain("mfe_ge_1_5r");
  });

  it("adverse when MAE ≥ 1R from bars", () => {
    const out = mapMfeMae({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 101,
      bars: [{ high: 102, low: 88 }],
    });
    expect(out.status).toBe("adverse");
    expect(out.maeR).toBe(1.2);
    expect(out.why).toContain("mae_ge_1r");
  });

  it("close_proxy when no bars", () => {
    const out = mapMfeMae({
      direction: "long",
      entry: 100,
      structuralStop: 90,
      lastClose: 105,
    });
    expect(out.status).toBe("observe");
    expect(out.mfeR).toBe(0.5);
    expect(out.maeR).toBe(0);
    expect(out.why).toContain("close_proxy");
  });

  it("short peak from bars", () => {
    const out = mapMfeMae({
      direction: "short",
      entry: 100,
      structuralStop: 110,
      lastClose: 95,
      bars: [
        { high: 103, low: 90 },
        { high: 101, low: 85 },
      ],
    });
    expect(out.mfeR).toBe(1.5);
    expect(out.maeR).toBe(0.3);
    expect(out.status).toBe("favorable");
    expect(out.why).toContain("peak_from_bars");
  });

  it("missing inputs → none", () => {
    const out = mapMfeMae({ direction: "long", entry: 100 });
    expect(out.status).toBe("none");
    expect(out.why).toContain("missing_inputs");
  });
});
