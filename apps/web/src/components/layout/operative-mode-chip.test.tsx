/**
 * Tests — chip de modo operativo persistente (`UI5-21`).
 *
 * El chip informa del modo vigente (`AUTO`/`SEMI`/`MANUAL`) y enlaza a `/auto`. No cambia el modo
 * y no es una puerta L1. Un único casing (`UI5-10`): el libro DEMO se traduce al vocabulario
 * canónico `OPERATION_MODE_LABEL`.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

const prefsState = vi.hoisted(() => ({
  mode: "semi" as "manual" | "semi" | "auto",
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({
    mode: prefsState.mode,
    maxOpenPositions: 10,
    defaultSizePctOfCash: 10,
    countryPrefer: "home_first",
  }),
}));

import { OperativeModeChip } from "@/components/layout/operative-mode-chip";

afterEach(cleanup);

function renderChip() {
  return render(
    <MemoryRouter initialEntries={["/mesa"]}>
      <OperativeModeChip />
    </MemoryRouter>,
  );
}

describe("OperativeModeChip (UI5-21)", () => {
  it("en SEMI muestra el modo y enlaza a /auto", () => {
    prefsState.mode = "semi";
    renderChip();
    const chip = screen.getByTestId("operative-mode-chip");
    expect(chip.getAttribute("href")).toBe("/auto");
    expect(chip.getAttribute("data-mode")).toBe("SEMI");
    expect(chip.textContent).toContain("SEMI");
  });

  it.each([
    ["manual", "MANUAL"],
    ["semi", "SEMI"],
    ["auto", "AUTO"],
  ] as const)("traduce el modo %s a %s (un único casing)", (mode, label) => {
    prefsState.mode = mode;
    renderChip();
    expect(
      screen.getByTestId("operative-mode-chip").getAttribute("data-mode"),
    ).toBe(label);
  });
});
