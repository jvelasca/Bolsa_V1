/**
 * V1.72 — Entry compact: Precio actual + Distancia solo con mark. Sin Ideal/Máxima.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { buildEntryOperatingTruth } from "@bolsa/shared";
import { EntryDecisionSurfaceCard } from "@/features/trading/entry-decision-surface-card";

afterEach(() => cleanup());

function study(): DecisionJournalStudyViewV1 {
  return {
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    hasOperationalPlan: true,
    tradePlanStatus: "ARMED",
    studiedAt: "2026-08-31T09:00:00.000Z",
    entry: 100,
    stop: 94,
    target1: 112,
    target2: 124,
    expectedRR: 2,
    riskAmount: 250,
    quantity: 10,
  } as DecisionJournalStudyViewV1;
}

describe("EntryCompactBody V1.72 mark + distance", () => {
  it("hides mark/distance without markPrice and never shows Ideal/Máxima", () => {
    const truth = buildEntryOperatingTruth({ study: study() });
    expect(truth).not.toBeNull();
    render(<EntryDecisionSurfaceCard truth={truth!} symbol="AAPL" />);
    expect(screen.queryByTestId("entry-decision-mark")).toBeNull();
    expect(screen.queryByTestId("entry-decision-distance")).toBeNull();
    expect(screen.queryByText(/Ideal/i)).toBeNull();
    expect(screen.queryByText(/Máxima/i)).toBeNull();
  });

  it("shows Precio actual and Distancia when mark is present", () => {
    const truth = buildEntryOperatingTruth({
      study: study(),
      markPrice: 101.5,
    });
    expect(truth?.plan.currentPrice).toBe(101.5);
    render(<EntryDecisionSurfaceCard truth={truth!} symbol="AAPL" />);
    expect(screen.getByTestId("entry-decision-mark").textContent).toMatch(
      /101/,
    );
    expect(screen.getByTestId("entry-decision-distance").textContent).toMatch(
      /\+1\.50/,
    );
  });
});
