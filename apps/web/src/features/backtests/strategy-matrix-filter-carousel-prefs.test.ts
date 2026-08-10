import { describe, expect, it } from "vitest";
import {
  normalizeStrategyMatrixFilter,
  normalizeStrategyMatrixFilterCarouselPrefs,
  orderedVisibleStrategyMatrixFilters,
  toggleStrategyMatrixFilterFavorite,
  toggleStrategyMatrixFilterVisible,
} from "@/features/backtests/strategy-matrix-filter-carousel-prefs";

describe("strategy-matrix-filter-carousel-prefs", () => {
  it("maps legacy saved filter to mine", () => {
    expect(normalizeStrategyMatrixFilter("saved")).toBe("mine");
  });

  it("orders favorites first", () => {
    const prefs = normalizeStrategyMatrixFilterCarouselPrefs({
      visibleIds: ["all", "preset", "optimized", "mine", "finalists"],
      favoriteIds: ["finalists", "mine"],
    });
    expect(orderedVisibleStrategyMatrixFilters(prefs)).toEqual([
      "mine",
      "finalists",
      "all",
      "preset",
      "optimized",
    ]);
  });

  it("does not hide the last visible chip", () => {
    const prefs = normalizeStrategyMatrixFilterCarouselPrefs({
      visibleIds: ["preset"],
      favoriteIds: ["preset"],
    });
    expect(toggleStrategyMatrixFilterVisible(prefs, "preset")).toEqual(prefs);
  });

  it("toggles favorite only when visible", () => {
    const prefs = normalizeStrategyMatrixFilterCarouselPrefs({
      visibleIds: ["all", "preset"],
      favoriteIds: ["all"],
    });
    expect(
      toggleStrategyMatrixFilterFavorite(prefs, "preset").favoriteIds,
    ).toContain("preset");
  });
});
