/**
 * P2 (sello 2) — regresión de la vista de auditoría por valor de ESTUDIO.
 *
 * Invariantes: un valor solo se rotula «Medido» con las dos mitades; un valor sin dato se
 * declara «Sin dato todavía» y pinta sus motivos (nunca un 0 de relleno); la superficie
 * declara `pointCitable = false`.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const AUDIT = {
  available: true,
  readOnly: true,
  serving: "PRECOMPUTED_ARTIFACT",
  window: "2026-04-01_2026-04-02",
  audit: {
    kind: "AUTO_ESTUDIO_AUDIT_V1",
    readOnly: true,
    pointCitable: false,
    pointCitableReason: "La banda de K=12 sorteos cruza el cero.",
    summary: {
      values: 2,
      measured: 1,
      unmeasured: 1,
      withPresetKey: 1,
      withoutPresetKey: 1,
    },
    values: [
      {
        symbol: "AAA",
        strategy: { presetKey: "sma_crossover", version: "ver-1" },
        why: { indicatorSpecs: null, recommendations: null },
        signal: {
          cycles: 3,
          linkedCycles: 1,
          unlinkedCycles: 2,
          duplicateCycles: 0,
          measuredCycles: 3,
          daysCovered: 2,
        },
        cycles: [
          {
            cycleId: "cyc-aaa-1",
            entryDay: "2026-04-01",
            exitDay: "2026-04-02",
            strategyPresetKey: "sma_crossover",
            strategyVersion: "ver-1",
            realizedR: 0.4,
          },
        ],
        resultR: {
          verdict: "MIXED",
          verdictReason: "preliminary_sample",
          evidenceQuality: "SUPPORTED",
          expectancyR: 0.4,
          hitRate: 0.55,
          realizedRTotal: 1.2,
          measuredCycles: 8,
          daysCovered: 2,
          measured: true,
          sampleFloor: 5,
        },
        money: {
          trades: 12,
          netReturnPct: 2.5,
          netReturnPctAtStress: 1.8,
          maxDrawdownPct: 3.0,
          hitRate: 0.6,
          committedCapital: 1000,
          measured: true,
          sampleFloor: 10,
        },
        measured: true,
        unmeasured: [],
      },
      {
        symbol: "BBB",
        strategy: { presetKey: null, version: null },
        why: { indicatorSpecs: null, recommendations: null },
        signal: {
          cycles: 1,
          linkedCycles: 0,
          unlinkedCycles: 1,
          duplicateCycles: 0,
          measuredCycles: 1,
          daysCovered: 1,
        },
        cycles: [],
        resultR: {
          verdict: "NOT_MEASURED",
          verdictReason: "insufficient_sample",
          evidenceQuality: "NOT_MEASURED",
          expectancyR: null,
          hitRate: null,
          realizedRTotal: null,
          measuredCycles: 2,
          daysCovered: 1,
          measured: false,
          sampleFloor: 5,
        },
        money: {
          trades: 0,
          netReturnPct: null,
          netReturnPctAtStress: null,
          maxDrawdownPct: null,
          hitRate: null,
          committedCapital: null,
          measured: false,
          sampleFloor: 10,
        },
        measured: false,
        unmeasured: [
          "R: 2 ciclos medidos < suelo 5 ⇒ ratios sin dato",
          "dinero: sin grupo financiero para el valor (Sin dato todavía)",
          "estrategia: el ciclo no declara presetKey (Sin dato todavía)",
        ],
      },
    ],
    notes: [],
  },
  notes: [],
};

vi.mock("@/lib/api", () => ({
  api: {
    getAutoEstudioAudit: vi.fn(async () => AUDIT),
  },
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
    accounts: [],
  }),
}));

import { api } from "@/lib/api";
import { EstudioAuditPanel } from "@/features/auto-monitor/estudio-audit-panel";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EstudioAuditPanel", () => {
  it("pinta por valor estrategia, señal, R y dinero con el estado de medición", async () => {
    renderWithClient(<EstudioAuditPanel />);

    await waitFor(() =>
      expect(screen.getByTestId("estudio-audit-panel")).toBeTruthy(),
    );

    const rows = screen.getAllByTestId("estudio-audit-value");
    const measured = rows.find(
      (row) => row.getAttribute("data-symbol") === "AAA",
    );
    const gap = rows.find((row) => row.getAttribute("data-symbol") === "BBB");

    expect(measured?.getAttribute("data-measure-state")).toBe("measured");
    expect(measured?.textContent).toContain("sma_crossover · ver-1");
    expect(measured?.textContent).toContain("+0.40R");
    expect(measured?.textContent).toContain("+2.50%");
    // La señal cuadra con la lista: los ciclos ENLAZABLES declarados == los que se listan.
    expect(
      measured?.querySelector('[data-testid="estudio-audit-value-signal"]')
        ?.textContent,
    ).toContain("1 de 3 ciclos enlazables");

    // El informe por valor enlaza con la operación canónica por `cycleId`.
    expect(
      measured
        ?.querySelector('[data-testid="estudio-audit-value-cycle-link"]')
        ?.getAttribute("href"),
    ).toBe("/auto/operar/operacion/cyc-aaa-1");
    expect(
      measured?.querySelector('[data-testid="estudio-audit-value-cycle"]')
        ?.textContent,
    ).toContain("2026-04-01 → 2026-04-02");

    expect(gap?.getAttribute("data-measure-state")).toBe("unmeasured");
    // Un valor sin ciclos enlazables declara el hueco (nunca se inventa un enlace).
    expect(
      gap?.querySelector('[data-testid="estudio-audit-value-signal"]')
        ?.textContent,
    ).toContain("0 de 1 ciclos enlazables");
    expect(
      gap?.querySelector('[data-testid="estudio-audit-value-cycles-gap"]'),
    ).toBeTruthy();
    expect(
      gap?.querySelector('[data-testid="estudio-audit-value-cycle-link"]'),
    ).toBeNull();
    // Un valor sin dato declara el hueco y sus motivos; nunca un 0 que finja medición.
    expect(gap?.textContent).toContain("Sin dato todavía");
    expect(gap?.textContent).not.toContain("0.00R");
    expect(
      gap?.querySelector('[data-testid="estudio-audit-value-gap"]')
        ?.textContent,
    ).toContain("sin grupo financiero");

    // La superficie declara que se cita la banda, no un punto.
    expect(
      screen.getByTestId("estudio-audit-point-citable").textContent,
    ).toContain("pointCitable = false");
    // Rotula la estrategia como la EJECUTADA (identidad del ciclo), no como «elegida».
    expect(screen.getByTestId("estudio-audit-panel").textContent).toContain(
      "Estrategia ejecutada (identidad del ciclo)",
    );
    expect(api.getAutoEstudioAudit).toHaveBeenCalled();
  });

  it("declara la ausencia honesta cuando no hay artefacto", async () => {
    vi.mocked(api.getAutoEstudioAudit).mockResolvedValueOnce({
      available: false,
      readOnly: true,
      serving: "PRECOMPUTED_ARTIFACT",
      window: null,
      audit: null,
      notes: ["no_artifacts"],
    });

    renderWithClient(<EstudioAuditPanel />);

    const card = await screen.findByTestId("estudio-audit-unavailable");
    expect(card.textContent).toContain("Sin dato todavía");
    expect(card.textContent).not.toContain("no_artifacts");
  });
});
