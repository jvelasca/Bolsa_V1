import { describe, expect, it } from "vitest";
import type { DecisionBoardV1 } from "../decision-board.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  buildMesaSessionState,
  enrichMesaCandidates,
  filterMesaAttentionItems,
  mesaEntriesBlocked,
  overlayLiveTradePlanOnStudy,
  pickPositionStudies,
  studiesByDecisionIdMap,
  studiesByInstrumentMap,
} from "./mesa-hoy-model.js";
import type { HoyQueueItemV1 } from "./hoy-queue.js";
import type { MesaEntryQueueRowV1 } from "./mesa-entry-queue.js";
import { buildPortfolioScenario } from "./portfolio-scenario.js";

const baseItem = (overrides: Partial<HoyQueueItemV1> = {}): HoyQueueItemV1 => ({
  id: "x",
  symbol: "AAPL",
  kind: "WATCH",
  status: "WATCH",
  whyNot: [],
  gate: "PASS",
  planSource: "live",
  ...overrides,
});

const emptyBoard: DecisionBoardV1 = {
  accountId: "acc-1",
  generatedAt: new Date().toISOString(),
  buckets: {
    pendingConfirm: 1,
    vetoed: 0,
    deferred: 0,
    autoWaiting: 0,
    total: 1,
  },
  semiF3Queue: [],
  decisionSessions: [],
};

describe("mesa-hoy-model", () => {
  it("blocks entries on kill switch, incidents or veto", () => {
    expect(mesaEntriesBlocked({ killSwitchEffective: true })).toBe(true);
    expect(
      mesaEntriesBlocked({
        incidents: [
          {
            incidentId: "i1",
            accountId: "a",
            kind: "live_drift",
            status: "open",
            snapshot: null,
            openedAt: "",
            reviewedAt: null,
            reviewedBy: null,
            resolvedAt: null,
            resolvedBy: null,
            resolutionNote: null,
            clearedAt: null,
          },
        ],
      }),
    ).toBe(true);
    expect(mesaEntriesBlocked({ vetoed: 2 })).toBe(true);
    expect(mesaEntriesBlocked({})).toBe(false);
  });

  it("prioritizes incident session state", () => {
    const state = buildMesaSessionState(emptyBoard, {
      entriesBlocked: true,
      incidentCount: 1,
    });
    expect(state.tone).toBe("blocked");
    expect(state.headline).toMatch(/incidente/i);
    expect(state.detail).toMatch(/BLOQUEADAS/);
  });

  it("kill switch session blocks entries", () => {
    const state = buildMesaSessionState(emptyBoard, {
      entriesBlocked: true,
      killSwitchEffective: true,
    });
    expect(state.tone).toBe("blocked");
    expect(state.headline).toMatch(/kill switch/i);
    expect(state.detail).toMatch(/bloqueadas/i);
  });

  it("NO TRADE session when zero ready and no pending confirm", () => {
    const board: DecisionBoardV1 = {
      ...emptyBoard,
      buckets: {
        pendingConfirm: 0,
        vetoed: 0,
        deferred: 0,
        autoWaiting: 0,
        total: 0,
      },
      decisionSessions: [
        {
          sessionId: "s-watch",
          kind: "propose",
          status: "open",
          instrumentId: "i1",
          symbol: "WATCH1",
          createdAt: "2026-08-26T10:00:00Z",
          gate: "PASS",
          tradePlan: {
            artifactType: "ART-TRADE-PLAN",
            schemaVersion: "1.0.0",
            decisionId: "d1",
            instrumentId: "i1",
            direction: "long",
            status: "WATCH",
            entryReady: false,
            structuralStop: 9,
            entry: 10,
          },
        },
      ],
    };
    const state = buildMesaSessionState(board, { entriesBlocked: false });
    expect(state.headline).toBe("Hoy no hay operaciones recomendadas");
    expect(state.candidateCounts.ready).toBe(0);
  });

  it("filters attention items for REVIEW and protect hints", () => {
    const queue: HoyQueueItemV1[] = [
      baseItem({ kind: "WATCH" }),
      baseItem({
        kind: "REVIEW",
        thesisHealth: {
          status: "review",
          hint: "Tesis deteriorada",
          why: [],
          confidence: 0.4,
        },
      }),
      baseItem({
        kind: "ARMED",
        protectPlan: {
          status: "protect_hint",
          why: [],
          rMultiple: 1.2,
          target1: null,
          suggestedProtectStop: 140,
        },
      }),
    ];
    const attention = filterMesaAttentionItems(queue);
    expect(attention).toHaveLength(2);
    expect(attention[0]?.recommendedAction).toBe("REVISAR");
    expect(attention[1]?.recommendedAction).toBe("REVISAR PROTECCIÓN");
  });

  it("persist skipped discrepancy appears in attention queue", () => {
    const attention = filterMesaAttentionItems([], 5, [
      {
        symbol: "MSFT",
        reason: "Discrepancia de protección — persist omitido",
        recommendedAction: "REVISAR PROTECCIÓN",
      },
    ]);
    expect(attention).toHaveLength(1);
    expect(attention[0]?.symbol).toBe("MSFT");
    expect(attention[0]?.recommendedAction).toBe("REVISAR PROTECCIÓN");
  });

  it("overlays live board TradePlan sizing onto study without qty", () => {
    const study = {
      sessionId: "stale",
      instrumentId: "i1",
      symbol: "AAF",
      studiedAt: "2026-08-26T10:00:00Z",
      status: "in_progress",
      hasOperationalPlan: true,
      entry: 100,
      stop: 95,
      quantity: null,
      initialRiskR: null,
      positionValue: null,
      riskAmount: 50,
    } as DecisionJournalStudyViewV1;

    const board: DecisionBoardV1 = {
      ...emptyBoard,
      decisionSessions: [
        {
          sessionId: "s-live",
          kind: "propose",
          status: "open",
          instrumentId: "i1",
          symbol: "AAF",
          createdAt: "2026-08-27T10:00:00Z",
          gate: "PASS",
          tradePlan: {
            artifactType: "ART-TRADE-PLAN",
            schemaVersion: "1.0.0",
            decisionId: "d-live",
            instrumentId: "i1",
            direction: "long",
            status: "TRIGGERED",
            entryReady: true,
            structuralStop: 95,
            entry: 100,
            quantity: 10,
            initialRiskR: 1.5,
            positionValue: 1000,
            riskAmount: 50,
            target1: 110,
            expectedRR: 2,
          },
        },
      ],
    };

    const rows: MesaEntryQueueRowV1[] = [
      {
        symbol: "AAF",
        status: "TRIGGERED",
        statusLabel: "Listo",
        gate: "PASS",
      },
    ];
    const enriched = enrichMesaCandidates(
      rows,
      board,
      new Map([["i1", study]]),
    );
    expect(enriched[0]?.study?.quantity).toBe(10);
    expect(enriched[0]?.study?.initialRiskR).toBe(1.5);
    expect(enriched[0]?.study?.positionValue).toBe(1000);

    const scenario = buildPortfolioScenario({
      candidate: enriched[0]!,
      positions: [],
      equity: 5000,
      cash: 5000,
      candidateSector: "Tech",
    });
    expect(scenario.verdict).toBe("COMPATIBLE");
    expect(scenario.after.openRiskR).toBe(1.5);
  });

  it("overlay ignores WATCH live plan geometry", () => {
    const merged = overlayLiveTradePlanOnStudy(null, {
      artifactType: "ART-TRADE-PLAN",
      schemaVersion: "1.0.0",
      decisionId: "d1",
      instrumentId: "i1",
      direction: "long",
      status: "WATCH",
      entryReady: false,
      structuralStop: 95,
      entry: 100,
      quantity: 10,
      initialRiskR: 1,
    });
    expect(merged).toBeNull();
  });

  it("pickPositionStudies resolves origin by decisionId not instrument soft-join", () => {
    const origin = {
      decisionId: "D1",
      instrumentId: "i1",
      symbol: "AAPL",
    } as DecisionJournalStudyViewV1;
    const later = {
      decisionId: "D-LATER",
      instrumentId: "i1",
      symbol: "AAPL",
    } as DecisionJournalStudyViewV1;
    const byDecision = studiesByDecisionIdMap([origin, later]);
    const byInstrument = studiesByInstrumentMap([later]);
    const pair = pickPositionStudies(
      { instrumentId: "i1", operational: { tradePlanId: "D1" } },
      byDecision,
      byInstrument,
    );
    expect(pair.originStudy?.decisionId).toBe("D1");
    expect(pair.evolutionStudy?.decisionId).toBe("D-LATER");
  });
});
