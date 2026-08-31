/**
 * V1.41.2 — matriz de honestidad operativa sobre proyecciones actuales.
 * No E2E browser. V1.42 F2: fill parcial / REJECTED vía ExecutionState.
 * Mercado cerrado / trailing autoridad siguen parked.
 */

import { describe, expect, it } from "vitest";
import type { PositionDto } from "../types.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import { buildDailyDeskInbox } from "./daily-desk.js";
import {
  buildEntryOperatingTruth,
  entryOperatingSurfaceSnapshot,
} from "./entry-operating-truth.js";
import {
  buildExecutionState,
  formatExecutionStateCopy,
  isOrderInFlight,
} from "./execution-state.js";
import {
  buildOperationalTruth,
  formatExecutionHintCopy,
  operationalTruthSurfaceSnapshot,
} from "./operational-truth.js";
import { buildPaperOrder, transitionPaperOrder } from "./paper-order.js";
import { buildPositionOperatingTruth } from "./position-operating-truth.js";

const ASOF = "2026-08-31T08:15:00.000Z";

function armedStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "decision_journal_study",
    schemaVersion: 1,
    sessionId: "sess-1",
    decisionId: "dec-1",
    instrumentId: "inst-nvda",
    symbol: "NVDA",
    name: "NVIDIA",
    studiedAt: ASOF,
    ageMs: 0,
    period: "swing",
    timeframe: "D",
    opinion: "bullish",
    status: "active",
    strength: 7.5,
    strengthBand: "high",
    vigencia: null,
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
    decisionSummary: "Breakout",
    analysisNotes: [],
    trends: [],
    consensus: { total: 0, bullish: 0, neutral: 0, bearish: 0 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "ARMED",
    action: null,
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

function aaplOpen(overrides: Partial<PositionDto> = {}): PositionDto {
  return {
    id: "p-aapl",
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
      tradePlanId: "tp-aapl",
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

function noBuy(label: string | undefined): void {
  expect((label ?? "").toUpperCase()).not.toContain("BUY");
  expect((label ?? "").toUpperCase()).not.toContain("COMPRAR");
}

describe("operationalHonestyScenarios V1.41.2", () => {
  it("1 WATCH / sin plan → EntryOperatingTruth null", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy({
        hasOperationalPlan: false,
        tradePlanStatus: "WATCH",
        entry: null,
        stop: null,
        target1: null,
        target2: null,
      }),
    });
    expect(truth).toBeNull();
  });

  it("2 PREPARADA (ARMED) → Preparar operación", () => {
    const truth = buildEntryOperatingTruth({ study: armedStudy(), asOf: ASOF });
    expect(truth?.phase).toBe("preparada");
    expect(truth?.primaryCta.label).toBe("Preparar operación");
    noBuy(truth?.primaryCta.label);
  });

  it("3 DISPARADA (TRIGGERED) → Revisar y confirmar; no COMPRAR", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy({ tradePlanStatus: "TRIGGERED" }),
      asOf: ASOF,
    });
    expect(truth?.phase).toBe("disparada");
    expect(truth?.primaryCta.label).toBe("Revisar y confirmar");
    noBuy(truth?.primaryCta.label);
  });

  it("4 PROPUESTA (inConfirmQueue)", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy({ tradePlanStatus: "TRIGGERED" }),
      inConfirmQueue: true,
      asOf: ASOF,
    });
    expect(truth?.phase).toBe("propuesta");
    expect(truth?.primaryCta.label).toBe("Revisar y confirmar");
  });

  it("5 CONFIRMADA (orderPendingFill)", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy({ tradePlanStatus: "TRIGGERED" }),
      orderPendingFill: true,
      asOf: ASOF,
    });
    expect(truth?.phase).toBe("confirmada");
    expect(truth?.primaryCta.label).toBe("Ver operaciones");
  });

  it("6 Entradas bloqueadas → CTA none + frase", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy(),
      entriesBlocked: true,
      asOf: ASOF,
    });
    expect(truth?.primaryCta.kind).toBe("none");
    expect(truth?.primaryCta.label).toBe("Entradas bloqueadas");
    expect(truth?.phrase).toMatch(/bloqueadas/i);
    expect(entryOperatingSurfaceSnapshot(truth!).ctaKind).toBe("none");
  });

  it("7 Gate VETO → frase de veto y CTA none (alineadas)", () => {
    const truth = buildEntryOperatingTruth({
      study: armedStudy(),
      gateStatus: "VETO",
      asOf: ASOF,
    });
    expect(truth?.phrase).toMatch(/veto/i);
    expect(truth?.primaryCta.kind).toBe("none");
    expect(truth?.primaryCta.label).toBe("Gate en veto");
  });

  it("8 Posición OPEN HOLD limpia", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen(),
      portfolioReconStatus: "ok",
      asOf: ASOF,
    });
    const snap = operationalTruthSurfaceSnapshot(truth!);
    expect(snap.action).toBe("HOLD");
    expect(snap.ctaLabel).toBe("Mantener");
    expect(truth?.attention).toBe("NORMAL");
    expect(snap.executionHint).toBe("none");
  });

  it("9 Sin protección → protection NONE", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen({
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: null,
          target1: 105,
          target2: 110,
          unrealizedR: 0.4,
        },
      }),
      asOf: ASOF,
    });
    expect(truth?.protection).toBe("NONE");
  });

  it("10 T1 alcanzado → REDUCE + recommended_not_executed", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen({
        lastPrice: 105,
        marketValue: 1050,
        unrealizedPnl: 50,
      }),
      asOf: ASOF,
    });
    expect(truth?.decision.action).toBe("TAKE_PROFIT");
    expect(truth?.primaryCta.label).toBe("Reducir");
    expect(truth?.executionHint).toBe("recommended_not_executed");
    expect(formatExecutionHintCopy(truth!)).toMatch(/aún no ejecutada/i);
  });

  it("11 Misma T1 + orderPending → hint none", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen({
        lastPrice: 105,
        marketValue: 1050,
        unrealizedPnl: 50,
      }),
      asOf: ASOF,
      orderPending: true,
    });
    expect(truth?.decision.action).toBe("TAKE_PROFIT");
    expect(truth?.executionHint).toBe("none");
    expect(formatExecutionHintCopy(truth!)).toBeNull();
  });

  it("12 Recon drift → BLOCKED / Revisar", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen(),
      portfolioReconStatus: "drift",
      asOf: ASOF,
    });
    expect(truth?.attention).toBe("BLOCKED");
    expect(truth?.primaryCta.label).toBe("Revisar");
    expect(truth?.nextEvent).toBe("RECONCILIATION");
  });

  it("13 asOf explícito vs marketAsOf — no se inventa", () => {
    const explicit = buildOperationalTruth({
      position: aaplOpen(),
      asOf: ASOF,
    });
    expect(explicit?.asOf).toBe(ASOF);
    const fallback = buildOperationalTruth({ position: aaplOpen() });
    expect(fallback?.asOf).toBe(fallback?.decision.marketAsOf);
  });

  it("14 protect_hint thin ≠ PROTECT (HOLD gana)", () => {
    const truth = buildOperationalTruth({
      position: aaplOpen(),
      asOf: ASOF,
    });
    expect(truth?.decision.action).toBe("HOLD");
    expect(truth?.primaryCta.label).toBe("Mantener");
  });

  it("15 Daily Desk: HOLD clean → vacío", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "ok",
      pendingConfirm: 0,
    });
    expect(inbox.count).toBe(0);
  });

  it("16 Daily Desk: pending confirm agregado (sin individualizar)", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      pendingConfirm: 2,
      portfolioReconStatus: "ok",
    });
    expect(
      inbox.items.filter((i) => i.kind === "pending_confirm"),
    ).toHaveLength(1);
    expect(inbox.items[0]?.reason).toMatch(/2 pendientes/);
  });

  it("17 Daily Desk: T1 + board mismo símbolo → un item (dedup)", () => {
    const inbox = buildDailyDeskInbox({
      positions: [
        aaplOpen({ lastPrice: 105, marketValue: 1050, unrealizedPnl: 50 }),
      ],
      portfolioReconStatus: "ok",
      protectionDiscrepancies: [
        {
          symbol: "AAPL",
          reason: "Discrepancia de protección",
          recommendedAction: "REVISAR PROTECCIÓN",
        },
      ],
    });
    const aapl = inbox.items.filter((i) => i.symbol.toUpperCase() === "AAPL");
    expect(aapl).toHaveLength(1);
    expect(aapl[0]?.kind).toBe("position");
  });

  it("18 Nunca BUY/COMPRAR en CTAs de entrada y posición", () => {
    const entry = buildEntryOperatingTruth({
      study: armedStudy({ tradePlanStatus: "TRIGGERED" }),
    });
    const pos = buildOperationalTruth({
      position: aaplOpen({ lastPrice: 105 }),
    });
    noBuy(entry?.primaryCta.label);
    noBuy(pos?.primaryCta.label);
    const desk = buildDailyDeskInbox({
      positions: [aaplOpen({ lastPrice: 105 })],
      pendingConfirm: 1,
    });
    for (const item of desk.items) noBuy(item.ctaLabel);
  });

  it("19a Fill parcial → ExecutionState partial (V1.42 F2)", () => {
    const paper = transitionPaperOrder(
      transitionPaperOrder(
        buildPaperOrder({
          instrumentId: "inst-aapl",
          side: "buy",
          quantity: 10,
          orderId: "ORD-partial",
        }),
        "SUBMITTED",
      ),
      "PARTIAL",
      { filledQuantity: 4 },
    );
    const state = buildExecutionState({
      instrumentId: "inst-aapl",
      paperOrder: paper,
      asOf: ASOF,
    });
    expect(state.lifecycle).toBe("in_flight");
    expect(state.orderState).toBe("partial");
    expect(state.fillState).toBe("partial");
    expect(isOrderInFlight(state)).toBe(true);
    expect(formatExecutionStateCopy(state)).toMatch(/parcial/i);
    expect(state.nextAction?.allowsEntry).toBe(false);
  });

  it("19b REJECTED → ExecutionState failed (V1.42 F2)", () => {
    const paper = transitionPaperOrder(
      buildPaperOrder({
        instrumentId: "inst-aapl",
        side: "buy",
        quantity: 10,
        orderId: "ORD-rej",
      }),
      "REJECTED",
    );
    const state = buildExecutionState({
      instrumentId: "inst-aapl",
      paperOrder: paper,
      asOf: ASOF,
    });
    expect(state.lifecycle).toBe("failed");
    expect(state.orderState).toBe("rejected");
    expect(isOrderInFlight(state)).toBe(false);
    expect(formatExecutionStateCopy(state)).toMatch(/rechazada/i);
  });

  it("19d full_exit + protectionDiscrepancy → exit CTA (V1.42 F3 §A.8)", () => {
    const pot = buildPositionOperatingTruth({
      position: aaplOpen({
        lastPrice: 94,
        operational: {
          status: "OPEN",
          direction: "long",
          tradePlanId: "tp-aapl",
          plannedEntry: 100,
          actualEntry: 100,
          initialStop: 95,
          currentStop: 95,
          target1: 105,
          target2: 110,
          exitPlan: { suggestedAction: "full_exit" },
        },
      }),
      protectionDiscrepancy: true,
      asOf: ASOF,
    });
    expect(pot?.primaryCta.kind).toBe("exit");
    expect(pot?.primaryCta.label).toBe("Salir");
    expect(
      pot?.secondaryConditions.some((c) => c.kind === "protection_discrepancy"),
    ).toBe(true);
    noBuy(pot?.primaryCta.label);
  });

  it.todo(
    "19c Mercado cerrado — parked (no modelo de sesión en ExecutionState F2)",
  );

  it.todo(
    "20 Trailing como autoridad — parked (protect_hint thin ≠ autoridad)",
  );
});
