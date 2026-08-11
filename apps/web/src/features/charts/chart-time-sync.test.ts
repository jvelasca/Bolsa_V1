import { describe, expect, it } from "vitest";
import {
  CHART_HORIZONTAL_ZOOM_FACTOR,
  logicalRangesEqual,
  zoomLogicalRange,
} from "@/features/charts/chart-time-sync";

describe("chart-time-sync", () => {
  it("compara rangos lógicos con tolerancia", () => {
    expect(logicalRangesEqual({ from: 0, to: 100 }, { from: 0, to: 100 })).toBe(
      true,
    );
    expect(
      logicalRangesEqual({ from: 10.0001, to: 50 }, { from: 10, to: 50.0001 }),
    ).toBe(true);
    expect(logicalRangesEqual({ from: 0, to: 100 }, { from: 5, to: 100 })).toBe(
      false,
    );
  });

  it("zoom sin ancla se centra en el rango", () => {
    const range = { from: 0, to: 100 };
    const zoomed = zoomLogicalRange(range, "in");
    const mid = 50;
    expect((zoomed.from + zoomed.to) / 2).toBeCloseTo(mid, 6);
    expect(zoomed.to - zoomed.from).toBeCloseTo(
      100 * CHART_HORIZONTAL_ZOOM_FACTOR,
      6,
    );
  });

  it("zoom anclado mantiene el logical del cursor fijo", () => {
    const range = { from: 0, to: 100 };
    const anchor = 25;
    const zoomedIn = zoomLogicalRange(range, "in", anchor);
    const ratioIn = (anchor - range.from) / (range.to - range.from);
    const spanIn = zoomedIn.to - zoomedIn.from;
    expect(zoomedIn.from + ratioIn * spanIn).toBeCloseTo(anchor, 6);

    const zoomedOut = zoomLogicalRange(range, "out", anchor);
    const ratioOut = (anchor - range.from) / (range.to - range.from);
    const spanOut = zoomedOut.to - zoomedOut.from;
    expect(zoomedOut.from + ratioOut * spanOut).toBeCloseTo(anchor, 6);
    expect(spanOut).toBeCloseTo(100 / CHART_HORIZONTAL_ZOOM_FACTOR, 6);
  });
});
