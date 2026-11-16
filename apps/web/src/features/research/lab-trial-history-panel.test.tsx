/**
 * R7 — historial de experimentos del LAB (`lab-trial-history-panel`).
 *
 * Lo que debe morder:
 *   - un hueco (métrica o evidencia ausente) se declara `Sin dato todavía` y
 *     NUNCA se colapsa a `0` ni a `—`: `UNKNOWN ≠ 0`;
 *   - la evidencia lab presente muestra su modo (hold-out/WF/CPCV);
 *   - filtros, orden y selección avisan al contenedor (la URL la escribe él);
 *   - el vacío no es un error: explica y ofrece la puerta para probar.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §8 (R7)
 */

import { MemoryRouter } from "react-router-dom";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ResearchTrialDto } from "@bolsa/shared";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
import {
  LabTrialHistoryPanel,
  parseTrialPage,
  parseTrialSort,
  type LabHistoryFilters,
} from "@/features/research/lab-trial-history-panel";

afterEach(() => cleanup());

const FILTERS: LabHistoryFilters = {
  instrumentId: "",
  proposedBy: "",
  presetKey: "",
  sort: "created_at",
  page: 0,
  pageSize: 20,
};

function trial(partial: Partial<ResearchTrialDto> = {}): ResearchTrialDto {
  return {
    id: "trial-1",
    instrumentId: "inst-1",
    createdAt: "2026-11-10T10:00:00Z",
    isMetrics: {},
    params: {},
    proposedBy: "human",
    kContribution: 3,
    ...partial,
  };
}

type PanelProps = Parameters<typeof LabTrialHistoryPanel>[0];

function setup(overrides: Partial<PanelProps> = {}) {
  const props: PanelProps = {
    instruments: [
      { id: "inst-1", symbol: "ACA" },
      { id: "inst-2", symbol: "IBE" },
    ],
    filters: FILTERS,
    trials: [],
    total: 0,
    isLoading: false,
    isError: false,
    selectedTrialId: null,
    symbolById: new Map([
      ["inst-1", "ACA"],
      ["inst-2", "IBE"],
    ]),
    onFilterChange: vi.fn(),
    onSortChange: vi.fn(),
    onPageChange: vi.fn(),
    onSelectTrial: vi.fn(),
    ...overrides,
  };
  render(
    <MemoryRouter>
      <LabTrialHistoryPanel {...props} />
    </MemoryRouter>,
  );
  return props;
}

describe("LabTrialHistoryPanel · ausencia declarada", () => {
  it("declara el hueco de métricas y evidencia sin inventar 0 ni —", () => {
    setup({ trials: [trial()], total: 1 });

    // Configuración, Resultado (PnL), Calidad (Sharpe) y Evidencia sin medir.
    expect(screen.getAllByText(ABSENT_DATA_NOT_MEASURED)).toHaveLength(4);
    expect(screen.queryByText("0,00")).toBeNull();
    expect(screen.queryByText("—")).toBeNull();
  });

  it("muestra la evidencia del laboratorio cuando existe", () => {
    setup({
      trials: [
        trial({
          presetKey: "sma-20",
          isMetrics: { totalReturnPct: 4.5, sharpeRatio: 1.2 },
          blocks: {
            oosMetrics: { score: 3.4 },
          },
        }),
      ],
      total: 1,
    });

    expect(screen.getByText("Hold-out")).toBeTruthy();
    expect(screen.queryByText(ABSENT_DATA_NOT_MEASURED)).toBeNull();
  });

  it("el vacío explica y ofrece la puerta, y no finge un error", () => {
    setup();

    expect(
      screen.getByText("No hay experimentos con estos filtros."),
    ).toBeTruthy();
    const link = screen.getByRole("link", {
      name: "Ir a Probar estrategia",
    });
    expect(link.getAttribute("href")).toBe("/backtests?tab=run");
    expect(screen.queryByText(/No se pudo cargar el historial/i)).toBeNull();
  });
});

describe("LabTrialHistoryPanel · filtros y selección", () => {
  it("avisa al contenedor al cambiar instrumento y orden", () => {
    const props = setup();

    fireEvent.change(screen.getAllByRole("combobox")[0]!, {
      target: { value: "inst-2" },
    });
    expect(props.onFilterChange).toHaveBeenCalledWith({
      instrumentId: "inst-2",
    });

    fireEvent.change(screen.getAllByRole("combobox")[1]!, {
      target: { value: "sharpe" },
    });
    expect(props.onSortChange).toHaveBeenCalledWith("sharpe");
  });

  it("selecciona el experimento por su fila", () => {
    const props = setup({
      trials: [trial({ id: "trial-9" })],
      total: 1,
    });

    fireEvent.click(screen.getAllByText("ACA").at(-1)!);
    expect(props.onSelectTrial).toHaveBeenCalledWith("trial-9");
  });
});

describe("parseTrialSort / parseTrialPage", () => {
  it("normaliza sorts y páginas inválidas sin lanzar", () => {
    expect(parseTrialSort("sharpe")).toBe("sharpe");
    expect(parseTrialSort("nope")).toBe("created_at");
    expect(parseTrialSort(null)).toBe("created_at");
    expect(parseTrialPage("3")).toBe(3);
    expect(parseTrialPage("0")).toBe(0);
    expect(parseTrialPage("-2")).toBe(0);
    expect(parseTrialPage("abc")).toBe(0);
  });
});
