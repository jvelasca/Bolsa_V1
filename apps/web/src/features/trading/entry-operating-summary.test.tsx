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
});
