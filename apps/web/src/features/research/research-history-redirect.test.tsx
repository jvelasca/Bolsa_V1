/**
 * R5 · compatibilidad de la puerta única LAB.
 *
 * Los enlaces antiguos al detalle del experimento dentro del Asesor
 * (`/research?tab=history&trialId=…`) no pueden romperse ni duplicar el ledger:
 * se redirigen a `/backtests?tab=history` conservando instrumento y experimento.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §6 y §8 (R5/R7)
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResearchPage } from "@/features/research/research-page";

vi.mock("@/lib/api", () => ({
  api: {
    getLaboratoryResearchSummary: vi.fn(async () => ({
      data: {
        totalTrials: 0,
        totalK: 0,
        activeInstruments: 0,
        lastTrialAt: null,
        avgSharpe: null,
        avgProfitFactor: null,
        avgMaxDD: null,
        byInstrument: [],
        byPreset: [],
      },
    })),
  },
}));

afterEach(() => cleanup());

function Probe() {
  const location = useLocation();
  return <p data-testid="probe">{`${location.pathname}${location.search}`}</p>;
}

function renderAt(entry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/backtests" element={<Probe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResearchPage · deep-link legacy al LAB", () => {
  it("redirige conservando el experimento y el instrumento", () => {
    renderAt("/research?tab=history&trialId=trial-9&instrumentId=inst-3");

    expect(screen.getByTestId("probe").textContent).toBe(
      "/backtests?tab=history&trialId=trial-9&instrumentId=inst-3",
    );
    // No se monta el Asesor: el detalle ya no vive aquí.
    expect(screen.queryByRole("heading", { name: "Asesor" })).toBeNull();
  });

  it("redirige aunque el enlace antiguo no declare instrumento", () => {
    renderAt("/research?tab=dashboard&trialId=trial-9");

    expect(screen.getByTestId("probe").textContent).toBe(
      "/backtests?tab=history&trialId=trial-9",
    );
  });
});
