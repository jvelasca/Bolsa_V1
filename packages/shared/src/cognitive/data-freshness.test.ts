import { describe, expect, it } from "vitest";
import {
  buildDataFreshness,
  DATA_FRESHNESS_ABSENT_LABEL,
  DATA_FRESHNESS_THRESHOLD_MINUTES,
} from "./data-freshness.js";

describe("data-freshness", () => {
  it("unknown when no lastBarDate", () => {
    expect(buildDataFreshness({}).status).toBe("unknown");
  });

  it("unknown declara el hueco con la frase oficial, nunca con el comodín —", () => {
    const f = buildDataFreshness({});
    expect(f.status).toBe("unknown");
    expect(f.label).toBe("Sin dato todavía");
    expect(f.label).toBe(DATA_FRESHNESS_ABSENT_LABEL);
    expect(f.label).not.toBe("—");
  });

  it("invalid declara el hueco con la frase oficial y conserva el raw", () => {
    const f = buildDataFreshness({ lastBarDate: "no-es-una-fecha" });
    expect(f.status).toBe("invalid");
    expect(f.asOf).toBe("no-es-una-fecha");
    expect(f.label).toBe("Sin dato todavía");
    expect(f.label).not.toBe("—");
  });

  it("fresh when recent", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    expect(buildDataFreshness({ lastBarDate: last, now }).status).toBe("fresh");
  });

  it("stale when beyond threshold", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-01T12:00:00Z").toISOString();
    const f = buildDataFreshness({ lastBarDate: last, now });
    expect(f.status).toBe("stale");
    expect(f.thresholdMinutes).toBe(DATA_FRESHNESS_THRESHOLD_MINUTES);
  });

  it("error on query failed", () => {
    expect(buildDataFreshness({ queryFailed: true }).status).toBe("error");
  });

  it("partial sample never claims portfolio-wide fresh", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    const f = buildDataFreshness({
      lastBarDate: last,
      now,
      partialSample: { probed: 1, total: 3 },
    });
    expect(f.status).not.toBe("fresh");
    expect(f.label).toMatch(/muestra parcial \(1\/3\)/i);
  });

  it("single-position probe can stay fresh", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    expect(
      buildDataFreshness({
        lastBarDate: last,
        now,
        partialSample: { probed: 1, total: 1 },
      }).status,
    ).toBe("fresh");
  });
});
