/**
 * V1.40 — ruta visual de salida (Exit Management UX).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { buildExitRouteView, buildOperationalTruth } from "@bolsa/shared";
import { ExitRouteView } from "@/features/trading/exit-route-view";

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
