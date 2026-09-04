/**
 * V1.42 F6 — Daily Desk four buckets (§B.7).
 */

import { describe, expect, it } from "vitest";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  attentionRank,
  bucketFromEntryTruth,
  buildDailyDeskInbox,
  DAILY_DESK_BUCKET_LABEL,
  DAILY_DESK_BUCKET_ORDER,
  dailyDeskSurfaceSnapshot,
} from "./daily-desk.js";
import { buildEntryOperatingTruth } from "./entry-operating-truth.js";
import type { PositionDto } from "../types.js";

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

function armedStudy(
  overrides: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    artifactType: "decision_journal_study",
    schemaVersion: 1,
    sessionId: "s1",
    decisionId: "d1",
    instrumentId: "inst-msft",
    symbol: "MSFT",
    name: "Microsoft",
    studiedAt: "2026-08-31T09:00:00.000Z",
    ageMs: null,
    period: null,
    timeframe: null,
    opinion: null,
    status: "in_progress",
    strength: null,
    strengthBand: null,
    vigencia: null,
    entry: 100,
    stop: 94,
    target1: 112,
    target2: 124,
    expectedRR: 2,
    riskAmount: 60,
    quantity: 10,
    initialRiskR: 1,
    positionValue: 1000,
    direction: "long",
    hasOperationalPlan: true,
    userThesis: null,
    decisionSummary: null,
    analysisNotes: [],
    trends: [],
    consensus: { bullish: 0, bearish: 0, neutral: 0, total: 0 },
    indicators: { primary: null, confirmation: null },
    invalidation: [],
    nextReviewAt: null,
    tradePlanStatus: "ARMED",
    action: null,
    ...overrides,
  } as DecisionJournalStudyViewV1;
}

describe("dailyDesk V2.05 four buckets", () => {
  it("always exposes four chrome buckets (proteger folded)", () => {
    const inbox = buildDailyDeskInbox({ positions: [], pendingConfirm: 0 });
    expect(inbox.buckets.map((b) => b.id)).toEqual([
      ...DAILY_DESK_BUCKET_ORDER,
    ]);
    expect(inbox.buckets.map((b) => b.label)).toEqual([
      DAILY_DESK_BUCKET_LABEL.requiere_accion,
      DAILY_DESK_BUCKET_LABEL.oportunidades,
      DAILY_DESK_BUCKET_LABEL.posiciones,
      DAILY_DESK_BUCKET_LABEL.no_operar,
    ]);
    expect(inbox.buckets).toHaveLength(4);
  });

  it("HOLD clean → posiciones bucket lists open book", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "ok",
      pendingConfirm: 0,
    });
    expect(inbox.count).toBeGreaterThan(0);
    const posiciones = inbox.buckets.find((b) => b.id === "posiciones");
    expect(posiciones?.count).toBeGreaterThan(0);
    expect(posiciones?.items[0]?.ctaLabel).toMatch(/Mantener/i);
  });

  it("pending confirm → 🔴 REQUIERE ACCIÓN", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      pendingConfirm: 2,
      portfolioReconStatus: "ok",
    });
    expect(inbox.items[0]?.kind).toBe("pending_confirm");
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.ctaLabel).toBe("Revisar y confirmar");
    expect(inbox.buckets.find((b) => b.id === "requiere_accion")?.count).toBe(
      1,
    );
  });

  it("full_exit / T1 reduce → 🔴 with same POT CTA family", () => {
    const pos = aaplOpen({
      lastPrice: 105,
      marketValue: 1050,
      unrealizedPnl: 50,
    });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.ctaLabel).toBe("Reducir");
    expect(inbox.items[0]?.phrase.length).toBeGreaterThan(0);
    expect(attentionRank(inbox.items[0]!.attention)).toBeGreaterThan(0);
  });

  it("recon drift → 🔴 BLOCKED", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "drift",
    });
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.attention).toBe("BLOCKED");
    expect(inbox.items[0]?.ctaLabel).toBe("Revisar");
  });

  it("protection discrepancy → 🔴 Requiere atención (proteger folded)", () => {
    const inbox = buildDailyDeskInbox({
      positions: [],
      protectionDiscrepancies: [
        {
          symbol: "MSFT",
          reason: "Discrepancia de protección",
          recommendedAction: "REVISAR PROTECCIÓN",
        },
      ],
    });
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.ctaLabel).toBe("Proteger");
  });

  it("UNKNOWN instrument → 🔴 Ver operaciones (never reenviar)", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      portfolioReconStatus: "ok",
      unknownInstrumentIds: ["inst-aapl"],
    });
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.ctaLabel).toMatch(/operaciones/i);
    expect(inbox.items[0]?.phrase).toMatch(/desconocida|no duplicar/i);
  });

  it("incident → 🔴", () => {
    const inbox = buildDailyDeskInbox({
      positions: [],
      hasOpenIncident: true,
    });
    expect(inbox.items[0]?.kind).toBe("incident");
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
  });

  it("preparada EOT → 🟢 OPORTUNIDADES with human phase (not ARMED)", () => {
    const study = armedStudy();
    const eot = buildEntryOperatingTruth({ study, inEstudio: true });
    expect(eot?.phase).toBe("preparada");
    expect(bucketFromEntryTruth(eot!)).toBe("oportunidades");

    const studies = new Map([[study.instrumentId, study]]);
    const inbox = buildDailyDeskInbox({
      positions: [],
      studiesByInstrument: studies,
      board: {
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
        },
        decisionSessions: [
          {
            sessionId: "s1",
            kind: "propose",
            status: "open",
            instrumentId: study.instrumentId,
            symbol: "MSFT",
            createdAt: "2026-08-31T09:00:00Z",
            gate: "PASS",
            tradePlan: {
              artifactType: "ART-TRADE-PLAN",
              schemaVersion: "1.0.0",
              decisionId: "d1",
              instrumentId: study.instrumentId,
              direction: "long",
              status: "ARMED",
              entryReady: true,
              structuralStop: 94,
              entry: 100,
              target1: 112,
              target2: 124,
            },
          },
        ],
        semiF3Queue: [],
      } as never,
    });
    const opp = inbox.buckets.find((b) => b.id === "oportunidades");
    expect(opp?.count).toBeGreaterThan(0);
    const item = opp!.items[0]!;
    expect(item.phaseLabel).toMatch(/Preparada/i);
    expect(item.phaseLabel).not.toMatch(/ARMED|WATCH|TRIGGERED/);
    expect(item.ctaLabel.toUpperCase()).not.toContain("BUY");
    expect(item.phrase).toMatch(
      /Oportunidad armada|Esperar trigger|Plan armado|Disparador/i,
    );
  });

  it("WATCH without operable plan → 🟡 VIGILAR (not Ranking BUY)", () => {
    const study = armedStudy({
      instrumentId: "inst-enst",
      symbol: "ENST1",
      tradePlanStatus: "WATCH",
      hasOperationalPlan: false,
      entry: null,
      stop: null,
      target1: null,
      target2: null,
    });
    const studies = new Map([[study.instrumentId, study]]);
    const inbox = buildDailyDeskInbox({
      positions: [],
      studiesByInstrument: studies,
      board: {
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
        },
        decisionSessions: [
          {
            sessionId: "sw",
            kind: "propose",
            status: "open",
            instrumentId: study.instrumentId,
            symbol: "ENST1",
            createdAt: "2026-08-31T09:00:00Z",
            gate: "PASS",
            tradePlan: {
              artifactType: "ART-TRADE-PLAN",
              schemaVersion: "1.0.0",
              decisionId: "dw",
              instrumentId: study.instrumentId,
              direction: "long",
              status: "WATCH",
              entryReady: false,
              structuralStop: 9,
              entry: 10,
            },
          },
        ],
        semiF3Queue: [],
      } as never,
    });
    const noOperar = inbox.buckets.find((b) => b.id === "no_operar");
    expect(noOperar?.count).toBeGreaterThan(0);
    expect(noOperar!.items[0]!.phaseLabel).toMatch(/estudio/i);
    for (const item of noOperar!.items) {
      expect(item.phaseLabel ?? "").not.toMatch(/^(WATCH|ARMED|TRIGGERED)$/);
      expect(item.ctaLabel.toUpperCase()).not.toContain("BUY");
    }
  });

  it("surface snapshot includes buckets + phrases; no BUY", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const a = buildDailyDeskInbox({
      positions: [pos],
      pendingConfirm: 1,
      portfolioReconStatus: "ok",
    });
    const b = buildDailyDeskInbox({
      positions: [pos],
      pendingConfirm: 1,
      portfolioReconStatus: "ok",
    });
    expect(dailyDeskSurfaceSnapshot(a)).toEqual(dailyDeskSurfaceSnapshot(b));
    expect(dailyDeskSurfaceSnapshot(a).bucketIds).toContain("requiere_accion");
    expect(dailyDeskSurfaceSnapshot(a).phrases.length).toBe(a.count);
    for (const item of a.items) {
      expect(item.ctaLabel.toUpperCase()).not.toContain("BUY");
      expect(item.ctaLabel.toUpperCase()).not.toContain("COMPRAR");
    }
  });

  it("V2.16 — exceptionSummary headline for Exception Desk", () => {
    const inbox = buildDailyDeskInbox({
      positions: [aaplOpen()],
      pendingConfirm: 1,
      portfolioReconStatus: "ok",
    });
    expect(inbox.exceptionSummary).toBeTruthy();
    expect(inbox.exceptionSummary!.requiereAtencion).toBeGreaterThanOrEqual(1);
    expect(inbox.exceptionSummary!.headline).toMatch(/requieren atención/);
    expect(inbox.exceptionSummary!.headline).toMatch(/posiciones OK/);
  });

  it("orderPending on T1 → 🔴 Ver operaciones (same POT/ExecutionState as Mercado)", () => {
    const pos = aaplOpen({ lastPrice: 105 });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
      pendingInstrumentIds: [pos.instrumentId],
    });
    expect(inbox.count).toBe(1);
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    expect(inbox.items[0]?.ctaLabel).toMatch(/operaciones/i);
  });

  it("V2.19 — OPEN without executed stop → Requiere atención / Proteger (same as Mercado)", () => {
    const pos = aaplOpen({
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
        exitPlan: { suggestedAction: "hold" },
      },
    });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
      pendingConfirm: 0,
      // Discrepancy wire = same Mercado protect path when stop no está en libro.
      protectionDiscrepancies: [
        {
          symbol: "AAPL",
          reason: "Stop no ejecutado en libro",
          recommendedAction: "PROTEGER",
        },
      ],
    });
    const item = inbox.items.find((i) => i.symbol === "AAPL");
    expect(item?.bucket).toBe("requiere_accion");
    expect(item?.ctaKind).toBe("protect");
    expect(item?.ctaLabel).toMatch(/proteger/i);
  });

  it("V2.41 — Posiciones empty is honest when open position lives in Atención", () => {
    const pos = aaplOpen({
      lastPrice: 105,
      marketValue: 1050,
      unrealizedPnl: 50,
    });
    const inbox = buildDailyDeskInbox({
      positions: [pos],
      portfolioReconStatus: "ok",
    });
    expect(inbox.items[0]?.kind).toBe("position");
    expect(inbox.items[0]?.bucket).toBe("requiere_accion");
    const posiciones = inbox.buckets.find((b) => b.id === "posiciones");
    expect(posiciones?.count).toBe(0);
    expect(posiciones?.emptyLabel).toMatch(/Atención/i);
    expect(posiciones?.emptyLabel).not.toMatch(/Sin posiciones abiertas/i);
  });
});
