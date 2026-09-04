/**
 * V2.34 / V2.35 — Chart Focus toggle touch target + a11y.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ChartFocusToggle } from "@/features/charts/chart-focus-toggle";

vi.mock("@/features/charts/use-chart-focus-prefs", () => ({
  useChartFocusPrefs: () => ({ mode: "simple" as const }),
  useSetChartFocusMode: () => vi.fn(),
}));

describe("ChartFocusToggle V2.34 touch", () => {
  beforeEach(() => {
    cleanup();
  });

  it("uses ≥36px hit area and ≥12px text (not text-[9px])", () => {
    render(<ChartFocusToggle />);
    const group = screen.getByTestId("chart-focus-toggle");
    expect(group).toBeTruthy();
    const simple = screen.getByTestId("chart-focus-mode-simple");
    const completo = screen.getByTestId("chart-focus-mode-completo");
    expect(simple.className).toMatch(/min-h-10/);
    expect(completo.className).toMatch(/min-h-10/);
    expect(simple.className).toMatch(/text-xs/);
    expect(simple.className).not.toMatch(/text-\[9px\]/);
    expect(simple.getAttribute("aria-pressed")).toBe("true");
    expect(completo.getAttribute("aria-pressed")).toBe("false");
  });
});
