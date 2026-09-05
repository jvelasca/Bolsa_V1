/**
 * V1.54 — Operating Desk autoDesk projection (GP-DESK-UI-01,02,04,05,08,09).
 */

import { describe, expect, it } from "vitest";
import {
  buildOperatingDeskInbox,
  dailyDeskItemFromCandidateSnapshot,
  dailyDeskItemFromExceptionFact,
  formatCandidateDenyPhrase,
  isCandidateDenied,
  projectAutoDeskCandidates,
  projectDeskExceptionFacts,
  reconDriftPhraseParityCheck,
  POSITION_BIRTH_FAILED_PHRASE,
  ORPHAN_RECOVERY_FAILED_PHRASE,
} from "./cognitive/daily-desk-auto-projection.js";
import {
  buildPaperDailyReport,
  PAPER_DAILY_REPORT_SCHEMA,
  type PaperDeskCandidateSnapshotV1,
} from "./cognitive/paper-daily-report.js";
import { formatPositionDecisionPhrase } from "./cognitive/position-decision-copy.js";
import { buildPositionDecision } from "./cognitive/position-decision.js";
import { buildPositionStateFromFill } from "./cognitive/position-state.js";
import type { TradePlanV1 } from "./cognitive/trade-plan.js";

function triggeredPlan(overrides: Partial<TradePlanV1> = {}): TradePlanV1 {
  return {
    decisionId: "dec-msft",
    instrumentId: "inst-msft",
    direction: "long",
    status: "TRIGGERED",
    quantity: 10,
    riskPct: 0.5,
    whyNot: [],
    executionAllowed: true,
    entry: 100,
    structuralStop: 94,
    target1: 112,
    target2: 124,
    expectedRR: 2,
    riskAmount: 60,
    ...overrides,
  };
}

function triggeredCandidate(
  overrides: Partial<PaperDeskCandidateSnapshotV1> = {},
): PaperDeskCandidateSnapshotV1 {
  return {
    decisionId: "dec-msft",
    instrumentId: "inst-msft",
    rank: 1,
    score: 5,
    symbol: "MSFT",
    templateId: "moderate",
    analysisAsOf: "2026-09-01T09:00:00.000Z",
    tradePlan: triggeredPlan(),
    entry: 100,
    structuralStop: 94,
    target1: 112,
    target2: 124,
    riskAmount: 60,
    expectedRr: 2,
    ...overrides,
  };
}

function autoDeskWithCandidates(
  candidates: PaperDeskCandidateSnapshotV1[],
  skipped: PaperDeskCandidateSnapshotV1[] = [],
) {
  const base = buildPaperDailyReport({
    accountId: "acc-1",
    asOf: "2026-09-01",
    dryRun: true,
    paperDExecute: false,
    entry: {
      status: "dry_run",
      proposedCount: candidates.length,
      executedCount: 0,
    },
    positions: [],
  });
  return {
    ...base,
    entry: {
      ...base.entry,
      candidates,
      skipped,
    },
  };
}

describe("GP-DESK-UI-01 TRIGGERED candidate → green row", () => {
  it("projects TRIGGERED autoDesk candidate to oportunidades", () => {
    const autoDesk = autoDeskWithCandidates([triggeredCandidate()]);
    const items = projectAutoDeskCandidates({ autoDesk });
    expect(items).toHaveLength(1);
    expect(items[0]?.bucket).toBe("oportunidades");
    expect(items[0]?.kind).toBe("entry");
    expect(items[0]?.symbol).toBe("MSFT");
    expect(items[0]?.phaseLabel).toMatch(/Disparada/i);
    expect(items[0]?.reason).toContain("#1");
    expect(items[0]?.reason).toContain("moderate");
  });

  it("AUTO posture omits COMPRAR — links Confirm discipline", () => {
    const item = dailyDeskItemFromCandidateSnapshot(triggeredCandidate(), {
      paperAuto: {
        bookMode: "auto",
        autoArmed: true,
        paperDExecuteEnv: false,
        autoActive: true,
        modeLabel: "AUTO",
        modeDetail: "",
        statusBadge: null,
        requiresHumanConfirm: false,
        executeEligible: false,
        spineLine: "",
        armStateLabel: "AUTO ARMADO",
        executionVenueLabel: "EJECUCIÓN: PAPER",
        armPermissionLine:
          "Arm = permiso de motor · no autoriza una operación · Confirm = firma",
      },
    });
    expect(item?.bucket).toBe("oportunidades");
    expect(item?.ctaLabel.toUpperCase()).not.toContain("COMPRAR");
    expect(item?.ctaLabel.toUpperCase()).not.toContain("BUY");
    expect(item?.phrase).toMatch(/AUTO|PAPER|Ranking/i);
  });
});

describe("GP-DESK-UI-02 DENY candidate → no green / blocked copy", () => {
  it("ENTRY_RISK_LIMIT → no_operar BLOCKED, not oportunidades", () => {
    const denied = triggeredCandidate({
      reasonCode: "ENTRY_RISK_LIMIT",
      vetoes: ["portfolio_risk_limit"],
      humanMessage: "book_max_open_positions",
    });
    expect(isCandidateDenied(denied)).toBe(true);

    const autoDesk = autoDeskWithCandidates([denied]);
    const items = projectAutoDeskCandidates({ autoDesk });
    expect(items).toHaveLength(1);
    expect(items[0]?.bucket).not.toBe("oportunidades");
    expect(items[0]?.bucket).toBe("no_operar");
    expect(items[0]?.attention).toBe("BLOCKED");
    expect(items[0]?.reasonCode).toBe("ENTRY_RISK_LIMIT");
    expect(formatCandidateDenyPhrase(denied)).toMatch(/DENY|book_max/i);
  });

  it("ENTRY_STALE_DATA → reasonCode on desk item", () => {
    const denied = triggeredCandidate({
      reasonCode: "ENTRY_STALE_DATA",
      freshness: "stale",
      humanMessage: "Datos obsoletos — no proponer.",
    });
    const items = projectAutoDeskCandidates({
      autoDesk: autoDeskWithCandidates([denied]),
    });
    expect(items[0]?.attention).toBe("BLOCKED");
    expect(items[0]?.reasonCode).toBe("ENTRY_STALE_DATA");
    expect(items[0]?.phrase).toMatch(/Datos obsoletos/i);
    expect(items[0]?.ctaLabel.toUpperCase()).not.toContain("COMPRAR");
  });

  it("skipped[] candidates also projected as blocked", () => {
    const skipped = triggeredCandidate({
      instrumentId: "inst-skip",
      symbol: "SKIP",
      reasonCode: "ENTRY_INVALID_STOP",
    });
    const autoDesk = autoDeskWithCandidates([], [skipped]);
    const items = projectAutoDeskCandidates({ autoDesk });
    expect(items[0]?.bucket).toBe("no_operar");
    expect(items[0]?.attention).toBe("BLOCKED");
  });
});

describe("GP-DESK-UI-04 position_birth_failed → red row", () => {
  it("exception fact → requiere_accion with reconciliar copy", () => {
    const item = dailyDeskItemFromExceptionFact({
      kind: "position_birth_failed",
      instrumentId: "inst-aapl",
      symbol: "AAPL",
      decisionId: "dec-aapl",
    });
    expect(item.bucket).toBe("requiere_accion");
    expect(item.attention).toBe("URGENT");
    expect(item.phrase).toBe(POSITION_BIRTH_FAILED_PHRASE);
    expect(item.ctaLabel).toMatch(/Reconciliar/i);
  });

  it("buildOperatingDeskInbox merges birth_failed into 🔴", () => {
    const inbox = buildOperatingDeskInbox({
      positions: [],
      exceptionFacts: [
        {
          kind: "position_birth_failed",
          symbol: "AAPL",
          instrumentId: "inst-aapl",
        },
      ],
    });
    const red = inbox.buckets.find((b) => b.id === "requiere_accion");
    expect(red?.count).toBeGreaterThan(0);
    expect(red?.items.some((i) => i.reason === "position_birth_failed")).toBe(
      true,
    );
  });
});

describe("V2.47 orphan_recovery_failed → red row URGENT", () => {
  it("exception fact → requiere_accion URGENT", () => {
    const item = dailyDeskItemFromExceptionFact({
      kind: "orphan_recovery_failed",
    });
    expect(item.bucket).toBe("requiere_accion");
    expect(item.attention).toBe("URGENT");
    expect(item.phrase).toBe(ORPHAN_RECOVERY_FAILED_PHRASE);
    expect(item.ctaLabel).toMatch(/Revisar/i);
  });
});

describe("GP-DESK-UI-05 recon drift → reconciliar copy", () => {
  it("portfolio drift projects cartera row in requiere_accion", () => {
    const items = projectDeskExceptionFacts({
      portfolioReconStatus: "drift",
    });
    expect(items).toHaveLength(1);
    expect(items[0]?.bucket).toBe("requiere_accion");
    expect(items[0]?.symbol).toBe("Cartera");
    expect(items[0]?.phrase).toMatch(/discrepancia/i);
    expect(items[0]?.ctaLabel).toMatch(/Reconciliar/i);
  });

  it("portfolio unavailable uses unavailable copy", () => {
    const items = projectDeskExceptionFacts({
      portfolioReconStatus: "unavailable",
    });
    expect(items[0]?.phrase).toMatch(/no disponible/i);
  });
});

describe("GP-DESK-UI-08 autoDesk absent → no crash", () => {
  it("projectAutoDeskCandidates with null autoDesk returns []", () => {
    expect(projectAutoDeskCandidates({ autoDesk: null })).toEqual([]);
    expect(projectAutoDeskCandidates({ autoDesk: undefined })).toEqual([]);
  });

  it("buildOperatingDeskInbox without autoDesk equals base + exceptions only", () => {
    const inbox = buildOperatingDeskInbox({ positions: [] });
    expect(inbox.count).toBe(0);
    // V2.05 / F6 — four chrome buckets (proteger folded into Atención).
    expect(inbox.buckets).toHaveLength(4);
  });

  it("legacy PaperDailyReport without candidates field is safe", () => {
    const legacy = buildPaperDailyReport({
      accountId: "acc-1",
      dryRun: true,
      paperDExecute: false,
      entry: { status: "skipped" },
      positions: [],
    });
    expect(legacy.schemaVersion).toBe(PAPER_DAILY_REPORT_SCHEMA);
    expect(projectAutoDeskCandidates({ autoDesk: legacy })).toEqual([]);
  });
});

describe("GP-DESK-UI-09 phrase parity with position-decision-copy", () => {
  it("recon drift phrase matches formatPositionDecisionPhrase", () => {
    expect(reconDriftPhraseParityCheck("drift")).toBe(true);

    const plan: TradePlanV1 = {
      decisionId: "dec-aapl",
      instrumentId: "inst-aapl",
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
    const position = buildPositionStateFromFill(plan, {
      price: 100,
      quantity: 10,
      filledAt: "2026-08-28T10:00:00Z",
    });
    const decision = buildPositionDecision({
      position: position ?? undefined,
      signals: { markPrice: 102 },
      templateId: "moderate",
      portfolioReconStatus: "drift",
    });
    const items = projectDeskExceptionFacts({ portfolioReconStatus: "drift" });
    expect(formatPositionDecisionPhrase(decision!)).toBe(items[0]?.phrase);
  });
});
