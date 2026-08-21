/**
 * Protects the one-shot localStorage timeframe-favorites path in normalizeWorkspace.
 * Do not delete readLegacyTimeframeFavorites or LEGACY_TIMEFRAME_FAVORITES_KEY until E8.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  LEGACY_TIMEFRAME_FAVORITES_KEY,
  normalizeWorkspace,
} from "./workspace-store-core";

describe("workspace legacy timeframe favorites", () => {
  beforeEach(() => {
    localStorage.removeItem(LEGACY_TIMEFRAME_FAVORITES_KEY);
  });

  afterEach(() => {
    localStorage.removeItem(LEGACY_TIMEFRAME_FAVORITES_KEY);
  });

  it("keeps the storage key name bolsa-chart-timeframe-favorites", () => {
    expect(LEGACY_TIMEFRAME_FAVORITES_KEY).toBe(
      "bolsa-chart-timeframe-favorites",
    );
  });

  it("picks up localStorage favorites via normalizeWorkspace", () => {
    localStorage.setItem(
      LEGACY_TIMEFRAME_FAVORITES_KEY,
      JSON.stringify(["1d", "1h", "not-a-tf"]),
    );

    const workspace = normalizeWorkspace({});

    expect(workspace.chartToolbarGlobal?.timeframeFavorites).toEqual([
      "1d",
      "1h",
    ]);
  });

  it("does not override workspace timeframeFavorites with the legacy key", () => {
    localStorage.setItem(
      LEGACY_TIMEFRAME_FAVORITES_KEY,
      JSON.stringify(["1d", "1h"]),
    );

    const workspace = normalizeWorkspace({
      chartToolbarGlobal: { timeframeFavorites: ["4h"] } as never,
    });

    expect(workspace.chartToolbarGlobal?.timeframeFavorites).toEqual(["4h"]);
  });

  it("ignores a malformed legacy blob", () => {
    localStorage.setItem(LEGACY_TIMEFRAME_FAVORITES_KEY, "{not-json");

    const workspace = normalizeWorkspace({});

    expect(workspace.chartToolbarGlobal?.timeframeFavorites).toEqual([]);
  });

  it("ignores a non-array legacy blob", () => {
    localStorage.setItem(
      LEGACY_TIMEFRAME_FAVORITES_KEY,
      JSON.stringify({ favorites: ["1d"] }),
    );

    const workspace = normalizeWorkspace({});

    expect(workspace.chartToolbarGlobal?.timeframeFavorites).toEqual([]);
  });
});
