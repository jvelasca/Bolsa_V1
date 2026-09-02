/**
 * V1.66 — DecisionExplainView cross-surface determinism (GP-V166-04).
 */

import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildDecisionExplainView,
  decisionExplainSurfaceSnapshot,
  formatTradePlanWhyNot,
  TRADE_PLAN_WHY_NOT_LABELS,
} from "./decision-explain-view.js";

const ASOF = "2026-09-02T08:00:00.000Z";

function armedStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "ART-DECISION-JOURNAL-STUDY",
    schemaVersion: "1.0.0",
    sessionId: "sess-1",
    decisionId: "dec-1",
    instrumentId: "inst-nvda",
    symbol: "NVDA",
    name: "NVIDIA",
    studiedAt: ASOF,
    ageMs: 0,
    period: "daily",
    timeframe: "D",
    opinion: "bullish",
    status: "in_progress",
    strength: 7.5,
    strengthBand: "strong",
    vigencia: "current",
    entry: 421.5,
    stop: 408,
    target1: 448,
    target2: 470,
    expectedRR: 2,
    riskAmount: 250,
    quantity: 10,
    initialRiskR: 1,
    positionValue: 4215,
    direction: "long",
    hasOperationalPlan: true,
    userThesis: null,
    decisionSummary: "Breakout con volumen en resistencia",
    analysisNotes: ["Breakout con volumen en resistencia"],
    trends: [
      {
        key: "short_term",
        label: "Corto plazo",
        value: "up",
        display: "Tendencia alcista CP",
      },
    ],
    consensus: { total: 5, bullish: 3, neutral: 1, bearish: 1 },
    indicators: {
      primary: "RSI > 50",
      confirmation: "MACD cruce alcista",
    },
    invalidation: ["Cierre < 408.00"],
    nextReviewAt: null,
    tradePlanStatus: "ARMED",
    action: null,
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

function fourSurfaces(input: Parameters<typeof buildDecisionExplainView>[0]) {
  return {
    mercado: buildDecisionExplainView(input),
    hoy: buildDecisionExplainView(input),
    journal: buildDecisionExplainView(input),
    operaciones: buildDecisionExplainView(input),
  };
}

describe("formatTradePlanWhyNot GP-V166-02", () => {
  it("maps all canonical TradePlanWhyNot codes", () => {
    for (const [code, label] of Object.entries(TRADE_PLAN_WHY_NOT_LABELS)) {
      expect(
        formatTradePlanWhyNot(code as keyof typeof TRADE_PLAN_WHY_NOT_LABELS),
      ).toBe(label);
    }
  });
});

describe("buildDecisionExplainView GP-V166-01", () => {
  it("composes thesis, signals, conditions, invalidators, policy and traceability", () => {
    const view = buildDecisionExplainView({
      study: armedStudy(),
      entriesBlocked: false,
      gateStatus: "PASS",
      whyNot: ["entry"],
    });

    expect(view.thesis).toEqual({
      opinion: "Alcista",
      strength: "Fuerte",
      summary: "Breakout con volumen en resistencia",
    });
    expect(view.signals.consensus).toEqual([
      "Alcista 60% (3)",
      "Neutral 20% (1)",
      "Bajista 20% (1)",
    ]);
    expect(view.signals.indicators).toEqual(["RSI > 50", "MACD cruce alcista"]);
    expect(view.signals.trends).toEqual(["Tendencia alcista CP"]);
    expect(view.conditions.phase).toBe("Preparada");
    expect(view.conditions.entryCondition).toBe("Esperar confirmación");
    expect(view.conditions.whyNot).toEqual([
      { code: "entry", label: "Entrada aún no lista" },
    ]);
    expect(view.invalidators).toEqual(["Cierre < 408.00"]);
    expect(view.policy).toEqual({
      entriesBlocked: false,
      gateStatus: "PASS",
      fitLabel: null,
      mandateLabel: null,
    });
    expect(view.traceability).toEqual({
      asOf: ASOF,
      source: "ART-DECISION-JOURNAL-STUDY",
      decisionId: "dec-1",
    });
  });

  it("includes fit/mandate policy labels when whyNot codes present", () => {
    const view = buildDecisionExplainView({
      study: armedStudy({ tradePlanStatus: "BLOCKED" }),
      whyNot: ["fit", "mandate"],
    });
    expect(view.policy.fitLabel).toBe("No encaja en la cartera");
    expect(view.policy.mandateLabel).toBe("Sin mandato abierto");
  });

  it("merges secondaryConditions into conditions.whyNot", () => {
    const view = buildDecisionExplainView({
      study: armedStudy(),
      secondaryConditions: [
        {
          kind: "trail_hint_not_applied",
          label: "Trail no aplicado · requiere Confirm",
        },
      ],
    });
    expect(view.conditions.whyNot).toContainEqual({
      code: "trail_hint_not_applied",
      label: "Trail no aplicado · requiere Confirm",
    });
  });
});

describe("sameDecisionExplainAcrossSurfaces GP-V166-04", () => {
  it("same fixture → same explain view on mercado/hoy/journal/operaciones", () => {
    const input = {
      study: armedStudy(),
      entriesBlocked: true,
      gateStatus: "VETO",
      whyNot: ["entry", "freshness"],
      phase: "bloqueada" as const,
    };
    const { mercado, hoy, journal, operaciones } = fourSurfaces(input);
    const snap = decisionExplainSurfaceSnapshot(mercado);
    expect(decisionExplainSurfaceSnapshot(hoy)).toEqual(snap);
    expect(decisionExplainSurfaceSnapshot(journal)).toEqual(snap);
    expect(decisionExplainSurfaceSnapshot(operaciones)).toEqual(snap);
    expect(snap).toMatchSnapshot();
  });
});
