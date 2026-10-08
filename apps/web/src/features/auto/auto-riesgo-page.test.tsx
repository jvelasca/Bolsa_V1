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

  it("declara «Sin dato todavía» lo que AUTO no materializa (nunca 0)", () => {
    renderPage();
    for (const testId of [
      "auto-riesgo-open-risk",
      "auto-riesgo-max-loss",
      "auto-riesgo-position-risk",
      "auto-riesgo-daily-limit",
    ]) {
      expect(screen.getByTestId(testId).textContent).toBe("Sin dato todavía");
    }
  });

  it("sin datos medidos, todo se declara en vez de asumirse", () => {
    financialState.data = null;
    renderPage();
    expect(screen.getByTestId("auto-riesgo-state").textContent).toContain(
      "Sin dato todavía",
    );
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
