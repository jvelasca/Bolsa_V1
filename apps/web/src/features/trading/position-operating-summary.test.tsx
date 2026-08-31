/**
 * V1.36 — resumen operativo diario (frase + próximo evento + protección).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { PositionDto } from "@bolsa/shared";
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

describe("PositionOperatingSummary V1.36", () => {
  it("renders phrase, next event and protection for open position", () => {
    render(
      <PositionOperatingSummary
        position={openPosition()}
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-operating-summary")).toBeTruthy();
    expect(screen.getByTestId("position-operating-phrase").textContent).toMatch(
      /Mantén/,
    );
    expect(
      screen.getByTestId("position-operating-next-event").textContent,
    ).toBe("T1");
    expect(
      screen.getByTestId("position-operating-protection").textContent,
    ).toMatch(/Stop operativo vigente/);
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
    expect(screen.getByText("Bloqueada")).toBeTruthy();
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
