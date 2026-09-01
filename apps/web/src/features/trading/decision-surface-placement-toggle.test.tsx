/**
 * V1.63 — Decision Surface placement toggle sync tests.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { DecisionSurfacePlacementToggle } from "@/features/trading/decision-surface-placement-toggle";
import { loadMercadoDecisionSurfacePrefs } from "@/features/trading/mercado-decision-surface-prefs";

afterEach(() => cleanup());

describe("DecisionSurfacePlacementToggle (V1.63)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("GP-V163-06: toggle updates shared persisted pref", () => {
    render(<DecisionSurfacePlacementToggle />);
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("panel");
    fireEvent.click(
      screen.getByRole("button", { name: "Gráfico", pressed: false }),
    );
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("chart");
    fireEvent.click(
      screen.getByRole("button", { name: "Panel", pressed: false }),
    );
    expect(loadMercadoDecisionSurfacePrefs().placement).toBe("panel");
  });
});
