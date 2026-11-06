/**
 * V1.17 — mesa position row + showRoute wiring.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import type { PositionDto } from "@bolsa/shared";
import {
  MesaPositionRow,
  mesaPositionShowsRoute,
} from "@/features/mesa/mesa-position-row";

vi.mock("@/lib/api", () => ({
  api: {
    getAccounts: vi.fn(async () => ({ data: [] })),
    getAccountSettings: vi.fn(async () => ({ data: null })),
    getPendingOrders: vi.fn(async () => ({ data: [] })),
    getLifecycleSnapshot: vi.fn(async () => ({
      data: {
        positionId: "p1",
        stage: "candidate",
        lineagePath: "trail",
        events: [],
        accounting: null,
      },
    })),
  },
}));

afterEach(() => cleanup());

function renderRow(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

function position(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-1",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 105,
    marketValue: 1050,
    unrealizedPnl: 50,
    unrealizedPnlPct: 5,
    ...overrides,
  };
}

describe("mesaPositionShowsRoute", () => {
  it("true when study has operational plan", () => {
    expect(
      mesaPositionShowsRoute(position(), { hasOperationalPlan: true } as never),
    ).toBe(true);
  });

  it("true when operational stop or target exists", () => {
    expect(
      mesaPositionShowsRoute(
        position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: 95,
            target1: null,
            target2: null,
            tradePlanId: "tp-1",
          },
        }),
      ),
    ).toBe(true);
  });

  it("false without plan or operational levels", () => {
    expect(mesaPositionShowsRoute(position())).toBe(false);
    expect(
      mesaPositionShowsRoute(
        position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: null,
            target1: null,
            target2: null,
            tradePlanId: "tp-1",
          },
        }),
      ),
    ).toBe(false);
  });
});

describe("MesaPositionRow showRoute", () => {
  it("renders position route panel when showRoute is true", () => {
    renderRow(
      <MesaPositionRow
        position={position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: 95,
            target1: 110,
            target2: null,
            tradePlanId: "tp-1",
          },
        })}
        study={{ hasOperationalPlan: true, stop: 95, target1: 110 } as never}
        showRoute
      />,
    );
    expect(screen.getByTestId("position-route-AAPL")).toBeTruthy();
  });

  it("hides route panel when showRoute is false", () => {
    renderRow(
      <MesaPositionRow
        position={position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: 95,
            target1: 110,
            target2: null,
            tradePlanId: "tp-1",
          },
        })}
        study={{ hasOperationalPlan: true, stop: 95, target1: 110 } as never}
      />,
    );
    expect(screen.queryByTestId("position-route-AAPL")).toBeNull();
  });
});

describe("MesaPositionRow P&L tone (P2-01)", () => {
  it("un P&L no medido declara el hueco y no se pinta como ganancia", () => {
    renderRow(
      <MesaPositionRow
        position={position({ unrealizedPnl: null, unrealizedPnlPct: null })}
      />,
    );
    const pnl = screen.getByTestId("mesa-position-pnl-AAPL");
    expect(pnl.textContent).toBe("Sin dato todavía");
    expect(pnl.dataset.tone).toBe("neutral");
    expect(pnl.className).not.toContain("emerald");
  });

  it("un cero medido es plano, no ganancia", () => {
    renderRow(<MesaPositionRow position={position({ unrealizedPnl: 0 })} />);
    const pnl = screen.getByTestId("mesa-position-pnl-AAPL");
    expect(pnl.dataset.tone).toBe("neutral");
    expect(pnl.className).not.toContain("emerald");
  });

  it("los valores medidos conservan su signo en el tono y en el importe", () => {
    renderRow(<MesaPositionRow position={position({ unrealizedPnl: 50 })} />);
    expect(screen.getByTestId("mesa-position-pnl-AAPL").dataset.tone).toBe(
      "positive",
    );

    cleanup();
    renderRow(<MesaPositionRow position={position({ unrealizedPnl: -50 })} />);
    const negative = screen.getByTestId("mesa-position-pnl-AAPL");
    expect(negative.dataset.tone).toBe("negative");
    expect(negative.textContent).toContain("-50");
  });
});

describe("MesaPositionRow mode badge (UI5-10)", () => {
  it("declara modo y canal junto al símbolo cuando hay evidencia", () => {
    renderRow(
      <MesaPositionRow
        position={position({
          operational: {
            status: "OPEN",
            direction: "long",
            currentStop: null,
            target1: null,
            target2: null,
            tradePlanId: "manual-2026-10-08-abc",
          },
        })}
      />,
    );
    const badge = screen.getByTestId("mesa-position-mode-AAPL");
    expect(badge.textContent).toBe("MANUAL · SIMULADO");
    expect(badge.dataset.mode).toBe("MANUAL");
    expect(badge.dataset.channel).toBe("SIMULADO");
  });

  it("sin evidencia no inventa el modo: «Sin dato todavía»", () => {
    renderRow(<MesaPositionRow position={position()} />);
    expect(screen.getByTestId("mesa-position-mode-AAPL").textContent).toBe(
      "Sin dato todavía",
    );
  });
});
