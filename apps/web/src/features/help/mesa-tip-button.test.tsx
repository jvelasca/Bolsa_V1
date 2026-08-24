/**
 * Tests — catálogo y botón de tips de mesa operativa.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import {
  getMesaTip,
  MESA_TIP_IDS,
  MESA_TIPS,
} from "@/features/help/mesa-tip-catalog";

afterEach(() => cleanup());

describe("mesa-tip-catalog", () => {
  it("exposes U1 tip ids plus U3 confirm-drawer and U4 fit-chip tips", () => {
    expect(MESA_TIP_IDS).toEqual(
      expect.arrayContaining([
        "operativa-proponer",
        "confirm-firmar",
        "operativa-recomendacion",
        "operativa-confirm-drawer",
        "operativa-fit-chip",
      ]),
    );
    expect(MESA_TIP_IDS).toHaveLength(5);
  });

  it("returns Spanish copy with optional links", () => {
    const propose = getMesaTip("operativa-proponer");
    expect(propose.title).toMatch(/Proponer F3/i);
    expect(propose.body.length).toBeGreaterThan(40);
    expect(propose.linkTo).toBe("/confirm");

    const confirm = MESA_TIPS["confirm-firmar"];
    expect(confirm.body).toMatch(/firmas/i);
    expect(confirm.body).toMatch(/Nunca/i);

    const reco = MESA_TIPS["operativa-recomendacion"];
    expect(reco.linkTo).toBe("/trading");

    const drawer = MESA_TIPS["operativa-confirm-drawer"];
    expect(drawer.body).toMatch(/panel/i);
    expect(drawer.linkTo).toBe("/confirm");

    const fit = MESA_TIPS["operativa-fit-chip"];
    expect(fit.body).toMatch(/Fit/i);
    expect(fit.body).toMatch(/PASS/i);
  });
});

describe("MesaTipButton", () => {
  it("opens a dialog with the tip title and body", () => {
    render(
      <MemoryRouter>
        <MesaTipButton tip="confirm-firmar" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("mesa-tip-confirm-firmar"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Firmar en Confirmar")).toBeTruthy();
    expect(screen.getByText(/Nunca se envían órdenes solas/i)).toBeTruthy();
  });
});
