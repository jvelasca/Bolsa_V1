/**
 * Secciones AUTO (ADR-044) — estructura mínima.
 *
 * Comprueba que cada página de sección expone exactamente un `<h1>` (título de
 * página) y los enlaces/operaciones clave. El story panel se mockea para aislar la
 * estructura de la sección del I/O de red; el monitor se controla desde `monitorState`
 * para ejercitar carga/error/vacío.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("@/features/auto-monitor/auto-operation-story-panel", () => ({
  AutoOperationStoryPanel: () => <div data-testid="story-stub" />,
}));

const monitorState = vi.hoisted(() => ({
  cycles: [] as Array<Record<string, unknown>>,
  isLoading: false,
  isError: false,
}));

vi.mock("@/features/auto-monitor/use-auto-operational-monitor", () => ({
  useAutoOperationalMonitor: () => ({
    view: { cycles: monitorState.cycles },
    isLoading: monitorState.isLoading,
    isError: monitorState.isError,
    isFetching: false,
    refetch: vi.fn(),
  }),
}));

import { AutoOperarPage } from "@/features/auto/auto-operar-page";
import { AutoOperacionPage } from "@/features/auto/auto-operacion-page";

const CYCLES = [
  {
    cycleId: "cyc-1",
    instrumentId: "AAPL",
    directionLabel: "Largo",
    statusLabel: "Precio aplicado",
    steps: [{ id: "SIGNAL", at: "2026-10-03T09:00:00Z" }],
  },
  {
    cycleId: "cyc-2",
    instrumentId: "MSFT",
    directionLabel: "Largo",
    statusLabel: "Orden anotada",
    steps: [{ id: "SIGNAL", at: "2026-10-04T09:00:00Z" }],
  },
  {
    cycleId: "cyc-3",
    instrumentId: "AAPL",
    directionLabel: "Corto",
    statusLabel: "Cerrada",
    steps: [{ id: "SIGNAL", at: "2026-10-05T09:00:00Z" }],
  },
];

beforeEach(() => {
  monitorState.cycles = CYCLES;
  monitorState.isLoading = false;
  monitorState.isError = false;
});

afterEach(cleanup);

function singleH1() {
  return screen.queryAllByRole("heading", { level: 1 });
}

function renderOperar() {
  return render(
    <MemoryRouter initialEntries={["/auto/operar"]}>
      <AutoOperarPage />
    </MemoryRouter>,
  );
}

describe("AutoOperarPage", () => {
  it("expone un h1 y enlaza cada operación a la ruta canónica", () => {
    renderOperar();
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toBe("Operar");
    const links = screen.getAllByTestId("auto-operar-operation-link");
    expect(links).toHaveLength(3);
    expect(
      links
        .find((l) => l.getAttribute("data-cycle-id") === "cyc-1")
        ?.getAttribute("href"),
    ).toBe("/auto/operar/operacion/cyc-1");
    // Una sola fuente de selección: la lista. La historia vive en su ruta canónica.
    expect(screen.queryByTestId("story-stub")).toBeNull();
  });

  it("identifica dos ciclos del mismo símbolo de forma distinguible", () => {
    renderOperar();
    const links = screen.getAllByTestId("auto-operar-operation-link");
    const aapl = links
      .filter((l) => l.textContent?.includes("AAPL"))
      .map((l) => l.textContent ?? "");
    expect(aapl).toHaveLength(2);
    // Mismo símbolo, distinta entrada → etiquetas humanas distintas (no `cycleId`).
    expect(aapl[0]).not.toBe(aapl[1]);
    expect(aapl[0]).toContain("03 oct");
    expect(aapl[1]).toContain("05 oct");
  });

  it("muestra el bloque Oportunidades como lanzadera a la Mesa", () => {
    renderOperar();
    expect(screen.getByTestId("auto-operar-opportunities")).toBeTruthy();
    expect(
      screen.getByTestId("auto-operar-opportunities-link").getAttribute("href"),
    ).toContain("oportunidades");
  });

  it("el error se declara distinto del vacío", () => {
    monitorState.isError = true;
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-error")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-empty")).toBeNull();
  });

  it("el vacío real sólo aparece sin carga ni error", () => {
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-empty")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-error")).toBeNull();
  });

  it("la carga se declara, no se presenta como vacío", () => {
    monitorState.isLoading = true;
    monitorState.cycles = [];
    renderOperar();
    expect(screen.getByTestId("auto-operar-loading")).toBeTruthy();
    expect(screen.queryByTestId("auto-operar-empty")).toBeNull();
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

  it("un cycleId inexistente se declara con el id pedido, sin inventar otro ciclo", () => {
    render(
      <MemoryRouter initialEntries={["/auto/operar/operacion/does-not-exist"]}>
        <Routes>
          <Route
            path="/auto/operar/operacion/:cycleId"
            element={<AutoOperacionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(singleH1()).toHaveLength(1);
    expect(singleH1()[0]?.textContent).toContain("does-not-exist");
    expect(singleH1()[0]?.textContent).not.toContain("AAPL");
    expect(singleH1()[0]?.textContent).not.toContain("MSFT");
  });
});
