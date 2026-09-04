/**
 * V2.30 — Chart Focus prefs tests.
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  CHART_FOCUS_PREFS_KEY,
  defaultChartFocusPrefs,
  loadChartFocusPrefs,
  normalizeChartFocusPrefs,
  patchChartFocusPrefs,
  saveChartFocusPrefs,
} from "@/features/charts/chart-focus-prefs";

describe("chart-focus-prefs (V2.30)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to simple (menos ruido)", () => {
    const d = defaultChartFocusPrefs();
    expect(d.mode).toBe("simple");
    expect(loadChartFocusPrefs().mode).toBe("simple");
  });

  it("load/save round-trip", () => {
    saveChartFocusPrefs({ mode: "completo" });
    expect(loadChartFocusPrefs().mode).toBe("completo");
    expect(JSON.parse(localStorage.getItem(CHART_FOCUS_PREFS_KEY)!).mode).toBe(
      "completo",
    );
  });

  it("normalizes invalid mode to simple", () => {
    expect(normalizeChartFocusPrefs({ mode: "invalid" }).mode).toBe("simple");
    expect(normalizeChartFocusPrefs(null).mode).toBe("simple");
  });

  it("patch updates persisted value", () => {
    patchChartFocusPrefs({ mode: "completo" });
    expect(loadChartFocusPrefs().mode).toBe("completo");
    patchChartFocusPrefs({ mode: "simple" });
    expect(loadChartFocusPrefs().mode).toBe("simple");
  });
});
