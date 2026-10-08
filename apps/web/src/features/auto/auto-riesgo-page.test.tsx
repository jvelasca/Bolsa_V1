/**
 * AUTO · RIESGO — primer nivel honesto y detalle técnico plegado (spec 3.0 §5).
 *
 * Comprueba que la cabecera plana no inventa cifras (lo no medido se declara), que el error se
 * distingue del vacío y que el detalle técnico vive plegado en su propio bloque.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
    accounts: [],
  }),
}));

const financialState = vi.hoisted(() => ({
  data: null as Record<string, unknown> | null,
  isLoading: false,
  isError: false,
}));

vi.mock("@/features/operational-console/use-financial-integrity", () => ({
  useFinancialIntegrity: () => ({
    data: financialState.data,
    isLoading: financialState.isLoading,
    isError: financialState.isError,
    error: financialState.isError ? new Error("boom") : null,
  }),
}));

import { AutoRiesgoPage } from "@/features/auto/auto-riesgo-page";

beforeEach(() => {
  financialState.data = {
    accountId: "acc-1",
    status: "clean",
    operationalState: "OK",
    portfolioStatus: "clean",
    fillLinkIssues: [],
    outboxDead: 0,
    slaBreached: false,
  };
  financialState.isLoading = false;
  financialState.isError = false;
});

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/auto/riesgo"]}>
      <AutoRiesgoPage />
    </MemoryRouter>,
  );
}

function countOccurrences(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

describe("AutoRiesgoPage", () => {
  it("expone un h1 y traduce el estado medido", () => {
    renderPage();
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByTestId("auto-riesgo-state").textContent).toContain(
      "Normal",
    );
    expect(screen.getByTestId("auto-riesgo-portfolio").textContent).toContain(
      "Cuadra",
    );
    expect(screen.getByTestId("auto-riesgo-fill-links").textContent).toContain(
      "Sin incidencias",
    );
  });

  it("abre el primer nivel con un veredicto humano (UI5-18)", () => {
    renderPage();
    expect(screen.getByTestId("auto-riesgo-verdict-label").textContent).toBe(
      "Controlado",
    );
  });

  it("sin lectura, el veredicto es «Sin dato todavía», nunca «Controlado»", () => {
    financialState.data = null;
    renderPage();
    expect(screen.getByTestId("auto-riesgo-verdict-label").textContent).toBe(
      "Sin dato todavía",
    );
  });

  it("declara una sola vez lo que AUTO no materializa (nunca 0, ni repite el hueco)", () => {
    renderPage();
    const limits = screen.getByTestId("auto-riesgo-limits").textContent ?? "";
    expect(limits).toContain("Sin dato todavía");
    expect(limits).not.toContain("no están disponibles");
    expect(limits).not.toContain("0");
    // Las cuatro filas con el mismo hueco se han retirado del primer nivel.
    expect(screen.queryByTestId("auto-riesgo-open-risk")).toBeNull();
    expect(screen.queryByTestId("auto-riesgo-max-loss")).toBeNull();
    expect(screen.queryByTestId("auto-riesgo-position-risk")).toBeNull();
    expect(screen.queryByTestId("auto-riesgo-daily-limit")).toBeNull();
  });

  it("sin datos medidos, todo se declara en vez de asumirse", () => {
    financialState.data = null;
    renderPage();
    // El hueco vive en el veredicto; los campos no repiten el rótulo como celdas vacías.
    expect(screen.getByTestId("auto-riesgo-verdict-label").textContent).toBe(
      "Sin dato todavía",
    );
    expect(screen.queryByTestId("auto-riesgo-state")).toBeNull();
    expect(screen.queryByTestId("auto-riesgo-portfolio")).toBeNull();
    expect(screen.queryByTestId("auto-riesgo-fill-links")).toBeNull();
  });

  it("con integridad desconocida, el primer nivel declara el hueco una sola vez (UI5-14, RT-03)", () => {
    financialState.data = null;
    renderPage();
    const firstLevel =
      screen.getByTestId("auto-riesgo-first-level").textContent ?? "";
    expect(
      countOccurrences(firstLevel, "Sin dato todavía"),
    ).toBeLessThanOrEqual(1);
    // El vocabulario prohibido no asoma por el h1 ni por su descripción.
    const page = screen.getByTestId("auto-riesgo-page").textContent ?? "";
    expect(page).not.toContain("NO MEDIDO");
  });

  it("el detalle técnico está plegado por defecto", () => {
    renderPage();
    const detail = screen.getByTestId("auto-riesgo-technical");
    expect(detail.tagName).toBe("DETAILS");
    expect((detail as HTMLDetailsElement).open).toBe(false);
  });

  it("el error se declara distinto de un dato ausente", () => {
    financialState.isError = true;
    financialState.data = null;
    renderPage();
    expect(screen.getByTestId("auto-riesgo-error")).toBeTruthy();
  });

  it("la carga se declara", () => {
    financialState.isLoading = true;
    financialState.data = null;
    renderPage();
    expect(screen.getByTestId("auto-riesgo-loading")).toBeTruthy();
  });
});
