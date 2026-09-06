/**
 * Tests — Ayuda Hoy + mesa operativa (fase pruebas v2.10.1).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";
import { HoyEnLaMesaBlock } from "@/features/help/hoy-en-la-mesa";
import {
  OperatingDeskAssetJourneyBlock,
  OperatingDeskBasicBlocks,
  OperatingDeskExpertDetails,
} from "@/features/help/operating-desk-help-blocks";
import {
  OPERATING_DESK_ASSET_JOURNEY,
  OPERATING_DESK_EXPERT,
  OPERATING_DESK_SUMMARY,
  OPERATING_DESK_SYNC,
} from "@/features/help/operating-desk-help";

afterEach(() => cleanup());

describe("help operating desk / Hoy", () => {
  it("HELP_CONTENT_AS_OF is 2026-09-07", () => {
    expect(HELP_CONTENT_AS_OF).toBe("2026-09-07");
    expect(OPERATING_DESK_SYNC.asOf).toBe(HELP_CONTENT_AS_OF);
    expect(OPERATING_DESK_SYNC.phase).toBe("pruebas");
    expect(OPERATING_DESK_SYNC.tipLabel).toBe("v2.10.1-beta");
  });

  it("Hoy en la mesa describes inbox → Mercado → Confirm", () => {
    render(
      <MemoryRouter>
        <HoyEnLaMesaBlock />
      </MemoryRouter>,
    );
    const text = screen.getByTestId("hoy-en-la-mesa").textContent ?? "";
    expect(text).toMatch(/inbox/i);
    expect(text).toMatch(/requiere atención/i);
    expect(text).toMatch(/Avanzado/i);
    expect(text).toMatch(/Mercado/i);
    expect(text).toMatch(/Ranking ≠ orden/i);
    expect(text).toMatch(/Confirm/i);
    expect(text).toMatch(/Calidad N\/100 ≠ BUY/i);
    expect(text).toMatch(/Trail = propuesta/i);
    expect(text).toMatch(/T1 alcanzado ≠ gestionado/i);
    expect(text).toMatch(/Entradas bloqueadas/i);
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

  it("asset journey covers Estudio → Confirm → stops", () => {
    render(
      <MemoryRouter>
        <OperatingDeskAssetJourneyBlock />
      </MemoryRouter>,
    );
    const text =
      screen.getByTestId("operating-desk-asset-journey").textContent ?? "";
    expect(text).toContain(OPERATING_DESK_ASSET_JOURNEY.title);
    expect(text).toMatch(/Pasar a lista Estudio/i);
    expect(text).toMatch(/Indicadores técnicos/i);
    expect(text).toMatch(/Análisis fundamental/i);
    expect(text).toMatch(/Firmar en Confirm/i);
    expect(text).toMatch(/Stop loss/i);
    expect(text).toMatch(/T1 \/ T2/i);
    expect(text).not.toMatch(/docs\/engineering/);
  });

  it("basic summary then expert details without dumping ADR paths", () => {
    render(
      <MemoryRouter>
        <OperatingDeskBasicBlocks />
        <OperatingDeskExpertDetails />
      </MemoryRouter>,
    );
    const summary =
      screen.getByTestId("operating-desk-summary").textContent ?? "";
    expect(summary).toContain(OPERATING_DESK_SUMMARY.title);
    expect(summary).toMatch(/fase de pruebas/i);
    expect(summary).toMatch(/Confirm/i);
    expect(summary).toMatch(/v2\.10\.1-beta/);
    expect(summary).not.toMatch(/docs\/engineering/);

    const expert =
      screen.getByTestId("operating-desk-expert").textContent ?? "";
    expect(expert).toContain(OPERATING_DESK_EXPERT.title);
    expect(expert).toMatch(/Daily Desk/i);
    expect(expert).toMatch(/misma CTA/i);
    expect(expert).toMatch(/LIVE VIRTUAL/i);
    expect(expert).not.toMatch(/traspaso-relevo/);
    expect(expert).not.toMatch(/CURRENT_SYSTEM/);
  });
});
