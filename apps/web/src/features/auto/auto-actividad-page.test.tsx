/**
 * AUTO · ACTIVIDAD — estructura y estados del centro de actividad.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

const monitorState = vi.hoisted(() => ({
  header: null as Record<string, unknown> | null,
  cycles: [] as Array<Record<string, unknown>>,
  isLoading: false,
  isError: false,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view:
      monitorState.header || monitorState.cycles.length > 0
        ? { header: monitorState.header, cycles: monitorState.cycles }
        : null,
    isLoading: monitorState.isLoading,
    isError: monitorState.isError,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

// P4 — el panel «Por qué AUTO no operó» tiene su propio test; aquí se aísla para no
// requerir QueryClientProvider ni las consultas de descubrimiento.
vi.mock("@/features/auto/auto-no-trade-panel", () => ({
  AutoNoTradePanel: () => <div data-testid="auto-no-trade-panel-stub" />,
}));

import { AutoActividadPage } from "@/features/auto/auto-actividad-page";

beforeEach(() => {
  monitorState.header = { lastDecisionAt: "2026-10-06T09:42:00Z" };
  monitorState.cycles = [
    {
      cycleId: "cyc-1",
      instrumentId: "AAPL",
      steps: [{ id: "ORDER", state: "reached", at: "2026-10-06T09:10:00Z" }],
    },
  ];
  monitorState.isLoading = false;
  monitorState.isError = false;
});

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/auto/actividad"]}>
      <AutoActividadPage />
    </MemoryRouter>,
  );
}

describe("AutoActividadPage", () => {
  it("expone un h1 y una única línea temporal con enlace a la operación", () => {
    renderPage();
    expect(screen.queryAllByRole("heading", { level: 1 })).toHaveLength(1);
    const entries = screen.getAllByTestId("auto-actividad-entry");
    expect(entries).toHaveLength(2);
    const link = screen.getByTestId("auto-actividad-operation-link");
    expect(link.getAttribute("href")).toBe("/auto/operar/operacion/cyc-1");
  });

  it("declara el vacío sin presentarlo como error", () => {
    monitorState.header = { lastDecisionAt: null };
    monitorState.cycles = [];
    renderPage();
    expect(screen.getByTestId("auto-actividad-empty")).toBeTruthy();
    expect(screen.queryByTestId("auto-actividad-error")).toBeNull();
  });

  it("el error se declara distinto del vacío", () => {
    monitorState.isError = true;
    monitorState.cycles = [];
    renderPage();
    expect(screen.getByTestId("auto-actividad-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-actividad-empty")).toBeNull();
  });

  it("la carga se declara", () => {
    monitorState.isLoading = true;
    monitorState.cycles = [];
    renderPage();
    expect(screen.getByTestId("auto-actividad-loading")).toBeTruthy();
  });
});
