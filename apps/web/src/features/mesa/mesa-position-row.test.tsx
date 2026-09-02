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
