import { beforeEach, describe, expect, it } from "vitest";
import { recordSemiConfirmMandate } from "@/features/trading/semi-confirm-mandate";
import {
  MANDATE_TENURES_KEY,
  MANDATE_TRADE_LINKS_KEY,
  getOpenMandateTenure,
  listOpenMandateTenures,
  listTradeLinksForMandate,
} from "@/features/platform/operating-mandate";
import { STRATEGY_ADOPTION_KEY } from "@/features/platform/strategy-adoption";
import type { SupervisedProposePayload } from "@/stores/supervised-f3-queue-store";

function basePayload(
  patch: Partial<SupervisedProposePayload> = {},
): SupervisedProposePayload {
  return {
    artifactType: "ART-RECOMMENDATION",
    schemaVersion: "1.0.0",
    recommendationId: "REC-test",
    decisionId: "DEC-test",
    instrumentId: "inst-acs",
    symbol: "ACS.MC",
    action: "recommend_long",
    suggestedQuantity: 10,
    metrics: {
      confidence: 0.5,
      consensus: 0.5,
      evidenceStrength: 0.5,
      stability: 0.5,
      conviction: 0.5,
    },
    status: "awaiting_human",
    createdAt: "2026-08-03T12:00:00.000Z",
    decisionPackage: {
      strategyOrSignalRef: "strat-sma-1",
      strategyLabel: "SMA Finalista",
    },
    ...patch,
  } as SupervisedProposePayload;
}

describe("recordSemiConfirmMandate", () => {
  beforeEach(() => {
    localStorage.removeItem(MANDATE_TENURES_KEY);
    localStorage.removeItem(MANDATE_TRADE_LINKS_KEY);
    localStorage.removeItem(STRATEGY_ADOPTION_KEY);
  });

  it("opens tenure and links trade on executed intent", () => {
    const r = recordSemiConfirmMandate({
      accountId: "acc-1",
      payload: basePayload(),
      intentStatus: "executed",
      trade: { status: "filled", transactionId: "tx-1" },
    });
    expect(r.mandateTenureId).toBeTruthy();
    expect(r.linked).toBe(true);
    const open = getOpenMandateTenure("inst-acs", "acc-1");
    expect(open?.reason).toBe("propose_accepted");
    expect(listTradeLinksForMandate(open!.id)).toHaveLength(1);
    expect(listOpenMandateTenures("acc-1")).toHaveLength(1);
  });

  it("ignores non-execute statuses", () => {
    const r = recordSemiConfirmMandate({
      accountId: "acc-1",
      payload: basePayload(),
      intentStatus: "rejected",
      trade: null,
    });
    expect(r.mandateTenureId).toBeNull();
    expect(listOpenMandateTenures("acc-1")).toHaveLength(0);
  });
});
