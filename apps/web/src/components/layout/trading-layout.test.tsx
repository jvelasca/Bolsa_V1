/**
 * Cascarón del Mercado: DECISIÓN maximizada ocupa el área completa (como Listas
 * u Operaciones) y, en ventana estrecha, es la única vista del panel.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { TradingLayout } from "@/components/layout/trading-layout";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { stubNarrowViewport, stubWideViewport } from "@/lib/test-viewport";

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: (
    sel: (s: {
      workspace: { layout: { listPanelSizePct: number } };
    }) => unknown,
  ) => sel({ workspace: { layout: { listPanelSizePct: 26 } } }),
}));

vi.mock("@/features/trading/lists-tab/use-chart-list-membership-sync", () => ({
  useChartListMembershipSync: () => undefined,
}));

vi.mock("@/features/trading/lists-tab/use-chart-visualization-sync", () => ({
  useChartVisualizationSync: () => undefined,
}));

vi.mock("@/features/trading/lists-tab/watchlist-panel", () => ({
  WatchlistPanel: () => <p>watchlist</p>,
}));

vi.mock("@/features/trading/charts-zone", () => ({
  ChartsZone: ({ children }: { children: ReactNode }) => (
    <p>charts-zone {children}</p>
  ),
}));

vi.mock("@/features/trading/operations-panel", () => ({
  OperationsPanel: () => <p>operations-panel</p>,
}));

vi.mock("@/features/trading/trading-health-strip", () => ({
  TradingHealthStrip: () => <p>health-strip</p>,
}));

vi.mock("@/features/trading/trading-operativa-panel", () => ({
  TradingOperativaPanel: ({ maximized }: { maximized?: boolean }) => (
    <div data-testid="operativa-panel" data-maximized={String(!!maximized)} />
  ),
}));

function renderLayout() {
  return render(
    <TradingLayout>
      <p>chart</p>
    </TradingLayout>,
  );
}

beforeEach(() => {
  stubWideViewport();
  useTradingLayoutStore.setState({
    listsOpen: true,
    chartsOpen: true,
    operationsOpen: true,
    operativaOpen: true,
    listsMaximized: false,
    chartsMaximized: false,
    operationsMaximized: false,
    operativaMaximized: false,
    namedLayoutId: "trader",
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TradingLayout — DECISIÓN maximizada", () => {
  it("monta solo el dock DECISIÓN y le pasa maximized al panel", () => {
    useTradingLayoutStore.setState({ operativaMaximized: true });
    renderLayout();

    expect(screen.getByTestId("operativa-panel").dataset.maximized).toBe(
      "true",
    );
    expect(screen.getByText("DECISIÓN")).toBeTruthy();
    expect(screen.getByTitle("Restaurar")).toBeTruthy();
    expect(screen.queryByText("Listas")).toBeNull();
    expect(screen.queryByText("Gráfico")).toBeNull();
    expect(screen.queryByText("Operaciones")).toBeNull();
    expect(screen.queryByText("health-strip")).toBeNull();
  });

  it("en dock normal el panel no se declara maximizado y ofrece Maximizar", () => {
    renderLayout();

    expect(screen.getByTestId("operativa-panel").dataset.maximized).toBe(
      "false",
    );
    expect(screen.getByText("Listas")).toBeTruthy();
    expect(screen.getByText("Gráfico")).toBeTruthy();
    const decisionZone = screen.getByText("DECISIÓN").closest("section");
    expect(decisionZone).toBeTruthy();
    expect(within(decisionZone!).getByTitle("Maximizar")).toBeTruthy();
    expect(screen.getByText("health-strip")).toBeTruthy();
  });
});

describe("TradingLayout — ventana estrecha (<768 px)", () => {
  it("DECISIÓN maximizada es una vista completa, sin dock oculto ni Maximizar", () => {
    stubNarrowViewport();
    useTradingLayoutStore.setState({ operativaMaximized: true });
    renderLayout();

    expect(screen.getByTestId("operativa-panel").dataset.maximized).toBe(
      "true",
    );
    expect(screen.getByText("DECISIÓN")).toBeTruthy();
    expect(screen.queryByTitle("Maximizar")).toBeNull();
    expect(screen.getByTitle("Cerrar")).toBeTruthy();
    expect(screen.queryByText("Listas")).toBeNull();
  });

  it("sin maximizar el móvil conserva Listas/Gráfico (DECISIÓN sigue siendo dock md+)", () => {
    stubNarrowViewport();
    renderLayout();

    expect(screen.getByText("health-strip")).toBeTruthy();
    expect(screen.getByText("Listas")).toBeTruthy();
    expect(screen.getByText("Gráfico")).toBeTruthy();
  });
});
