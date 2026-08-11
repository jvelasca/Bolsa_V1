import { beforeEach, describe, expect, it } from "vitest";
import type { BacktestRunDetailDto, ResearchTrialDto } from "@bolsa/shared";
import {
  buildOosEvidenceForAdopt,
  extractOosEvidenceFromOptimizeResult,
  extractOosEvidenceFromTrial,
  oosEvidenceToPaperLabSnapshot,
  readStashedOosEvidence,
  resolveOosEvidence,
  stashOosEvidenceForStrategy,
} from "@/features/backtests/backtest-oos-evidence";
import { buildPaperGate } from "@/features/backtests/backtest-paper-gate";

function trial(partial: Partial<ResearchTrialDto>): ResearchTrialDto {
  return {
    id: "t1",
    instrumentId: "i1",
    params: {},
    isMetrics: {},
    proposedBy: "grid",
    kContribution: 1,
    createdAt: "2026-07-26T00:00:00Z",
    ...partial,
  };
}

function runDetail(
  partial: Partial<BacktestRunDetailDto> = {},
): BacktestRunDetailDto {
  return {
    id: "run-1",
    instrumentId: "inst-1",
    symbol: "IBE.MC",
    name: "Test",
    strategyType: "sma_crossover",
    initialCash: 10_000,
    finalEquity: 11_000,
    totalReturnPct: 10,
    maxDrawdownPct: 12,
    tradeCount: 8,
    winCount: 5,
    barCount: 500,
    firstDate: "2020-01-01",
    lastDate: "2024-01-01",
    createdAt: "2026-07-26T00:00:00Z",
    trades: [],
    ...partial,
  } as BacktestRunDetailDto;
}

describe("OOS evidence for checklist / adopt", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("reads hold-out blocks from a research trial", () => {
    const evidence = extractOosEvidenceFromTrial(
      trial({
        blocks: {
          oosMetrics: {
            score: 4.2,
            totalReturnPct: 3,
            maxDrawdownPct: 2,
            tradeCount: 3,
          },
        },
      }),
    );
    expect(evidence.kind).toBe("holdout");
    expect(evidence.oosScore).toBe(4.2);
  });

  it("reads walk-forward summary from trial blocks", () => {
    const evidence = extractOosEvidenceFromTrial(
      trial({
        blocks: {
          walkForward: {
            meanOosScore: 1.5,
            stdOosScore: 0.2,
            nFolds: 3,
            walkForwardEfficiency: 0.62,
            oosCv: 0.13,
            positiveOosFoldShare: 1,
          },
        },
      }),
    );
    expect(evidence.kind).toBe("walkforward");
    expect(evidence.meanOosScore).toBe(1.5);
    expect(evidence.nFolds).toBe(3);
    expect(evidence.walkForwardEfficiency).toBe(0.62);
    expect(evidence.oosCv).toBe(0.13);
  });

  it("extracts from optimize API result", () => {
    const evidence = extractOosEvidenceFromOptimizeResult({
      walkForward: {
        meanOosScore: 2.25,
        stdOosScore: 0.5,
        nFolds: 3,
        walkForwardEfficiency: 0.7,
        positiveOosFoldShare: 1,
      },
    });
    expect(evidence.kind).toBe("walkforward");
    expect(evidence.oosScore).toBe(2.25);
    expect(evidence.walkForwardEfficiency).toBe(0.7);
  });

  it("reads CPCV blocks and prefers them over hold-out", () => {
    const evidence = extractOosEvidenceFromTrial(
      trial({
        blocks: {
          cpcv: {
            meanOosScore: 3.1,
            pathCount: 10,
            walkForwardEfficiency: 0.55,
            oosCv: 0.4,
            positiveOosFoldShare: 0.7,
          },
          labEvidence: { wfeSource: "lab_score", mode: "cpcv" },
          oosMetrics: { score: 1 },
        },
      }),
    );
    expect(evidence.kind).toBe("cpcv");
    expect(evidence.pathCount).toBe(10);
    expect(evidence.walkForwardEfficiency).toBe(0.55);
    expect(evidence.wfeSource).toBe("lab_score");
  });

  it("extracts CPCV from optimize API result", () => {
    const evidence = extractOosEvidenceFromOptimizeResult({
      cpcv: {
        meanOosScore: 1.1,
        pathCount: 6,
        walkForwardEfficiency: 0.8,
      },
    });
    expect(evidence.kind).toBe("cpcv");
    expect(evidence.walkForwardEfficiency).toBe(0.8);
  });

  it("stashes and resolves evidence by strategy id", () => {
    stashOosEvidenceForStrategy("strat-1", {
      kind: "holdout",
      oosScore: 7,
      oosReturnPct: 5,
    });
    expect(readStashedOosEvidence("strat-1")?.oosScore).toBe(7);
    expect(resolveOosEvidence({ strategyId: "strat-1" }).kind).toBe("holdout");
    expect(
      resolveOosEvidence({ trial: null, strategyId: "missing" }).kind,
    ).toBe("none");
  });

  it("prefers trial ledger over session stash", () => {
    stashOosEvidenceForStrategy("strat-2", { kind: "holdout", oosScore: 1 });
    const evidence = resolveOosEvidence({
      strategyId: "strat-2",
      trial: trial({
        blocks: {
          walkForward: { meanOosScore: 9, nFolds: 2 },
        },
      }),
    });
    expect(evidence.kind).toBe("walkforward");
    expect(evidence.meanOosScore).toBe(9);
  });

  it("adopt stash keeps CPCV + PBO + Edge even when row has path oosMetrics", () => {
    const evidence = buildOosEvidenceForAdopt(
      {
        cpcv: {
          meanOosScore: 2.4,
          pathCount: 10,
          walkForwardEfficiency: 0.65,
          oosCv: 0.25,
          positiveOosFoldShare: 0.7,
          pbo: { pbo: 0.55 },
        },
        pbo: { pbo: 0.55 },
        edgeReport: {
          credibility: 58,
          band: "uncertain",
          suite: { monteCarloPValue: 0.02, dsr: 0.7 },
        },
        trials: [{ oosMetrics: { score: 9.9, totalReturnPct: 12 } }],
      },
      { oosMetrics: { score: 9.9, totalReturnPct: 12 } },
    );
    expect(evidence.kind).toBe("cpcv");
    expect(evidence.meanOosScore).toBe(2.4);
    expect(evidence.pbo).toBe(0.55);
    expect(evidence.edgeBand).toBe("uncertain");
    expect(evidence.credibility).toBe(58);

    stashOosEvidenceForStrategy("strat-adopt-cpcv", evidence);
    const resolved = resolveOosEvidence({ strategyId: "strat-adopt-cpcv" });
    expect(resolved.kind).toBe("cpcv");
    expect(resolved.pbo).toBe(0.55);

    const gate = buildPaperGate({
      detail: runDetail({ strategyDefinitionId: "strat-adopt-cpcv" }),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: resolved,
    });
    expect(gate.checks.find((c) => c.id === "oos_validation")?.status).toBe(
      "pass",
    );
    expect(gate.checks.find((c) => c.id === "pbo")?.status).toBe("warn");
    expect(gate.checks.find((c) => c.id === "edge_report")?.status).toBe(
      "pass",
    );
  });

  it("maps OOS evidence to paper lab deploy snapshot", () => {
    const snap = oosEvidenceToPaperLabSnapshot(
      {
        kind: "cpcv",
        meanOosScore: 2,
        walkForwardEfficiency: 0.6,
        pbo: 0.4,
        edgeBand: "uncertain",
      },
      { sourceBacktestRunId: "run-1", trialId: "t-1" },
    );
    expect(snap.kind).toBe("cpcv");
    expect(snap.pbo).toBe(0.4);
    expect(snap.sourceBacktestRunId).toBe("run-1");
    expect(snap.note).toMatch(/not a production gate/i);
  });

  it("hold-out adopt merges EdgeReport fields onto row OOS scores", () => {
    const evidence = buildOosEvidenceForAdopt(
      {
        edgeReport: {
          credibility: 40,
          band: "luck",
          suite: { monteCarloPValue: 0.4, dsr: 0.1 },
        },
        trials: [{ oosMetrics: { score: 3, totalReturnPct: 2 } }],
      },
      { oosMetrics: { score: 4.5, totalReturnPct: 3.2 } },
    );
    expect(evidence.kind).toBe("holdout");
    expect(evidence.oosScore).toBe(4.5);
    expect(evidence.edgeBand).toBe("luck");
    expect(evidence.monteCarloPValue).toBe(0.4);
  });
});
