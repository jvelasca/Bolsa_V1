/**
 * Secciones AUTO (ADR-044) — estructura mínima.
 *
 * Comprueba que cada página de sección expone exactamente un `<h1>` (título de
 * página) y los enlaces/operaciones clave. El story panel y el hook del monitor
 * se mockean para aislar la estructura de la sección del I/O de red.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("@/features/auto-monitor/auto-operation-story-panel", () => ({
  AutoOperationStoryPanel: () => <div data-testid="story-stub" />,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view: {
      cycles: [
        { cycleId: "cyc-1", instrumentId: "AAPL" },
        { cycleId: "cyc-2", instrumentId: "MSFT" },
      ],
    },
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

import { AutoOperarPage } from "@/features/auto/auto-operar-page";
import { AutoOperacionPage } from "@/features/auto/auto-operacion-page";

afterEach(cleanup);

function singleH1() {
  return screen.queryAllByRole("heading", { level: 1 });
}

describe("AutoOperarPage", () => {
  it("expone un h1 y enlaza cada operación a la ruta canónica", () => {
    render(
      <MemoryRouter initialEntries={["/auto/operar"]}>
        <AutoOperarPage />
      </MemoryRouter>,
    );
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toBe("Operar");
    const links = screen.getAllByTestId("auto-operar-operation-link");
    expect(links).toHaveLength(2);
    expect(links[0]?.getAttribute("href")).toBe("/auto/operar/operacion/cyc-1");
    expect(screen.getByTestId("story-stub")).toBeTruthy();
  });
});

describe("AutoOperacionPage", () => {
  it("expone un h1 con el instrumento del ciclo seleccionado", () => {
    render(
      <MemoryRouter initialEntries={["/auto/operar/operacion/cyc-2"]}>
        <Routes>
          <Route
            path="/auto/operar/operacion/:cycleId"
            element={<AutoOperacionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toContain("MSFT");
  });
});
