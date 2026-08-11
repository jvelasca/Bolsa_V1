import { describe, expect, it } from "vitest";
import { normalizeSidebarPanelLayout } from "@/lib/screener-split-layout";

describe("normalizeSidebarPanelLayout", () => {
  it("returns equal split when no stored sizes", () => {
    const layout = normalizeSidebarPanelLayout(["trackers", "execution"], {});
    expect(layout.trackers).toBeCloseTo(50, 1);
    expect(layout.execution).toBeCloseTo(50, 1);
  });

  it("normalizes stored sizes to 100%", () => {
    const layout = normalizeSidebarPanelLayout(["trackers", "execution"], {
      trackers: 30,
      execution: 30,
    });
    expect(layout.trackers).toBeCloseTo(50, 1);
    expect(layout.execution).toBeCloseTo(50, 1);
  });
});
