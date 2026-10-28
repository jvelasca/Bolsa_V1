/**
 * P1-06 — cartera caída ≠ «sin posiciones ni stops».
 *
 * Falsable: con `positions = portfolio?.positions ?? []` y `open === 0`, el fallo
 * de `/api/portfolio` se pintaba como «Sin posiciones abiertas — no hay stop que
 * confirmar», una afirmación de seguridad sobre un dato que no se leyó.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { PortfolioSummaryDto } from "@bolsa/shared";
import { MesaProteccionKpi } from "@/features/mesa/mesa-proteccion-kpi";
import { MesaPositionsSummary } from "@/features/mesa/mesa-positions-summary";
import { MesaLibroPanel } from "@/features/mesa/mesa-libro-panel";

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (selector: (s: { items: unknown[] }) => unknown) =>
    selector({ items: [] }),
}));

vi.mock("@/features/trading/use-pending-orders", () => ({
  usePendingOrders: () => ({ pendingOrders: [], isError: false }),
}));

vi.mock("@/features/operations/no-trade-session-button", () => ({
  NoTradeSessionButton: () => null,
}));

vi.mock("@/features/trading/operations-panel", () => ({
  OperationsPanel: () => <div data-testid="operations-panel-stub" />,
}));

const kpi = { protected: 0, open: 0, discrepancies: 0, pct: null };

afterEach(cleanup);

describe("Mesa · Protección con la cartera caída", () => {
  it("declara el hueco y nunca la frase de seguridad", () => {
    render(<MesaProteccionKpi kpi={kpi} absenceState="error" />);

    expect(screen.getByTestId("mesa-proteccion-unavailable")).toHaveTextContent(
      "No disponible",
    );
    expect(
      screen.getByText(/no se pudo leer la cartera; no hay recuento de stops/),
    ).toBeTruthy();
    expect(
      screen.queryByText(/Sin posiciones abiertas — no hay stop que confirmar/),
    ).toBeNull();
  });

  it("mientras carga tampoco afirma que no hay stops", () => {
    render(<MesaProteccionKpi kpi={kpi} absenceState="loading" />);

    expect(
      screen.queryByText(/Sin posiciones abiertas — no hay stop que confirmar/),
    ).toBeNull();
    expect(screen.getByText(/Cargando la cartera/)).toBeTruthy();
  });

  it("con la cartera leída y cero posiciones sí declara el cero medido", () => {
    render(<MesaProteccionKpi kpi={kpi} absenceState="empty" />);

    expect(
      screen.getByText(/Sin posiciones abiertas — no hay stop que confirmar/),
    ).toBeTruthy();
  });

  it("el Libro propaga el estado al KPI compacto", () => {
    render(
      <MemoryRouter>
        <MesaLibroPanel
          summary={null}
          protectionKpi={kpi}
          protectionState="error"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("mesa-proteccion-absence")).toHaveTextContent(
      "No disponible",
    );
  });

  it("el KPI compacto no pinta 0 / 0 sin dato", () => {
    render(<MesaProteccionKpi kpi={kpi} compact absenceState="error" />);
    expect(screen.queryByText("0")).toBeNull();
  });
});

describe("Mesa · Posiciones con la cartera caída", () => {
  it("declara «No disponible» y no «Sin posiciones»", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <MesaPositionsSummary
            positions={[]}
            protectPlanByInstrument={new Map()}
            studiesByInstrument={new Map()}
            studiesByDecisionId={new Map()}
            portfolioState="error"
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByTestId("mesa-positions-absence")).toHaveTextContent(
      "No disponible",
    );
    expect(screen.queryByText("Sin posiciones")).toBeNull();
  });

  it("con la cartera leída y vacía sí dice «Sin posiciones»", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <MesaPositionsSummary
            positions={[]}
            protectPlanByInstrument={new Map()}
            studiesByInstrument={new Map()}
            studiesByDecisionId={new Map()}
            portfolioState="empty"
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText("Sin posiciones")).toBeTruthy();
    expect(screen.queryByTestId("mesa-positions-absence")).toBeNull();
  });
});

describe("Mesa · P2-04 · cifras ausentes del Libro", () => {
  const summaryWithoutFigures = {
    positions: [],
    totalEquity: null,
    totalUnrealizedPnl: null,
  } as unknown as PortfolioSummaryDto;

  it("patrimonio y P&L sin medir se declaran como texto, nunca con el comodín —", () => {
    render(
      <MemoryRouter>
        <MesaLibroPanel summary={summaryWithoutFigures} />
      </MemoryRouter>,
    );

    const panel = screen.getByTestId("mesa-libro-panel");
    expect(panel).toHaveTextContent("Sin dato todavía");
    // El comodín prohibido es el nodo de texto suelto; la prosa del panel puede
    // usar la raya como puntuación (`— CTAs encolan Confirm`).
    expect(screen.queryByText("—")).toBeNull();
    expect(panel).not.toHaveTextContent("0.00");
  });

  it("UI5-04: el detalle no repite el rótulo «Posiciones» de la lista", () => {
    render(
      <MemoryRouter>
        <MesaLibroPanel summary={summaryWithoutFigures} />
      </MemoryRouter>,
    );

    // En `?view=posiciones` conviven la lista (`MesaPositionsSummary`) y este detalle:
    // si ambos se titulan «Posiciones», el mismo nombre designa dos secciones.
    const headings = screen.getAllByRole("heading", { level: 2 });
    expect(headings).toHaveLength(1);
    expect(headings[0]?.textContent).toBe("Plan y pendientes");
    expect(
      screen.queryByRole("heading", { level: 2, name: "Posiciones" }),
    ).toBeNull();
  });
});
