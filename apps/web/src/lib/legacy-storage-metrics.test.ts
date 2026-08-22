import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LEGACY_STORAGE_METRICS_LOG_CAP,
  LEGACY_STORAGE_METRICS_LOG_KEY,
  LEGACY_STORAGE_METRICS_OPT_IN_KEY,
  clearLegacyStorageMetricsLog,
  collectWorkspaceDeprecatedFieldPresence,
  isLegacyStorageMetricsOptIn,
  mergeWorkspaceDeprecatedFieldPresence,
  readLegacyStorageMetricsLog,
  reportLegacyStorageMetric,
  resetLegacyStorageMetricsForTests,
  shouldEmitLegacyStorageMetric,
} from "./legacy-storage-metrics";

describe("legacy-storage-metrics", () => {
  beforeEach(() => {
    localStorage.removeItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY);
    clearLegacyStorageMetricsLog();
    resetLegacyStorageMetricsForTests();
    vi.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(() => {
    localStorage.removeItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY);
    clearLegacyStorageMetricsLog();
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

  it("persists an inspectable log entry when emission fires", () => {
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    reportLegacyStorageMetric("pending_orders_legacy_blob", { count: 3 });
    const log = readLegacyStorageMetricsLog();
    expect(log).toHaveLength(1);
    expect(log[0]).toMatchObject({
      name: "pending_orders_legacy_blob",
      payload: { count: 3 },
    });
    expect(typeof log[0]?.ts).toBe("string");
    expect(Number.isNaN(Date.parse(log[0]!.ts))).toBe(false);
  });

  it("caps the inspectable log at LEGACY_STORAGE_METRICS_LOG_CAP", () => {
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    const seeded = Array.from(
      { length: LEGACY_STORAGE_METRICS_LOG_CAP },
      (_, i) => ({
        ts: `2026-01-01T00:00:${String(i).padStart(2, "0")}.000Z`,
        name: `seeded_${i}`,
        payload: { i },
      }),
    );
    localStorage.setItem(
      LEGACY_STORAGE_METRICS_LOG_KEY,
      JSON.stringify(seeded),
    );
    reportLegacyStorageMetric("workspace_deprecated_fields", {
      chartDataStrip: true,
    });
    const log = readLegacyStorageMetricsLog();
    expect(log).toHaveLength(LEGACY_STORAGE_METRICS_LOG_CAP);
    expect(log[0]?.name).toBe("seeded_1");
    expect(log[log.length - 1]).toMatchObject({
      name: "workspace_deprecated_fields",
      payload: { chartDataStrip: true },
    });
  });

  it("clearLegacyStorageMetricsLog empties the inspectable log", () => {
    localStorage.setItem(LEGACY_STORAGE_METRICS_OPT_IN_KEY, "1");
    reportLegacyStorageMetric("timeframe_favorites_legacy_blob", {
      present: true,
    });
    expect(readLegacyStorageMetricsLog()).toHaveLength(1);
    clearLegacyStorageMetricsLog();
    expect(readLegacyStorageMetricsLog()).toEqual([]);
    expect(localStorage.getItem(LEGACY_STORAGE_METRICS_LOG_KEY)).toBeNull();
  });

  it("does not persist when opted out and sample misses", () => {
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    reportLegacyStorageMetric("pending_orders_legacy_blob", { count: 1 });
    expect(readLegacyStorageMetricsLog()).toEqual([]);
  });
});
