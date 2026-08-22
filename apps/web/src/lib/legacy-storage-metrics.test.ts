import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LEGACY_STORAGE_METRICS_OPT_IN_KEY,
  collectWorkspaceDeprecatedFieldPresence,
  isLegacyStorageMetricsOptIn,
  mergeWorkspaceDeprecatedFieldPresence,
  reportLegacyStorageMetric,
  resetLegacyStorageMetricsForTests,
  shouldEmitLegacyStorageMetric,
} from "./legacy-storage-metrics";

describe("legacy-storage-metrics", () => {
  beforeEach(() => {
    localStorage.removeItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY);
    resetLegacyStorageMetricsForTests();
    vi.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(() => {
    localStorage.removeItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY);
    resetLegacyStorageMetricsForTests();
    vi.restoreAllMocks();
  });

  it("detects deprecated workspace fields on raw docs", () => {
    expect(
      collectWorkspaceDeprecatedFieldPresence({
        chartDataStrip: { showVolume: true },
        chartNewTabSeed: { instrumentId: "x" },
        preferences: { newChartConfigSource: "template" },
      }),
    ).toEqual({
      chartDataStrip: true,
      chartNewTabSeed: true,
      newChartConfigSource: true,
    });
    expect(collectWorkspaceDeprecatedFieldPresence({})).toEqual({
      chartDataStrip: false,
      chartNewTabSeed: false,
      newChartConfigSource: false,
    });
  });

  it("merges deprecated field presence across two workspace docs", () => {
    expect(
      mergeWorkspaceDeprecatedFieldPresence(
        collectWorkspaceDeprecatedFieldPresence({ chartDataStrip: {} }),
        collectWorkspaceDeprecatedFieldPresence({
          preferences: { newChartConfigSource: "active" },
        }),
      ),
    ).toEqual({
      chartDataStrip: true,
      chartNewTabSeed: false,
      newChartConfigSource: true,
    });
  });

  it("is opt-in when localStorage flag is set", () => {
    expect(isLegacyStorageMetricsOptIn()).toBe(false);
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    expect(isLegacyStorageMetricsOptIn()).toBe(true);
  });

  it("emits once per session when opted in", () => {
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    expect(shouldEmitLegacyStorageMetric("pending_orders_legacy_blob")).toBe(
      true,
    );
    reportLegacyStorageMetric("pending_orders_legacy_blob", { count: 2 });
    expect(shouldEmitLegacyStorageMetric("pending_orders_legacy_blob")).toBe(
      false,
    );
  });

  it("samples when not opted in", () => {
    const random = vi.fn().mockReturnValue(0.005);
    expect(
      shouldEmitLegacyStorageMetric("timeframe_favorites_legacy_blob", random),
    ).toBe(true);
    expect(random).toHaveBeenCalled();
    random.mockReturnValue(0.5);
    expect(
      shouldEmitLegacyStorageMetric("workspace_deprecated_fields", random),
    ).toBe(false);
  });

  it("console.debug in dev when reporting", () => {
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    reportLegacyStorageMetric("pending_orders_legacy_blob", { count: 1 });
    expect(console.debug).toHaveBeenCalledWith(
      "[legacy-storage-metric] pending_orders_legacy_blob",
      { count: 1 },
    );
  });
});
