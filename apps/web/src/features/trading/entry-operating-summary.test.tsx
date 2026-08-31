/**
 * V1.38 — resumen operativo de entrada.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { buildEntryOperatingTruth } from "@bolsa/shared";
import { EntryOperatingSummary } from "@/features/trading/entry-operating-summary";

afterEach(() => cleanup());

function triggeredStudy(): DecisionJournalStudyViewV1 {
  return {
    instrumentId: "inst-nvda",
    symbol: "NVDA",
    hasOperationalPlan: true,
    tradePlanStatus: "TRIGGERED",
    studiedAt: "2026-08-31T09:00:00.000Z",
    entry: 421.5,
    stop: 408,
    target1: 448,
    target2: 470,
    expectedRR: 2,
    riskAmount: 250,
    initialRiskR: 1,
    positionValue: 4215,
    quantity: 10,
  } as DecisionJournalStudyViewV1;
}

describe("EntryOperatingSummary V1.38", () => {
  it("renders disparada phase, phrase and unified CTA", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    expect(screen.getByTestId("entry-operating-summary")).toBeTruthy();
    expect(screen.getByTestId("entry-operating-phase").textContent).toBe(
      "Disparada",
    );
    expect(screen.getByTestId("entry-operating-trigger").textContent).toBe(
      "Trigger: Disparado",
    );
    expect(screen.getByTestId("entry-operating-action").textContent).toBe(
      "Revisar y confirmar",
    );
    expect(screen.getByTestId("entry-operating-phrase").textContent).toMatch(
      /Disparo confirmado/i,
    );
  });

  it("shows risk sizing from study", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    expect(screen.getByText(/Riesgo al stop/i)).toBeTruthy();
    expect(screen.getByText(/R\/R esperado/i)).toBeTruthy();
  });

  it("shows Ranking ≠ BUY disclaimer", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    expect(screen.getByText(/Ranking ≠ BUY/i)).toBeTruthy();
    expect(screen.getByText(/Confirm = firma/i)).toBeTruthy();
  });

  it("returns null without entry operating phase", () => {
    const { container } = render(
      <EntryOperatingSummary
        study={
          {
            instrumentId: "x",
            hasOperationalPlan: false,
            tradePlanStatus: "WATCH",
            studiedAt: "2026-08-31T09:00:00.000Z",
          } as DecisionJournalStudyViewV1
        }
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("accepts pre-built truth", () => {
    const truth = buildEntryOperatingTruth({ study: triggeredStudy() });
    render(<EntryOperatingSummary truth={truth} />);
    expect(screen.getByTestId("entry-operating-asof").textContent).toMatch(
      /2026-08-31 09:00 UTC/,
    );
  });

  it("entriesBlocked → Entradas bloqueadas", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} entriesBlocked />);
    expect(screen.getByTestId("entry-operating-action").textContent).toBe(
      "Entradas bloqueadas",
    );
    expect(screen.getByTestId("entry-operating-phrase").textContent).toMatch(
      /bloqueadas/i,
    );
  });

  it("orderPendingFill → ExecutionState in_flight copy (V1.42 F2)", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} orderPendingFill />);
    const root = screen.getByTestId("entry-operating-summary");
    expect(root.getAttribute("data-execution-lifecycle")).toBe("in_flight");
    expect(screen.getByTestId("entry-operating-execution").textContent).toMatch(
      /en vuelo/i,
    );
  });

  it("submitIntent send_attempted → UNKNOWN copy without Confirm (V1.42 F2b)", () => {
    render(
      <EntryOperatingSummary
        study={triggeredStudy()}
        submitIntent={{
          decisionId: "DEC-1",
          intentId: "INT-1",
          orderId: "ORD-1",
          accountId: "acc-1",
          phase: "send_attempted",
          venueOrderId: null,
          reason: "crash_before_venue_ack",
          venue: "paper",
          sendAttemptedAt: "2026-08-31T12:00:00.000Z",
          instrumentId: "inst-nvda",
        }}
      />,
    );
    const root = screen.getByTestId("entry-operating-summary");
    expect(root.getAttribute("data-execution-lifecycle")).toBe("unknown");
    expect(screen.getByTestId("entry-operating-execution").textContent).toMatch(
      /desconocida|no duplicar/i,
    );
  });
});
