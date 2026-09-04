/**
 * V2.27 — Journal spine + RESULTADO honesty.
 */

import { describe, expect, it } from "vitest";
import {
  buildJournalSpineView,
  formatJournalMfeMaeLine,
  parseMfeMaeWire,
} from "./journal-spine-view.js";
import { buildTradeStory } from "./trade-story.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { PositionStateV1 } from "./position-state.js";
import type { MfeMaeV1 } from "./mfe-mae.js";

const INST = "inst-aapl";

function baseStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "sess-1",
    decisionId: "dec-1",
    instrumentId: INST,
    symbol: "AAPL",
    name: "Apple",
    studiedAt: "2026-09-02T08:00:00.000Z",
    ageMs: 0,
    period: "daily",
    timeframe: "1d",
    opinion: "bullish",
    status: "in_progress",
    strength: 7,
    strengthBand: "strong",
    vigencia: "current",
    entry: 184.2,
    stop: 176.8,
    target1: 195,
    target2: 205,
    expectedRR: 1.5,
    riskAmount: 400,
    quantity: 62,
    initialRiskR: 1,
    positionValue: 11420,
    direction: "long",
    hasOperationalPlan: true,
    userThesis: null,
    decisionSummary: "Tendencia alcista",
    analysisNotes: ["Tendencia alcista"],
    trends: [],
    consensus: { bullish: 1, bearish: 0, neutral: 0, total: 1 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "TRIGGERED",
    action: "buy",
    mfeMae: null,
    learningVerdict: null,
    ...overrides,
  };
}

describe("parseMfeMaeWire / formatJournalMfeMaeLine", () => {
  it("parses advisory wire and abs MAE (no signed mark mix)", () => {
    const parsed = parseMfeMaeWire({
      status: "favorable",
      mfeR: 1.8,
      maeR: -0.2,
      currentR: 0.5,
      why: ["peak_from_bars", "mfe_ge_1_5r"],
      source: "bars",
    });
    expect(parsed?.maeR).toBe(0.2);
    expect(parsed?.mfeR).toBe(1.8);
    expect(formatJournalMfeMaeLine(parsed!)).toContain("MFE 1.8R");
    expect(formatJournalMfeMaeLine(parsed!)).toContain("MAE 0.2R");
  });
});

describe("buildJournalSpineView V2.27", () => {
  it("tesis-only: TESIS+DECISIÓN known, later pending; no Final R from returnPct", () => {
    const study = baseStudy({
      hasOperationalPlan: false,
      entry: null,
      stop: null,
      initialRiskR: null,
      // Must never become Final R
      learningVerdict: "hit",
    });
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
    });
    const spine = buildJournalSpineView({ study, tradeStory: story });
    const byId = Object.fromEntries(spine.steps.map((s) => [s.id, s]));
    expect(byId.tesis?.state).toBe("done");
    expect(byId.decision?.state).toBe("current");
    expect(byId.entrada?.state).toBe("pending");
    expect(byId.t1?.state).toBe("pending");
    expect(spine.result.finalR).toBeNull();
    expect(spine.result.learningVerdict).toBe("hit");
  });

  it("fill without T1: entrada+riesgo current-ish; T1 pending (plan levels ≠ achieved)", () => {
    const study = baseStudy({ initialRiskR: 1 });
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      fills: [
        {
          price: 184.2,
          quantity: 62,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-1",
        },
      ],
    });
    const spine = buildJournalSpineView({ study, tradeStory: story });
    const byId = Object.fromEntries(spine.steps.map((s) => [s.id, s]));
    expect(byId.entrada?.state).toBe("done");
    expect(byId.riesgo?.state).toBe("current");
    expect(byId.t1?.state).toBe("pending");
    expect(byId.t2?.state).toBe("pending");
    expect(spine.result.initialRiskR).toBe(1);
  });

  it("T1 stamped marks T1; trailing hint alone does not mark TRAILING", () => {
    const study = baseStudy();
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      fills: [
        {
          price: 184.2,
          quantity: 62,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-1",
        },
      ],
      facts: [{ kind: "t1", asOf: "2026-09-06T10:00:00.000Z" }],
    });
    expect(story.events.some((e) => e.kind === "trailing_applied")).toBe(false);
    const spine = buildJournalSpineView({ study, tradeStory: story });
    const byId = Object.fromEntries(spine.steps.map((s) => [s.id, s]));
    expect(byId.t1?.state).toBe("current");
    expect(byId.trailing?.state).toBe("pending");
  });

  it("trailing_applied stamps TRAILING", () => {
    const study = baseStudy();
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      fills: [
        {
          price: 184.2,
          quantity: 62,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-1",
        },
      ],
      facts: [
        { kind: "t1", asOf: "2026-09-06T10:00:00.000Z" },
        { kind: "trailing_applied", asOf: "2026-09-07T11:00:00.000Z" },
      ],
    });
    const spine = buildJournalSpineView({ study, tradeStory: story });
    const byId = Object.fromEntries(spine.steps.map((s) => [s.id, s]));
    expect(byId.trailing?.state).toBe("current");
  });

  it("cierre + MFE/MAE: RESULTADO current; Final R only from PositionState CLOSED", () => {
    const mfeMae: MfeMaeV1 = {
      status: "favorable",
      mfeR: 2.1,
      maeR: 0.3,
      currentR: 1.5,
      why: ["peak_from_bars", "mfe_ge_1_5r"],
      source: "bars",
    };
    const study = baseStudy({
      status: "closed",
      mfeMae,
      learningVerdict: "hit",
      initialRiskR: 1,
    });
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      fills: [
        {
          price: 184.2,
          quantity: 62,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-1",
        },
      ],
      facts: [{ kind: "cierre", asOf: "2026-09-10T16:00:00.000Z" }],
    });

    // Without PositionState: realized/final stay null (honesty).
    const openSpine = buildJournalSpineView({
      study,
      tradeStory: story,
      positionState: null,
    });
    expect(openSpine.result.mfeMae?.mfeR).toBe(2.1);
    expect(openSpine.result.realizedR).toBeNull();
    expect(openSpine.result.finalR).toBeNull();
    expect(openSpine.steps.find((s) => s.id === "resultado")?.state).toBe(
      "current",
    );

    const closedPs: Pick<
      PositionStateV1,
      "realizedR" | "status" | "initialRisk"
    > = {
      realizedR: 1.4,
      status: "CLOSED",
      initialRisk: 5,
    };
    const closedSpine = buildJournalSpineView({
      study,
      tradeStory: story,
      positionState: closedPs,
    });
    expect(closedSpine.result.realizedR).toBe(1.4);
    expect(closedSpine.result.finalR).toBe(1.4);
  });

  it("returnPct must never become Final R (learning verdict separate)", () => {
    const study = baseStudy({
      status: "closed",
      learningVerdict: "miss",
      initialRiskR: 1,
    });
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      facts: [{ kind: "cierre", asOf: "2026-09-10T16:00:00.000Z" }],
    });
    const spine = buildJournalSpineView({ study, tradeStory: story });
    expect(spine.result.finalR).toBeNull();
    expect(spine.result.learningVerdict).toBe("miss");
  });

  it("T2 without T1 stamp → T1 unknown gap", () => {
    const study = baseStudy();
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: study.decisionId,
      study,
      fills: [
        {
          price: 184.2,
          quantity: 62,
          filledAt: "2026-09-05T18:00:00.000Z",
          positionId: "pos-1",
        },
      ],
      facts: [{ kind: "t2", asOf: "2026-09-08T10:00:00.000Z" }],
    });
    const spine = buildJournalSpineView({ study, tradeStory: story });
    const byId = Object.fromEntries(spine.steps.map((s) => [s.id, s]));
    expect(byId.t1?.state).toBe("unknown");
    expect(byId.t2?.state).toBe("current");
  });
});
