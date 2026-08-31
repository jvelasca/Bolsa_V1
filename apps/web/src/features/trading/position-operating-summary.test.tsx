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
      /T1 alcanzado · Mantener/,
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

  it("orderPending → ExecutionState in_flight copy (V1.42 F2)", () => {
    render(
      <PositionOperatingSummary
        position={openPosition()}
        portfolioReconStatus="ok"
        orderPending
      />,
    );
    const root = screen.getByTestId("position-operating-summary");
    expect(root.getAttribute("data-execution-lifecycle")).toBe("in_flight");
    expect(root.getAttribute("data-execution-order")).toBe("pending");
    expect(
      screen.getByTestId("position-operating-execution").textContent,
    ).toMatch(/en vuelo/i);
  });

  it("submitIntent venue_bound → UNKNOWN copy from list facts (V1.42 F2b)", () => {
    render(
      <PositionOperatingSummary
        position={openPosition()}
        portfolioReconStatus="ok"
        submitIntent={{
          decisionId: "DEC-1",
          intentId: "INT-1",
          orderId: "ORD-1",
          accountId: "acc-1",
          phase: "venue_bound",
          venueOrderId: "v-1",
          reason: "crash_after_venue_ack",
          venue: "paper",
          sendAttemptedAt: "2026-08-31T12:00:00.000Z",
          instrumentId: "inst-aapl",
        }}
      />,
    );
    const root = screen.getByTestId("position-operating-summary");
    expect(root.getAttribute("data-execution-lifecycle")).toBe("unknown");
    expect(root.getAttribute("data-execution-order")).toBe("unknown");
    expect(
      screen.getByTestId("position-operating-execution").textContent,
    ).toMatch(/desconocida|no duplicar/i);
  });

  it("full_exit + protectionDiscrepancy → Salir + secondary (V1.42 F3 §A.8)", () => {
    render(
      <PositionOperatingSummary
        position={openPosition({
          lastPrice: 94,
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
            exitPlan: { suggestedAction: "full_exit" },
          },
        })}
        portfolioReconStatus="ok"
        protectionDiscrepancy
      />,
    );
    const root = screen.getByTestId("position-operating-summary");
    expect(root.getAttribute("data-cta")).toBe("exit");
    expect(screen.getByTestId("position-operating-action").textContent).toBe(
      "Salir",
    );
    expect(root.getAttribute("data-protection-discrepancy")).toBe("1");
    expect(
      screen.getByTestId("position-operating-secondary").textContent,
    ).toMatch(/protección discrepante/i);
  });
});
