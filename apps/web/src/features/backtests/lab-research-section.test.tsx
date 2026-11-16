/**
 * R5 — salud e historial de experimentos dentro de `/backtests`.
 *
 * El Asesor ya no es la única puerta del LAB: este bloque monta la cobertura de
 * métricas (nivel 3, `TechnicalDetail`) y el historial con su detalle aquí.
 * Los filtros y la selección viven en la URL para que el deep-link conserve el
 * instrumento y el experimento.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { Mock } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LabResearchSection } from "@/features/backtests/lab-research-section";

vi.mock("@/lib/api", () => ({
  api: {
    getLabHealth: vi.fn(),
    getInstruments: vi.fn(),
    getResearchTrials: vi.fn(),
    getResearchTrial: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const getLabHealth = api.getLabHealth as unknown as Mock;
const getInstruments = api.getInstruments as unknown as Mock;
const getResearchTrials = api.getResearchTrials as unknown as Mock;
const getResearchTrial = api.getResearchTrial as unknown as Mock;

const health = {
  data: {
    totalTrials: 12,
    coverage: {
      sharpeRatio: { present: 10, total: 12, pct: 83.3 },
      sortinoRatio: { present: 8, total: 12, pct: 66.7 },
      calmarRatio: { present: 6, total: 12, pct: 50 },
    },
    zeroTradeCount: 1,
    zeroTradePct: 8.3,
    campaigns: [{ campaignId: "camp-1", trials: 12 }],
    campaignCount: 1,
    instrumentsWithTrials: 3,
    activeInstruments: 4,
    instrumentsWithoutTrials: 1,
    caveat: "Cobertura declarada, no imputada.",
  },
};

const trial = {
  id: "trial-1",
  instrumentId: "inst-1",
  params: {},
  isMetrics: { totalReturnPct: 4.2, sharpeRatio: 1.1 },
  proposedBy: "human",
  kContribution: 1,
  createdAt: "2026-11-10T10:00:00Z",
  presetKey: "sma_crossover",
};

function renderSection(
  entry = "/backtests?tab=history&instrumentId=inst-1&trialId=trial-1",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <LabResearchSection />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getLabHealth.mockResolvedValue(health);
  getInstruments.mockResolvedValue({
    data: [{ id: "inst-1", symbol: "ACA" }],
  });
  getResearchTrials.mockResolvedValue({ data: [trial], total: 1 });
  getResearchTrial.mockResolvedValue({ data: trial });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LabResearchSection", () => {
  it("monta la salud dentro del disclosure de nivel 3", async () => {
    renderSection();
    const technical = await screen.findByTestId(
      "lab-research-health-technical",
    );
    expect(technical.tagName).toBe("DETAILS");
    expect(technical.getAttribute("data-technical-detail")).toBe("true");
    expect(technical.textContent).toContain("Salud del laboratorio");
  });

  it("consulta el historial con el instrumento del deep-link", async () => {
    renderSection();
    await waitFor(() =>
      expect(getResearchTrials).toHaveBeenCalledWith(
        expect.objectContaining({
          instrumentId: "inst-1",
          limit: 30,
          offset: 0,
        }),
      ),
    );
  });

  it("pinta el experimento seleccionado y su detalle", async () => {
    renderSection();
    // El símbolo aparece en el filtro y en la fila del experimento.
    expect((await screen.findAllByText("ACA")).length).toBeGreaterThan(0);
    // El detalle del trial llega de `getResearchTrial` y no de la tabla.
    await waitFor(() =>
      expect(getResearchTrial).toHaveBeenCalledWith("trial-1"),
    );
    expect(await screen.findByText("Registro del experimento")).toBeTruthy();
  });
});
