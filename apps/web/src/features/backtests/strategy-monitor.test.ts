import { describe, expect, it } from "vitest";
import type { InvestmentAccountDto } from "@bolsa/shared";
import {
  buildStrategyMonitorRow,
  findLastFinalistsPropose,
  findPaperForTopSlots,
  isOpenAnalysisQuery,
  sliceMonitorInstruments,
  strategyMonitorChecklistHref,
} from "@/features/backtests/strategy-monitor";
import type { SupervisedQueueItem } from "@/stores/supervised-f3-queue-store";

function paper(
  partial: Partial<InvestmentAccountDto> & { id: string },
): InvestmentAccountDto {
  return {
    userId: null,
    name: "Paper",
    description: null,
    type: "paper",
    status: "active",
    currency: "EUR",
    baseCurrency: "EUR",
    initialDeposit: 10_000,
    leverage: 1,
    marginCallLevelPct: null,
    isDefault: false,
    settings: null,
    strategyDefinitionId: null,
    sourceBacktestRunId: null,
    labEvidence: null,
    createdAt: "",
    updatedAt: "",
    lastActivityAt: null,
    ...partial,
  };
}

describe("strategy-monitor helpers", () => {
  it("caps instrument list", () => {
    const ids = Array.from({ length: 50 }, (_, i) => ({
      id: `i${i}`,
      symbol: `S${i}`,
    }));
    expect(sliceMonitorInstruments(ids)).toHaveLength(40);
  });

  it("joins paper by strategyDefinitionId on TOP slots", () => {
    const accounts = [
      paper({
        id: "p1",
        strategyDefinitionId: "strat-a",
        labEvidence: { kind: "holdout" },
      }),
      paper({ id: "p2", strategyDefinitionId: "strat-other" }),
    ];
    expect(findPaperForTopSlots(accounts, ["strat-a"])?.id).toBe("p1");
    expect(findPaperForTopSlots(accounts, ["missing"])).toBeNull();
  });

  it("prefers DEMO simulated over paper broker type", () => {
    const accounts = [
      paper({
        id: "broker-paper",
        type: "paper",
        strategyDefinitionId: "strat-a",
      }),
      paper({
        id: "demo",
        type: "simulated",
        name: "DEMO",
        strategyDefinitionId: "strat-a",
      }),
    ];
    expect(findPaperForTopSlots(accounts, ["strat-a"])?.id).toBe("demo");
  });

  it("ignores closed DEMO/paper accounts", () => {
    const accounts = [
      paper({
        id: "closed",
        type: "simulated",
        status: "closed",
        strategyDefinitionId: "strat-a",
      }),
      paper({
        id: "live",
        type: "simulated",
        strategyDefinitionId: "strat-a",
      }),
    ];
    expect(findPaperForTopSlots(accounts, ["strat-a"])?.id).toBe("live");
  });

  it("finds latest finalists propose by symbol", () => {
    const queue: SupervisedQueueItem[] = [
      {
        id: "q1",
        enqueuedAt: "2026-01-01",
        symbol: "SAN",
        origin: "scan",
        payload: { symbol: "SAN", action: "wait" } as never,
      },
      {
        id: "q2",
        enqueuedAt: "2026-01-02",
        symbol: "SAN",
        origin: "finalists",
        payload: { symbol: "SAN", action: "recommend_long" } as never,
      },
    ];
    expect(findLastFinalistsPropose(queue, "san")?.id).toBe("q2");
    expect(findLastFinalistsPropose(queue, "BBVA")).toBeNull();
  });

  it("builds row + checklist href with openAnalysis", () => {
    const row = buildStrategyMonitorRow({
      instrument: { id: "inst-1", symbol: "SAN", name: "Santander" },
      timeframe: "1d",
      top: {
        id: "top-1",
        instrumentId: "inst-1",
        timeframe: "1d",
        status: "active",
        version: 2,
        evidenceLevel: "lab_validated",
        slots: [
          {
            rank: 1,
            label: "SMA opt",
            stars: 4,
            score: 1,
            source: "optimized",
            strategyDefinitionId: "strat-a",
            runId: "run-9",
          },
        ],
        createdAt: "",
        updatedAt: "",
      },
      accounts: [
        paper({
          id: "p1",
          strategyDefinitionId: "strat-a",
          labEvidence: { kind: "cpcv", pbo: 0.2 },
        }),
      ],
      queue: [],
    });
    expect(row.topStatus).toBe("active");
    expect(row.slot1RunId).toBe("run-9");
    expect(row.paperAccount?.id).toBe("p1");
    const href = strategyMonitorChecklistHref("inst-1", "run-9");
    expect(href).toContain("runId=run-9");
    expect(href).toContain("focus=detail");
    expect(href).toContain("openAnalysis=1");
  });
});

describe("isOpenAnalysisQuery", () => {
  it("accepts 1/true/yes", () => {
    expect(isOpenAnalysisQuery("1")).toBe(true);
    expect(isOpenAnalysisQuery("true")).toBe(true);
    expect(isOpenAnalysisQuery("YES")).toBe(true);
    expect(isOpenAnalysisQuery("0")).toBe(false);
    expect(isOpenAnalysisQuery(null)).toBe(false);
  });
});
