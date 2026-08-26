import { describe, expect, it } from "vitest";
import {
  buildMesaDecisionAlerts,
  buildRelevantJournalDelta,
  filterRelevantDeltaFields,
} from "./decision-journal-relevant-delta.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";

function study(
  partial: Partial<DecisionJournalStudyViewV1>,
): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
    accountId: "a",
    instrumentId: "i1",
    symbol: "AAPL",
    name: "Apple",
    studiedAt: "2026-08-26T10:00:00Z",
    status: "active",
    opinion: "bullish",
    strength: 8,
    vigencia: "valid",
    hasOperationalPlan: true,
    entry: 100,
    stop: 95,
    target1: 110,
    target2: null,
    expectedRR: 2,
    riskAmount: 500,
    tradePlanStatus: "ARMED",
    invalidation: [],
    ...partial,
  } as DecisionJournalStudyViewV1;
}

describe("buildRelevantJournalDelta", () => {
  it("detects opinion change conclusion", () => {
    const prev = study({ opinion: "bullish", strength: 8 });
    const next = study({ opinion: "neutral", strength: 6.5, sessionId: "s2" });
    const delta = buildRelevantJournalDelta(next, prev);
    expect(delta.hasRelevantChange).toBe(true);
    expect(delta.conclusion).toContain("opinión");
  });

  it("no relevant change when identical", () => {
    const s = study({});
    const delta = buildRelevantJournalDelta(s, { ...s, sessionId: "s0" });
    expect(delta.hasRelevantChange).toBe(false);
    expect(delta.conclusion).toBe("Sin cambios relevantes en la tesis.");
  });

  it("first thesis returns Primera tesis registrada", () => {
    const delta = buildRelevantJournalDelta(study({}), null);
    expect(delta.isFirst).toBe(true);
    expect(delta.hasRelevantChange).toBe(false);
    expect(delta.conclusion).toBe("Primera tesis registrada.");
  });

  it("strength-only change produces fuerza conclusion", () => {
    const prev = study({ strength: 8 });
    const next = study({ strength: 5.5, sessionId: "s2" });
    const delta = buildRelevantJournalDelta(next, prev);
    expect(delta.hasRelevantChange).toBe(true);
    expect(delta.conclusion).toContain("fuerza");
  });

  it("stop change is relevant but entry-only is filtered out", () => {
    const prev = study({ entry: 100, stop: 95 });
    const entryOnly = study({ entry: 102, stop: 95, sessionId: "s2" });
    const entryDelta = buildRelevantJournalDelta(entryOnly, prev);
    expect(entryDelta.hasRelevantChange).toBe(false);

    const stopChanged = study({ entry: 100, stop: 93, sessionId: "s3" });
    const stopDelta = buildRelevantJournalDelta(stopChanged, prev);
    expect(stopDelta.hasRelevantChange).toBe(true);
    expect(stopDelta.relevantFields.some((f) => f.label === "Stop")).toBe(true);
  });

  it("invalidation change is relevant", () => {
    const prev = study({ invalidation: ["RSI < 30"] });
    const next = study({
      invalidation: ["RSI < 30", "Volumen bajo"],
      sessionId: "s2",
    });
    const delta = buildRelevantJournalDelta(next, prev);
    expect(delta.hasRelevantChange).toBe(true);
    expect(delta.relevantFields.some((f) => f.label === "Invalidación")).toBe(
      true,
    );
  });
});

describe("filterRelevantDeltaFields", () => {
  it("keeps only labels in RELEVANT set", () => {
    const filtered = filterRelevantDeltaFields([
      { bucket: "plan", label: "Entrada", before: "100", after: "102" },
      { bucket: "plan", label: "Stop", before: "95", after: "93" },
    ]);
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.label).toBe("Stop");
  });
});

describe("buildMesaDecisionAlerts", () => {
  it("emits incident and data_stale system alerts from persisted inputs", () => {
    const alerts = buildMesaDecisionAlerts({
      incidentCount: 2,
      dataStale: true,
    });
    expect(
      alerts.some((a) => a.kind === "incident" && a.severity === "critical"),
    ).toBe(true);
    expect(alerts.some((a) => a.kind === "data_stale")).toBe(true);
  });

  it("derives position and study alerts without extra fetch", () => {
    const alerts = buildMesaDecisionAlerts({
      positions: [
        {
          symbol: "AAPL",
          lastPrice: 96,
          operational: {
            currentStop: 95.5,
            target1: 95,
            exitPlan: { suggestedAction: "protect" },
          },
        },
      ],
      studies: [
        {
          instrumentId: "i2",
          symbol: "MSFT",
          strength: 3.2,
          tradePlanStatus: "TRIGGERED",
        },
      ],
      protectionDiscrepancies: [{ symbol: "TSLA" }],
    });
    const kinds = alerts.map((a) => a.kind);
    expect(kinds).toContain("stop_near");
    expect(kinds).toContain("tp1_reached");
    expect(kinds).toContain("protection_discrepancy");
    expect(kinds).toContain("thesis_weak");
    expect(kinds).toContain("trigger_reached");
    expect(alerts.filter((a) => a.symbol === "TSLA")).toHaveLength(1);
  });

  it("returns empty when no persisted signals", () => {
    expect(buildMesaDecisionAlerts({})).toEqual([]);
  });
});
