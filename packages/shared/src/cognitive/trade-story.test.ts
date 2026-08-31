/**
 * V1.42 F4 — TradeStory unit tests (collect / dedupe / fail-closed / labels).
 */

import { describe, expect, it } from "vitest";
import {
  buildTradeStory,
  formatTradeStoryEventLabel,
  tradeStorySurfaceSnapshot,
} from "./trade-story.js";
import type { DecisionJournalEntryV1 } from "./decision-journal.js";

const INST = "inst-aapl";
const ASOF = "2026-08-31T10:00:00.000Z";

describe("TradeStory V1.42 F4", () => {
  it("estudio from study.studiedAt", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      study: {
        studiedAt: ASOF,
        sessionId: "sess-1",
        decisionId: "dec-1",
        tradePlanStatus: "ARMED",
        instrumentId: INST,
      },
    });
    expect(story.events).toHaveLength(1);
    expect(story.events[0]!.kind).toBe("estudio");
    expect(story.events[0]!.label).toBe("Estudio");
    expect(story.decisionId).toBe("dec-1");
  });

  it("tradePlanStatus alone does not invent preparada/trigger (no asOf stamp)", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      study: {
        studiedAt: ASOF,
        sessionId: "sess-1",
        decisionId: "dec-1",
        tradePlanStatus: "TRIGGERED",
        instrumentId: INST,
      },
    });
    expect(story.events.map((e) => e.kind)).toEqual(["estudio"]);
  });

  it("omits caller facts without asOf", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      facts: [
        { kind: "preparada", asOf: "" },
        { kind: "trigger", asOf: "not-a-date" },
        { kind: "propuesta", asOf: "2026-09-05T12:00:00.000Z" },
      ],
    });
    expect(story.events.map((e) => e.kind)).toEqual(["propuesta"]);
  });

  it("sorts by asOf ascending and never drops earlier events", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      facts: [
        { kind: "fill", asOf: "2026-09-05T18:00:00.000Z" },
        { kind: "estudio", asOf: "2026-09-02T08:00:00.000Z" },
        { kind: "propuesta", asOf: "2026-09-05T12:00:00.000Z" },
      ],
    });
    expect(story.events.map((e) => e.kind)).toEqual([
      "estudio",
      "propuesta",
      "fill",
    ]);
  });

  it("dedupes identical kind+asOf+source+refs", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      facts: [
        {
          kind: "fill",
          asOf: ASOF,
          refs: { transactionId: "tx-1" },
          eventId: "a",
        },
        {
          kind: "fill",
          asOf: ASOF,
          refs: { transactionId: "tx-1" },
          eventId: "b",
        },
      ],
    });
    expect(story.events).toHaveLength(1);
  });

  it("maps journal entries to product kinds", () => {
    const entries: DecisionJournalEntryV1[] = [
      {
        schemaVersion: "1.0.0",
        entryId: "e1",
        decisionId: "dec-1",
        instrumentId: INST,
        eventType: "proposal_recorded",
        actor: "system",
        createdAt: "2026-09-05T10:00:00.000Z",
      },
      {
        schemaVersion: "1.0.0",
        entryId: "e2",
        decisionId: "dec-1",
        instrumentId: INST,
        eventType: "human_confirm",
        actor: "human",
        createdAt: "2026-09-05T11:00:00.000Z",
      },
      {
        schemaVersion: "1.0.0",
        entryId: "e3",
        decisionId: "dec-1",
        instrumentId: INST,
        eventType: "gate_evaluated",
        actor: "system",
        createdAt: "2026-09-05T10:30:00.000Z",
      },
    ];
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: "dec-1",
      journalEntries: entries,
    });
    expect(story.events.map((e) => e.kind)).toEqual([
      "propuesta",
      "confirmacion",
    ]);
  });

  it("trailing hint never becomes trailing_applied without revision/fact", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      executionState: {
        instrumentId: INST,
        asOf: ASOF,
        lifecycle: "none",
        orderState: "none",
        fillState: "none",
        protectionState: "none",
        targetState: "none",
        trailingState: "hint",
        reconciliationState: "clean",
        nextAction: null,
        orderId: null,
        intentId: null,
        decisionId: null,
        transactionId: null,
        source: "none",
      },
    });
    expect(story.events.some((e) => e.kind === "trailing_applied")).toBe(false);
  });

  it("formatTradeStoryEventLabel matches §A.6 product copy", () => {
    expect(formatTradeStoryEventLabel("estudio")).toBe("Estudio");
    expect(formatTradeStoryEventLabel("preparada")).toBe("Preparada");
    expect(formatTradeStoryEventLabel("trigger")).toBe("Trigger");
    expect(formatTradeStoryEventLabel("confirmacion")).toBe("Confirmación");
    expect(formatTradeStoryEventLabel("stop_updated")).toBe("Stop actualizado");
    expect(formatTradeStoryEventLabel("cierre")).toBe("Cierre");
  });

  it("tradeStorySurfaceSnapshot exposes kinds and bounds", () => {
    const story = buildTradeStory({
      instrumentId: INST,
      decisionId: "dec-x",
      facts: [
        { kind: "estudio", asOf: "2026-09-01T00:00:00.000Z" },
        { kind: "cierre", asOf: "2026-09-15T00:00:00.000Z" },
      ],
    });
    expect(tradeStorySurfaceSnapshot(story)).toEqual({
      eventKinds: ["estudio", "cierre"],
      firstAsOf: "2026-09-01T00:00:00.000Z",
      lastAsOf: "2026-09-15T00:00:00.000Z",
      count: 2,
      decisionId: "dec-x",
      positionId: null,
    });
  });
});
