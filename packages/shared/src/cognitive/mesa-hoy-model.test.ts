import { describe, expect, it } from "vitest";
import type { DecisionBoardV1 } from "../decision-board.js";
import {
  buildMesaSessionState,
  filterMesaAttentionItems,
  mesaEntriesBlocked,
} from "./mesa-hoy-model.js";
import type { HoyQueueItemV1 } from "./hoy-queue.js";

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
});
