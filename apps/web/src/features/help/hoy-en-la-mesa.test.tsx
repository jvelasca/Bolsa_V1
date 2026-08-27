/**
 * Tests — Ayuda Hoy V1.23 (inbox · Mercado · Confirm).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";
import { HoyEnLaMesaBlock } from "@/features/help/hoy-en-la-mesa";

afterEach(() => cleanup());

describe("help Hoy V1.23", () => {
  it("HELP_CONTENT_AS_OF is 2026-08-27c", () => {
    expect(HELP_CONTENT_AS_OF).toBe("2026-08-27c");
  });

  it("Hoy en la mesa describes inbox → Mercado → Confirm", () => {
    render(
      <MemoryRouter>
        <HoyEnLaMesaBlock />
      </MemoryRouter>,
    );
    const text = screen.getByTestId("hoy-en-la-mesa").textContent ?? "";
    expect(text).toMatch(/inbox/i);
    expect(text).toMatch(/requiere acción/i);
    expect(text).toMatch(/Ver detalles/i);
    expect(text).toMatch(/Mercado/i);
    expect(text).toMatch(/Ranking ≠ orden/i);
    expect(text).toMatch(/Confirm/i);
    expect(text).toMatch(/Prioridad N\/100 ≠ BUY/i);
    expect(text).toMatch(/Trail = propuesta/i);
    expect(text).toMatch(/T1 alcanzado ≠ gestionado/i);
    expect(text).toMatch(/Estudio empty ≠ unavailable/i);
    expect(text).toMatch(/Asesor explica/i);
    expect(screen.getByRole("link", { name: "Hoy" })).toHaveAttribute(
      "href",
      "/mesa",
    );
    expect(screen.getByRole("link", { name: "Mercado" })).toHaveAttribute(
      "href",
      "/trading",
    );
    expect(screen.getByRole("link", { name: "/confirm" })).toHaveAttribute(
      "href",
      "/confirm",
    );
  });
});
