import { describe, expect, it } from "vitest";
import {
  buildMesaEntryQueue,
  deriveMesaRegimeHint,
  filterMesaEntryQueue,
  groupMesaEntryQueue,
  MESA_ENTRY_STATUS_LABEL,
} from "@bolsa/shared";
import type { DecisionBoardV1 } from "@bolsa/shared";

function board(partial: Partial<DecisionBoardV1> = {}): DecisionBoardV1 {
  return {
    accountId: "acc-1",
    generatedAt: "2026-08-25T12:00:00Z",
    buckets: {
      pendingConfirm: 0,
      vetoed: 0,
      deferred: 0,
      autoWaiting: 0,
      total: 0,
    },
    semiF3Queue: [],
    decisionSessions: [
      {
        sessionId: "s1",
        kind: "propose",
        status: "open",
        instrumentId: "i1",
        symbol: "AAA",
        createdAt: "2026-08-25T11:00:00Z",
        gate: "PASS",
        tradePlan: {
          artifactType: "ART-TRADE-PLAN",
          schemaVersion: "1.0.0",
          decisionId: "d1",
          instrumentId: "i1",
          direction: "long",
          status: "ARMED",
          entryReady: false,
          structuralStop: 9,
          entry: 10,
        },
      },
      {
        sessionId: "s2",
        kind: "propose",
        status: "open",
        instrumentId: "i2",
        symbol: "BBB",
        createdAt: "2026-08-25T10:00:00Z",
        gate: "VETO",
        tradePlan: {
          artifactType: "ART-TRADE-PLAN",
          schemaVersion: "1.0.0",
          decisionId: "d2",
          instrumentId: "i2",
          direction: "long",
          status: "BLOCKED",
          entryReady: false,
          structuralStop: 9,
          entry: 10,
        },
      },
    ],
    ...partial,
  };
}

describe("mesa-entry-queue", () => {
  it("maps TradePlan status to Spanish labels", () => {
    expect(MESA_ENTRY_STATUS_LABEL.WATCH).toBe("Vigilar");
    expect(MESA_ENTRY_STATUS_LABEL.TRIGGERED).toBe("Propuesto");
    expect(MESA_ENTRY_STATUS_LABEL.EXPIRED).toBe("Descartado");
  });

  it("buildMesaEntryQueue projects symbols and gates", () => {
    const rows = buildMesaEntryQueue(board());
    expect(
      rows.some((r) => r.symbol === "AAA" && r.statusLabel === "Preparado"),
    ).toBe(true);
    expect(rows.some((r) => r.symbol === "BBB" && r.status === "BLOCKED")).toBe(
      true,
    );
  });

  it("groupMesaEntryQueue omits empty buckets", () => {
    const groups = groupMesaEntryQueue(buildMesaEntryQueue(board()));
    expect(groups.every((g) => g.items.length > 0)).toBe(true);
    expect(groups.find((g) => g.status === "ARMED")?.label).toBe("Preparado");
  });

  it("filterMesaEntryQueue by gate and symbol", () => {
    const rows = buildMesaEntryQueue(board());
    const vetoOnly = filterMesaEntryQueue(rows, { gate: "VETO" });
    expect(vetoOnly.every((r) => r.gate.toUpperCase() === "VETO")).toBe(true);
    expect(vetoOnly.some((r) => r.symbol === "BBB")).toBe(true);

    const aaa = filterMesaEntryQueue(rows, { symbolQuery: "aaa" });
    expect(aaa).toHaveLength(1);
    expect(aaa[0]?.symbol).toBe("AAA");
  });

  it("filterMesaEntryQueue by status bucket", () => {
    const rows = buildMesaEntryQueue(board());
    const armed = filterMesaEntryQueue(rows, { statuses: ["ARMED"] });
    expect(armed.every((r) => r.status === "ARMED")).toBe(true);
  });

  it("deriveMesaRegimeHint from veto sessions", () => {
    const hint = deriveMesaRegimeHint(
      board({
        buckets: {
          pendingConfirm: 0,
          vetoed: 1,
          deferred: 0,
          autoWaiting: 0,
          total: 1,
        },
        decisionSessions: [
          {
            sessionId: "s-v",
            kind: "propose",
            status: "open",
            instrumentId: "i1",
            symbol: "V",
            createdAt: "2026-08-25T11:00:00Z",
            gate: "VETO",
            wyckoffSpringAnchor: { phase: "accumulation" },
          },
        ],
      }),
    );
    expect(hint).toBe("fase accumulation");
  });
});
