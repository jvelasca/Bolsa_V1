/**
 * V1.42 F4 — mismos hechos → misma TradeStory en Journal / Mercado / Hoy / Operaciones.
 */

import { describe, expect, it } from "vitest";
import {
  buildTradeStory,
  tradeStorySurfaceSnapshot,
  type BuildTradeStoryInputV1,
} from "./trade-story.js";

const ASOF = "2026-08-31T11:00:00.000Z";

function fourSurfaces(input: BuildTradeStoryInputV1) {
  const journal = buildTradeStory(input);
  const mercado = buildTradeStory(input);
  const hoy = buildTradeStory(input);
  const operaciones = buildTradeStory(input);
  return { journal, mercado, hoy, operaciones };
}

describe("sameTradeStoryAcrossSurfaces V1.42 F4", () => {
  it("study + facts → identical snapshot on all surfaces", () => {
    const input: BuildTradeStoryInputV1 = {
      instrumentId: "inst-aapl",
      decisionId: "dec-same",
      asOf: ASOF,
      study: {
        studiedAt: "2026-09-02T08:00:00.000Z",
        sessionId: "sess-same",
        decisionId: "dec-same",
        tradePlanStatus: "ARMED",
        instrumentId: "inst-aapl",
      },
      facts: [
        { kind: "preparada", asOf: "2026-09-03T09:00:00.000Z" },
        { kind: "propuesta", asOf: "2026-09-05T11:00:00.000Z" },
      ],
    };
    const { journal, mercado, hoy, operaciones } = fourSurfaces(input);
    const snap = tradeStorySurfaceSnapshot(journal);
    expect(snap.eventKinds).toEqual(["estudio", "preparada", "propuesta"]);
    expect(tradeStorySurfaceSnapshot(mercado)).toEqual(snap);
    expect(tradeStorySurfaceSnapshot(hoy)).toEqual(snap);
    expect(tradeStorySurfaceSnapshot(operaciones)).toEqual(snap);
  });

  it("empty bags → identical empty story", () => {
    const input: BuildTradeStoryInputV1 = { instrumentId: "inst-x" };
    const { journal, mercado, hoy, operaciones } = fourSurfaces(input);
    const snap = tradeStorySurfaceSnapshot(journal);
    expect(snap.count).toBe(0);
    expect(tradeStorySurfaceSnapshot(mercado)).toEqual(snap);
    expect(tradeStorySurfaceSnapshot(hoy)).toEqual(snap);
    expect(tradeStorySurfaceSnapshot(operaciones)).toEqual(snap);
  });

  it("unknown_order facts → same refs on all surfaces", () => {
    const input: BuildTradeStoryInputV1 = {
      instrumentId: "inst-aapl",
      decisionId: "dec-u",
      facts: [
        {
          kind: "unknown_order",
          asOf: ASOF,
          refs: { orderId: "ORD-same", intentId: "int-same" },
        },
      ],
    };
    const { journal, mercado, hoy, operaciones } = fourSurfaces(input);
    for (const s of [journal, mercado, hoy, operaciones]) {
      expect(s.events[0]!.refs.orderId).toBe("ORD-same");
      expect(s.events[0]!.refs.intentId).toBe("int-same");
      expect(s.events[0]!.label).toMatch(/desconocida/i);
    }
  });
});
