/**
 * R7 — detalle del experimento del LAB (`lab-trial-detail-panel`).
 *
 * Lo que debe morder:
 *   - sin selección no se inventa un registro: se pide elegir uno;
 *   - un experimento sin prueba vinculada declara su origen, no un enlace roto;
 *   - con `backtestRunId` el enlace abre el resultado en el LAB (`/backtests`);
 *   - los parámetros quedan en nivel 3: no se vierten en primer nivel.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §6 y §8 (R5/R7)
 */

import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ResearchTrialDto } from "@bolsa/shared";
import { LabTrialDetailPanel } from "@/features/research/lab-trial-detail-panel";

afterEach(() => cleanup());

function trial(partial: Partial<ResearchTrialDto> = {}): ResearchTrialDto {
  return {
    id: "trial-1",
    instrumentId: "inst-1",
    createdAt: "2026-11-10T10:00:00Z",
    isMetrics: {},
    params: { fast: 20, slow: 50 },
    proposedBy: "human",
    kContribution: 3,
    ...partial,
  };
}

function renderPanel(
  overrides: Partial<Parameters<typeof LabTrialDetailPanel>[0]> = {},
) {
  return render(
    <MemoryRouter>
      <LabTrialDetailPanel
        selectedTrialId={null}
        isLoading={false}
        selected={undefined}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

describe("LabTrialDetailPanel", () => {
  it("sin selección pide elegir un experimento (no inventa detalle)", () => {
    renderPanel();

    expect(
      screen.getByText("Selecciona un experimento en la tabla."),
    ).toBeTruthy();
  });

  it("declara el origen optimizador cuando no hay prueba vinculada", () => {
    renderPanel({
      selectedTrialId: "trial-1",
      selected: trial({ optimizationRunId: "opt-1" }),
    });

    expect(
      screen.getByText("Origen optimizador — sin prueba vinculada."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: "Abrir análisis de la prueba" }),
    ).toBeNull();
  });

  it("enlaza el resultado del LAB cuando hay backtestRunId", () => {
    renderPanel({
      selectedTrialId: "trial-1",
      selected: trial({ backtestRunId: "run-7" }),
    });

    const link = screen.getByRole("link", {
      name: "Abrir análisis de la prueba",
    });
    expect(link.getAttribute("href")).toBe("/backtests?tab=run&runId=run-7");
  });

  it("mantiene los parámetros dentro del detalle técnico", () => {
    renderPanel({
      selectedTrialId: "trial-1",
      selected: trial({ backtestRunId: "run-7" }),
    });

    // Nivel 3: «Parámetros» solo vive dentro del disclosure de detalle técnico.
    const detail = screen.getByTestId("research-trial-params-technical");
    expect(detail.getAttribute("data-technical-detail")).toBe("true");
    expect(within(detail).getByText("Parámetros")).toBeTruthy();
    expect(within(detail).getByText("Detalle técnico")).toBeTruthy();
  });
});
