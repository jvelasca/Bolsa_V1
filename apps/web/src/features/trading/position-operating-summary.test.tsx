/**
 * V1.37 — resumen operativo diario (estado: acción, P&L, próximo evento, protección, asOf).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { buildOperationalTruth } from "@bolsa/shared";
import { PositionOperatingSummary } from "@/features/trading/position-operating-summary";

afterEach(() => cleanup());

function openPosition(overrides: Partial<PositionDto> = {}): PositionDto {
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
    ...overrides,
  };
}

describe("PositionOperatingSummary V1.39", () => {
  it("renders phrase, next event and protection for open position", () => {
    render(
      <PositionOperatingSummary
        position={openPosition()}
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-operating-summary")).toBeTruthy();
    expect(
      screen.getByTestId("position-operating-summary").getAttribute("data-cta"),
    ).toBe("maintain");
    expect(screen.getByTestId("position-operating-action").textContent).toBe(
      "Mantener",
    );
    expect(screen.getByTestId("position-operating-phrase").textContent).toMatch(
      /Mantén/,
    );
    expect(
      screen.getByTestId("position-operating-next-event").textContent,
    ).toBe("T1");
    expect(
      screen.getByTestId("position-operating-protection").textContent,
    ).toMatch(/Stop operativo vigente/);
    expect(screen.getByTestId("position-operating-pnl").textContent).toMatch(
      /\+2\.0%/,
    );
  });

  it("shows semantic disclaimer: stop operativo ≠ broker", () => {
    render(<PositionOperatingSummary position={openPosition()} />);
    expect(
      screen.getByText(/Stop operativo registrado ≠ orden stop de broker/i),
    ).toBeTruthy();
    expect(screen.getByText(/Confirm = firma/i)).toBeTruthy();
  });

  it("shows recon blocked copy on portfolio drift", () => {
    render(
      <PositionOperatingSummary
        position={openPosition()}
        portfolioReconStatus="drift"
      />,
    );
    expect(screen.getByTestId("position-operating-phrase").textContent).toMatch(
      /discrepancia/i,
    );
    expect(screen.getByTestId("position-operating-recon").textContent).toBe(
      "Operativa bloqueada",
    );
    expect(
      screen.getByTestId("position-operating-recon-detail").textContent,
    ).toMatch(/Reconciliación necesaria/i);
  });

  it("shows asOf from OperationalTruth", () => {
    const truth = buildOperationalTruth({
      position: openPosition(),
      portfolioReconStatus: "ok",
      asOf: "2026-08-31T08:15:00.000Z",
    });
    render(<PositionOperatingSummary truth={truth} />);
    expect(screen.getByTestId("position-operating-asof").textContent).toMatch(
      /2026-08-31 08:15 UTC/,
    );
  });

  it("returns null without operational trade plan", () => {
    const { container } = render(
      <PositionOperatingSummary
        position={openPosition({ operational: undefined })}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
