import { describe, expect, it } from "vitest";
import {
  formatNextEventLabel,
  formatPositionDecisionActionLabel,
  formatPositionDecisionPhrase,
  formatProtectionLabel,
  isPrimaryPositionExitCta,
  positionOperatingCtaFromDecision,
  primaryPositionExitCta,
} from "./position-decision-copy.js";
import { buildPositionDecision } from "./position-decision.js";
import {
  buildPositionStateFromFill,
  type PositionStateV1,
} from "./position-state.js";
import type { TradePlanV1 } from "./trade-plan.js";

function openLong(): PositionStateV1 {
  const plan: TradePlanV1 = {
    decisionId: "dec-1",
    instrumentId: "AAPL",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 95,
    target1: 105,
    target2: 110,
  };
  const pos = buildPositionStateFromFill(plan, {
    price: 100,
    quantity: 10,
    filledAt: "2026-08-28T10:00:00Z",
  });
  if (!pos) throw new Error("expected position");
  return pos;
}

describe("position-decision-copy V1.36", () => {
  it("formats protection separately from next event", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
      portfolioReconStatus: "clean",
    });
    expect(d?.protection).toBe("ACTIVE");
    expect(d?.nextEvent).toBe("T1");
    expect(formatProtectionLabel(d!.protection)).toContain("operativo");
    expect(formatNextEventLabel(d!.nextEvent)).toBe("T1");
  });

  it("human phrase for HOLD with protection", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
      portfolioReconStatus: "clean",
    });
    const phrase = formatPositionDecisionPhrase(d!);
    expect(phrase).toMatch(/Mantén/);
    expect(phrase).toMatch(/Stop operativo/);
    expect(phrase).toMatch(/T1/);
  });

  it("human phrase for recon drift", () => {
    const d = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      portfolioReconStatus: "drift",
    });
    expect(formatPositionDecisionPhrase(d!)).toMatch(/discrepancia/i);
  });

  it("maps primary exit CTA from action", () => {
    const hold = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
    });
    expect(primaryPositionExitCta(hold!)).toBe("maintain");
    expect(isPrimaryPositionExitCta(hold!, "reduce")).toBe(false);

    const drift = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      portfolioReconStatus: "drift",
    });
    expect(primaryPositionExitCta(drift!)).toBe("review");
  });

  it("positionOperatingCtaFromDecision mirrors primary exit CTA", () => {
    const hold = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
    });
    expect(positionOperatingCtaFromDecision(hold!)).toEqual({
      kind: "maintain",
      label: "Mantener",
    });
    const drift = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      portfolioReconStatus: "drift",
    });
    expect(positionOperatingCtaFromDecision(drift!)).toEqual({
      kind: "review",
      label: "Revisar",
    });
  });

  it("formats action labels for surface copy", () => {
    const hold = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      templateId: "moderate",
    });
    expect(formatPositionDecisionActionLabel(hold!)).toBe("Mantener");
    const drift = buildPositionDecision({
      position: openLong(),
      signals: { markPrice: 102 },
      portfolioReconStatus: "drift",
    });
    expect(formatPositionDecisionActionLabel(drift!)).toBe("Revisar");
  });
});
