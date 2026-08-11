/**
 * Tests — deep-links Biblioteca.
 */

import { describe, expect, it } from "vitest";
import {
  backtestLibraryHref,
  libraryHrefForPreset,
  libraryHrefForSavedStrategy,
  parseLibraryFilterParam,
  parseLibraryNavFromSearch,
} from "@/features/backtests/library-nav";

describe("library-nav", () => {
  it("builds saved strategy href", () => {
    expect(libraryHrefForSavedStrategy("abc-123")).toBe(
      "/backtests?tab=strategies&library=mine&strategyId=abc-123",
    );
  });

  it("builds preset href", () => {
    expect(libraryHrefForPreset("sma_crossover")).toContain("library=generics");
    expect(libraryHrefForPreset("sma_crossover")).toContain(
      "preset=sma_crossover",
    );
  });

  it("parses filter and search", () => {
    expect(parseLibraryFilterParam("mine")).toBe("mine");
    expect(parseLibraryFilterParam("optimized")).toBe("optimized");
    expect(parseLibraryFilterParam("x")).toBeNull();
    expect(libraryHrefForSavedStrategy("x", "optimized")).toContain(
      "library=optimized",
    );
    const sp = new URLSearchParams(
      "tab=strategies&library=mine&strategyId=s1&q=tef",
    );
    expect(parseLibraryNavFromSearch(sp)).toEqual({
      library: "mine",
      strategyId: "s1",
      preset: undefined,
      q: "tef",
    });
    expect(
      parseLibraryNavFromSearch(new URLSearchParams("tab=run")),
    ).toBeNull();
  });

  it("includes optional q", () => {
    expect(backtestLibraryHref({ library: "all", q: " ACS " })).toContain(
      "q=ACS",
    );
  });
});
