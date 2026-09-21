/**
 * V1.38 — resumen operativo de entrada.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { buildEntryOperatingTruth } from "@bolsa/shared";
import { EntryOperatingSummary } from "@/features/trading/entry-operating-summary";
import { stubNarrowViewport, stubWideViewport } from "@/lib/test-viewport";

afterEach(() => cleanup());

function triggeredStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
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
    ...overrides,
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
      /Trigger confirmado/i,
    );
  });

  it("shows risk sizing from study", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    expect(screen.getByText(/Riesgo al stop/i)).toBeTruthy();
    expect(screen.getByText(/R\/R esperado/i)).toBeTruthy();
  });

  it("V2.47 — valor esperado neto medido se pinta con signo y moneda", () => {
    render(
      <EntryOperatingSummary
        study={triggeredStudy({
          expectedR: 0.8,
          netExpectedCurrency: 34,
        })}
      />,
    );
    expect(
      screen.getByTestId("entry-operating-expected-value").textContent,
    ).toBe("+34.00 € · R esperado 0.80");
    expect(screen.getByText(/Valor esperado neto/i)).toBeTruthy();
  });

  it("V2.47 — sin medición NO se pinta fila (jamás un 0 € inventado)", () => {
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    expect(screen.queryByTestId("entry-operating-expected-value")).toBeNull();
    expect(screen.queryByText(/Valor esperado neto/i)).toBeNull();
  });

  it("V2.47 — R medido sin coste cerrado publica solo el R (y declara el hueco)", () => {
    render(
      <EntryOperatingSummary
        study={triggeredStudy({ expectedR: 0.42, netExpectedCurrency: null })}
      />,
    );
    expect(
      screen.getByTestId("entry-operating-expected-value").textContent,
    ).toBe("R esperado 0.42");
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

describe("EntryOperatingSummary V2.47 — móvil", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("en teléfono declara el ancho y apila cada fila (misma información)", () => {
    stubNarrowViewport();
    render(
      <EntryOperatingSummary
        study={triggeredStudy({ expectedR: 0.8, netExpectedCurrency: 34 })}
      />,
    );
    const root = screen.getByTestId("entry-operating-summary");
    expect(root.getAttribute("data-cabin-width")).toBe("narrow");

    const actionRow = screen.getByTestId(
      "entry-operating-action",
    ).parentElement!;
    expect(actionRow.className).toMatch(/flex-col/);
    expect(actionRow.className).not.toMatch(/justify-between/);

    // Nada se oculta al apilar: etiqueta y valor siguen ahí.
    expect(screen.getByText("Riesgo al stop")).toBeTruthy();
    expect(screen.getByText("Valor esperado neto")).toBeTruthy();
    expect(
      screen.getByTestId("entry-operating-expected-value").textContent,
    ).toBe("+34.00 € · R esperado 0.80");
  });

  it("en escritorio mantiene la fila en una línea", () => {
    stubWideViewport();
    render(<EntryOperatingSummary study={triggeredStudy()} />);
    const root = screen.getByTestId("entry-operating-summary");
    expect(root.getAttribute("data-cabin-width")).toBe("wide");
    const actionRow = screen.getByTestId(
      "entry-operating-action",
    ).parentElement!;
    expect(actionRow.className).toMatch(/justify-between/);
    expect(actionRow.className).toMatch(/flex-wrap/);
  });
});
