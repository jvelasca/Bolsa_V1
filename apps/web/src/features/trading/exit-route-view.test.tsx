/**
 * V1.40 — ruta visual de salida (Exit Management UX).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { buildExitRouteView, buildOperationalTruth } from "@bolsa/shared";
import { ExitRouteView } from "@/features/trading/exit-route-view";
import { stubNarrowViewport, stubWideViewport } from "@/lib/test-viewport";

afterEach(() => cleanup());

function openPosition(): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 1020,
    unrealizedPnl: 20,
    unrealizedPnlPct: 2,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-1",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 105,
      target2: 110,
      unrealizedR: 0.4,
    },
  };
}

describe("ExitRouteView V1.40", () => {
  it("renders Entrada / Proteger / T1 / T2 nodes from OperationalTruth", () => {
    const position = openPosition();
    const truth = buildOperationalTruth({
      position,
      portfolioReconStatus: "ok",
    });
    render(<ExitRouteView truth={truth} position={position} />);
    expect(screen.getByTestId("exit-route-AAPL")).toBeTruthy();
    expect(
      screen.getByTestId("exit-route-AAPL-node-entry").textContent,
    ).toMatch(/Entrada/);
    expect(screen.getByTestId("exit-route-AAPL-node-stop").textContent).toMatch(
      /Proteger/,
    );
    expect(
      screen.getByTestId("exit-route-AAPL-node-target1").textContent,
    ).toMatch(/T1/);
    expect(
      screen.getByTestId("exit-route-AAPL-node-target2").textContent,
    ).toMatch(/T2/);
  });

  it("returns null without plan", () => {
    const position = openPosition({ operational: undefined });
    const { container } = render(
      <ExitRouteView position={position} truth={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("accepts pre-built route prop", () => {
    const position = openPosition();
    const truth = buildOperationalTruth({ position })!;
    const route = buildExitRouteView({ truth, position })!;
    render(<ExitRouteView route={route} testId="exit-route-custom" />);
    expect(screen.getByTestId("exit-route-custom")).toBeTruthy();
    expect(screen.getByTestId("exit-route-custom-node-stop")).toBeTruthy();
  });
});

describe("ExitRouteView V2.47 — móvil", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("en teléfono declara el ancho y cada nodo sigue mostrando rol, precio y R", () => {
    stubNarrowViewport();
    const position = openPosition();
    const truth = buildOperationalTruth({
      position,
      portfolioReconStatus: "ok",
    });
    render(<ExitRouteView truth={truth} position={position} />);

    const root = screen.getByTestId("exit-route-AAPL");
    expect(root.getAttribute("data-cabin-width")).toBe("narrow");

    const entryNode = screen.getByTestId("exit-route-AAPL-node-entry");
    expect(entryNode.textContent).toMatch(/Entrada/);
    // Precio, R y marca de alcanzado sobreviven al apilado (nada se oculta).
    expect(entryNode.textContent).toMatch(/100\.00/);
    expect(entryNode.textContent).toMatch(/\+0\.0R/);
    expect(entryNode.textContent).toMatch(/fill/);
    // El aviso de honestidad sube al suelo legible en teléfono.
    expect(screen.getByText(/Stop planificado/i).className).toMatch(
      /text-\[11px\]/,
    );
  });

  it("en escritorio mantiene el aviso en su tamaño de cabina", () => {
    stubWideViewport();
    const position = openPosition();
    const truth = buildOperationalTruth({ position })!;
    render(<ExitRouteView truth={truth} position={position} />);
    expect(
      screen.getByTestId("exit-route-AAPL").getAttribute("data-cabin-width"),
    ).toBe("wide");
    expect(screen.getByText(/Stop planificado/i).className).toMatch(
      /text-\[9px\]/,
    );
  });
});
