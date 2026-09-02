/**
 * V1.78 golden stages + V1.79 stateful lifecycle + V1.81 T2 POV (same identity AAPL).
 */
import { buildPaperDailyReport } from "@bolsa/shared";
import {
  E2E_ACCOUNT_ID,
  E2E_INSTRUMENT_ID,
  E2E_LIFECYCLE_DECISION_ID,
  E2E_LIFECYCLE_POSITION_ID,
  E2E_LIFECYCLE_TRADE_PLAN_ID,
  E2E_SYMBOL,
  type MercadoInstrumentSlice,
} from "./ids";
import { mercadoOpenPosition, type MercadoOpenPosition } from "./mercado";

/** V1.78–V1.79 + V1.81 T2. `clean` unchanged for GP-V178. */
export type E2eGoldenPositionStage =
  | "clean"
  | "candidate"
  | "open"
  | "t1_ready"
  | "t1_executed"
  | "t2_ready"
  | "t2_executed"
  | "trailing"
  | "exit_required"
  | "closed";

const T1_AT = "2026-09-02T11:00:00.000Z";
const TRAIL_AT = "2026-09-02T12:00:00.000Z";
const T1_EXEC_AT = "2026-09-02T11:30:00.000Z";
const T2_AT = "2026-09-02T12:15:00.000Z";
const T2_EXEC_AT = "2026-09-02T12:45:00.000Z";
const CLOSED_AT = "2026-09-02T15:00:00.000Z";
const MOCK_T1_FILL_ID = "fill-mock-t1";
const MOCK_T2_FILL_ID = "fill-mock-t2";

export function lifecycleOpenPosition(): MercadoOpenPosition {
  const pos = mercadoOpenPosition({
    id: E2E_LIFECYCLE_POSITION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    name: "Apple E2E",
    tradePlanId: E2E_LIFECYCLE_TRADE_PLAN_ID,
    avgCost: 100,
    lastPrice: 102,
    currentStop: 95,
    target1: 105,
    target2: 110,
  });
  return {
    ...pos,
    operational: {
      ...pos.operational,
      operationalView: {
        ...pos.operational.operationalView,
        decisionId: E2E_LIFECYCLE_DECISION_ID,
      },
    },
  };
}

export function lifecycleInstrumentSlice(): MercadoInstrumentSlice {
  const pos = applyGoldenPositionStage(lifecycleOpenPosition(), "open");
  return {
    instrumentId: pos.instrumentId,
    symbol: pos.symbol,
    positionId: pos.operational.operationalView.positionId,
    tradePlanId: pos.operational.tradePlanId,
    decisionId: pos.operational.operationalView.decisionId,
    levels: pos.operational.operationalView.levels,
  };
}

export function applyGoldenPositionStage(
  position: MercadoOpenPosition,
  stage: E2eGoldenPositionStage,
): MercadoOpenPosition {
  if (stage === "clean" || stage === "candidate") return position;

  const levels = position.operational.operationalView.levels;
  const decisionId =
    position.operational.operationalView.decisionId ?? `dec-${position.id}`;
  const isLifecycle = position.id === E2E_LIFECYCLE_POSITION_ID;
  const birthQty = 10;
  const remainingAfterT1 = 5;
  const trailRemaining = isLifecycle ? remainingAfterT1 : birthQty;
  const trailStop = (levels.currentStop ?? 95) + 3;

  const trailRevisions = [
    {
      revisionId: `rev-trail-${position.id}`,
      at: TRAIL_AT,
      previousStop: levels.currentStop,
      nextStop: trailStop,
      previousStatus: "PROTECTED" as const,
      nextStatus: "PROTECTED" as const,
      origin: "trail" as const,
      reason: "trail",
    },
  ];
  const trailHistory = [
    {
      label: "Initial",
      stop: levels.currentStop,
      origin: "birth",
    },
    {
      label: "Trail #1",
      stop: trailStop,
      delta: 3,
      at: TRAIL_AT,
      origin: "trail",
    },
  ];

  if (stage === "open") {
    return {
      ...position,
      operational: {
        ...position.operational,
        operationalView: {
          ...position.operational.operationalView,
          instrumentId: position.instrumentId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "PROTECTED",
          primaryAction: "MANTENER",
          levels: {
            ...levels,
            unrealizedR: 0.4,
          },
          t1: null,
          t2: null,
          stopHistory: [],
          events: [],
          quantity: birthQty,
          remainingQuantity: birthQty,
        },
      },
    };
  }

  if (stage === "t1_ready") {
    return {
      ...position,
      operational: {
        ...position.operational,
        target1Leg: { status: "triggered", at: T1_AT },
        revisions: [],
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "T1_READY",
          primaryAction: "REDUCIR",
          levels: {
            ...levels,
            unrealizedR: 0.6,
          },
          t1: { status: "triggered", at: T1_AT },
          t2: null,
          stopHistory: [],
          events: [],
          quantity: birthQty,
          remainingQuantity: birthQty,
        },
      },
    };
  }

  if (stage === "t1_executed") {
    const remaining = 5;
    const lastPrice = position.lastPrice;
    return {
      ...position,
      quantity: remaining,
      marketValue: lastPrice * remaining,
      unrealizedPnl: (lastPrice - position.avgCost) * remaining,
      unrealizedPnlPct:
        ((lastPrice - position.avgCost) / position.avgCost) * 100,
      operational: {
        ...position.operational,
        status: "PARTIAL",
        remainingQuantity: remaining,
        target1Leg: {
          status: "executed",
          at: T1_EXEC_AT,
          fillId: MOCK_T1_FILL_ID,
        },
        revisions: [],
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "T1_EXECUTED",
          primaryAction: "MANTENER",
          levels: {
            ...levels,
            unrealizedR: 0.8,
          },
          t1: {
            status: "executed",
            at: T1_EXEC_AT,
            fillId: MOCK_T1_FILL_ID,
          },
          t2: null,
          stopHistory: [],
          events: [
            {
              kind: "T1_EXECUTED",
              at: T1_EXEC_AT,
              fillId: MOCK_T1_FILL_ID,
            },
          ],
          quantity: birthQty,
          remainingQuantity: remaining,
        },
      },
    };
  }

  // V1.81 — T2 after T1; primaryAction MONITOR (UI Mantener) intentional.
  if (stage === "t2_ready") {
    const remaining = remainingAfterT1;
    const lastPrice = position.lastPrice;
    return {
      ...position,
      quantity: remaining,
      marketValue: lastPrice * remaining,
      unrealizedPnl: (lastPrice - position.avgCost) * remaining,
      unrealizedPnlPct:
        ((lastPrice - position.avgCost) / position.avgCost) * 100,
      operational: {
        ...position.operational,
        status: "PARTIAL",
        remainingQuantity: remaining,
        target1Leg: {
          status: "executed",
          at: T1_EXEC_AT,
          fillId: MOCK_T1_FILL_ID,
        },
        target2Leg: { status: "triggered", at: T2_AT },
        revisions: [],
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "T2_READY",
          primaryAction: "MONITOR",
          levels: {
            ...levels,
            unrealizedR: 1.0,
          },
          t1: {
            status: "executed",
            at: T1_EXEC_AT,
            fillId: MOCK_T1_FILL_ID,
          },
          t2: { status: "triggered", at: T2_AT },
          stopHistory: [],
          events: [
            {
              kind: "T1_EXECUTED",
              at: T1_EXEC_AT,
              fillId: MOCK_T1_FILL_ID,
            },
            { kind: "T2_TRIGGERED", at: T2_AT },
          ],
          quantity: birthQty,
          remainingQuantity: remaining,
        },
      },
    };
  }

  if (stage === "t2_executed") {
    const remaining = 2;
    const lastPrice = position.lastPrice;
    return {
      ...position,
      quantity: remaining,
      marketValue: lastPrice * remaining,
      unrealizedPnl: (lastPrice - position.avgCost) * remaining,
      unrealizedPnlPct:
        ((lastPrice - position.avgCost) / position.avgCost) * 100,
      operational: {
        ...position.operational,
        status: "PARTIAL",
        remainingQuantity: remaining,
        target1Leg: {
          status: "executed",
          at: T1_EXEC_AT,
          fillId: MOCK_T1_FILL_ID,
        },
        target2Leg: {
          status: "executed",
          at: T2_EXEC_AT,
          fillId: MOCK_T2_FILL_ID,
        },
        revisions: [],
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "T2_EXECUTED",
          primaryAction: "MONITOR",
          levels: {
            ...levels,
            unrealizedR: 1.2,
          },
          t1: {
            status: "executed",
            at: T1_EXEC_AT,
            fillId: MOCK_T1_FILL_ID,
          },
          t2: {
            status: "executed",
            at: T2_EXEC_AT,
            fillId: MOCK_T2_FILL_ID,
          },
          stopHistory: [],
          events: [
            {
              kind: "T1_EXECUTED",
              at: T1_EXEC_AT,
              fillId: MOCK_T1_FILL_ID,
            },
            {
              kind: "T2_EXECUTED",
              at: T2_EXEC_AT,
              fillId: MOCK_T2_FILL_ID,
            },
          ],
          quantity: birthQty,
          remainingQuantity: remaining,
        },
      },
    };
  }

  if (stage === "trailing") {
    return {
      ...position,
      quantity: trailRemaining,
      marketValue: position.lastPrice * trailRemaining,
      operational: {
        ...position.operational,
        status: "TRAILING",
        remainingQuantity: trailRemaining,
        target1Leg: isLifecycle
          ? {
              status: "executed",
              at: T1_EXEC_AT,
              fillId: MOCK_T1_FILL_ID,
            }
          : { status: "pending" },
        revisions: trailRevisions,
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "TRAILING",
          primaryAction: "SUBIR_STOP",
          levels: {
            ...levels,
            unrealizedR: 0.6,
          },
          t1: isLifecycle
            ? {
                status: "executed",
                at: T1_EXEC_AT,
                fillId: MOCK_T1_FILL_ID,
              }
            : null,
          t2: null,
          stopHistory: trailHistory,
          events: isLifecycle
            ? [
                {
                  kind: "T1_EXECUTED",
                  at: T1_EXEC_AT,
                  fillId: MOCK_T1_FILL_ID,
                },
              ]
            : [],
          quantity: birthQty,
          remainingQuantity: trailRemaining,
        },
      },
    };
  }

  if (stage === "exit_required") {
    return {
      ...position,
      quantity: trailRemaining,
      marketValue: position.lastPrice * trailRemaining,
      operational: {
        ...position.operational,
        remainingQuantity: trailRemaining,
        target1Leg: isLifecycle
          ? {
              status: "executed",
              at: T1_EXEC_AT,
              fillId: MOCK_T1_FILL_ID,
            }
          : { status: "pending" },
        revisions: [],
        operationalView: {
          positionId: position.operational.operationalView.positionId,
          instrumentId: position.instrumentId,
          tradePlanId: position.operational.tradePlanId,
          decisionId,
          lineageCollapsed: false,
          operatingState: "EXIT_REQUIRED",
          primaryAction: "SALIR",
          levels: {
            ...levels,
            unrealizedR: 0.6,
          },
          t1: null,
          t2: null,
          stopHistory: [],
          events: [],
          quantity: birthQty,
          remainingQuantity: trailRemaining,
        },
      },
    };
  }

  // closed — representation, not ledger fill. DTO quantity 0 hides open HUD.
  return {
    ...position,
    quantity: 0,
    marketValue: 0,
    unrealizedPnl: 0,
    unrealizedPnlPct: 0,
    operational: {
      ...position.operational,
      status: "CLOSED",
      remainingQuantity: 0,
      target1Leg: { status: "pending" },
      revisions: [],
      operationalView: {
        positionId: position.operational.operationalView.positionId,
        instrumentId: position.instrumentId,
        tradePlanId: position.operational.tradePlanId,
        decisionId,
        lineageCollapsed: false,
        operatingState: "CLOSED",
        primaryAction: "MANTENER",
        levels: {
          ...levels,
          unrealizedR: 0,
        },
        t1: null,
        t2: null,
        stopHistory: [],
        events: [{ kind: "POSITION_CLOSED", at: CLOSED_AT }],
        quantity: birthQty,
        remainingQuantity: 0,
      },
    },
  };
}

function lifecycleAaplCandidate(stale: boolean) {
  return {
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    rank: 1,
    score: 8.2,
    symbol: E2E_SYMBOL,
    autoSource: "estudio_ranking",
    templateId: "moderate",
    freshness: stale ? ("stale" as const) : ("current" as const),
    reasonCode: stale ? ("ENTRY_STALE_DATA" as const) : undefined,
    humanMessage: stale ? "Datos obsoletos — no proponer." : undefined,
    vetoes: stale ? ["data_freshness:stale"] : undefined,
    tradePlan: {
      decisionId: E2E_LIFECYCLE_DECISION_ID,
      instrumentId: E2E_INSTRUMENT_ID,
      direction: "long" as const,
      status: "ARMED" as const,
      quantity: 10,
      riskPct: 0.5,
      whyNot: [],
      executionAllowed: !stale,
      entry: 100,
      structuralStop: 95,
      target1: 105,
      target2: 110,
    },
    entry: 100,
    structuralStop: 95,
    target1: 105,
    target2: 110,
  };
}

export function lifecycleAutoDesk(accountId = E2E_ACCOUNT_ID, stale = false) {
  const candidates = [lifecycleAaplCandidate(stale)];
  const base = buildPaperDailyReport({
    accountId,
    asOf: "2026-09-02",
    dryRun: true,
    paperDExecute: false,
    entry: {
      status: "dry_run",
      proposedCount: candidates.length,
      executedCount: 0,
    },
    positions: [],
    notes: [
      "dryRun=true — V1.79 lifecycle AAPL.",
      stale
        ? "ENTRY_STALE_DATA · PAPER_D_EXECUTE off."
        : "AUTO armado · PAPER_D_EXECUTE off — sin ejecución ledger.",
    ],
  });
  return {
    ...base,
    entry: {
      ...base.entry,
      candidates,
      skipped: [],
    },
  };
}

export function lifecycleDailyOpsEnvelope(
  accountId = E2E_ACCOUNT_ID,
  stale = false,
) {
  const autoDesk = lifecycleAutoDesk(accountId, stale);
  return {
    schemaVersion: "daily_ops_report_v1",
    asOf: "2026-09-02",
    generatedAt: "2026-09-02T12:00:00.000Z",
    accountId,
    summary: {
      accountId,
      cash: 100_000,
      totalEquity: stale ? 100_000 : 100_000,
      openPositions: 0,
      dayPnl: 0,
      dayPnlPct: 0,
    },
    ledgerToday: [],
    tradesToday: [],
    week: [],
    f3PendingCount: 0,
    channels: { alarma: 0, aviso: 0, none: 0 },
    opinions: [],
    notes: autoDesk.notes,
    estudioStatus: "ok",
    estudioCount: 1,
    autoDesk,
  };
}

export function lifecycleDecisionStudy() {
  return {
    sessionId: "sess-e2e-lifecycle-1",
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    hasOperationalPlan: true,
    tradePlanStatus: "ARMED",
    studiedAt: "2026-09-02T09:00:00.000Z",
    entry: 100,
    stop: 95,
    target1: 105,
    target2: 110,
  };
}

export function lifecycleJournalEntry(closed: boolean) {
  return {
    id: "journal-e2e-lifecycle-1",
    decisionId: E2E_LIFECYCLE_DECISION_ID,
    instrumentId: E2E_INSTRUMENT_ID,
    symbol: E2E_SYMBOL,
    studiedAt: "2026-09-02T09:00:00.000Z",
    headline: closed
      ? "POSITION_CLOSED — remainingQuantity=0"
      : "Plan armado — dryRun",
    status: closed ? "closed" : "studied",
  };
}
