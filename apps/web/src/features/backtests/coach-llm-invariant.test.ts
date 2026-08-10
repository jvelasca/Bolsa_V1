/**
 * CORE A — invariantes: LLM no corona TOP; confirm ignorado; allowlist.
 */

import { describe, expect, it } from "vitest";
import {
  auditFindingsFromLlmPayload,
  filterLlmFindingsToAllowlist,
  readPriorCoachAuditHint,
  runCoachDualAudit,
} from "@/features/backtests/coach-dual-audit";
import {
  mergeLlmIntoDeepCoach,
  sanitizeLlmDeepCoachPayload,
  type DeepTechnicalCoachNote,
} from "@/features/backtests/backtest-deep-coach";
import type { ExplorePresetRow } from "@/features/backtests/backtest-explore-value";

function row(
  partial: Partial<ExplorePresetRow> &
    Pick<ExplorePresetRow, "strategyType" | "label">,
): ExplorePresetRow {
  return {
    category: "trend",
    categoryLabel: "Tendencia",
    status: "ok",
    totalReturnPct: 20,
    excessReturnPct: 5,
    maxDrawdownPct: 12,
    tradeCount: 20,
    barCount: 500,
    sharpeRatio: 0.8,
    buyHoldReturnPct: 15,
    periodReturns: { early: 5, mid: 6, late: 10 },
    ...partial,
  };
}

describe("CORE A · LLM no corona TOP", () => {
  it("ignores confirm and invented types outside allowlist", () => {
    const findings = auditFindingsFromLlmPayload(
      {
        audit: {
          findings: [
            {
              strategyType: "sma_crossover",
              action: "confirm",
              reason: "love it",
            },
            {
              strategyType: "invented_alpha",
              action: "veto",
              reason: "halluc",
            },
            {
              strategyType: "rsi_mean_reversion",
              action: "veto",
              reason: "ok",
            },
          ],
        },
      },
      "llm",
    );
    expect(findings.every((f) => f.action !== "confirm")).toBe(true);
    const allowed = filterLlmFindingsToAllowlist(findings, [
      "sma_crossover",
      "rsi_mean_reversion",
    ]);
    expect(allowed.map((f) => f.strategyType)).toEqual(["rsi_mean_reversion"]);
  });

  it("mergeLlmIntoDeepCoach keeps recommendation types (prose only)", () => {
    const local: DeepTechnicalCoachNote = {
      headline: "Local",
      analysis: ["a"],
      recommendations: [
        {
          rank: 1,
          row: row({ strategyType: "sma_crossover", label: "SMA" }),
          score: 80,
          stars: 4,
          starsCapped: false,
          reasons: ["x"],
        },
      ],
      outlook: ["o"],
      disclaimer: "d",
      contextLabel: "CTX",
    };
    const merged = mergeLlmIntoDeepCoach(local, {
      headline: "IA dice otra cosa",
      analysis: ["narrativa"],
      outlook: ["futuro"],
      disclaimer: "disc",
    });
    expect(merged.recommendations[0]?.row.strategyType).toBe("sma_crossover");
    expect(merged.headline).toBe("IA dice otra cosa");
  });

  it("sanitizeLlmDeepCoachPayload rejects corrupt shapes", () => {
    expect(sanitizeLlmDeepCoachPayload({ headline: 1 })).toBeNull();
    expect(sanitizeLlmDeepCoachPayload({ analysis: "x" })).toBeNull();
    expect(
      sanitizeLlmDeepCoachPayload({ headline: "ok", analysis: ["a"] })
        ?.headline,
    ).toBe("ok");
  });

  it("local audit TOP types unchanged when LLM findings empty", () => {
    const rows = [
      row({
        strategyType: "sma_crossover",
        label: "SMA",
        periodReturns: { early: 4, mid: 5, late: 12 },
        excessReturnPct: 8,
      }),
      row({
        strategyType: "rsi_mean_reversion",
        label: "RSI",
        category: "mean_reversion",
        categoryLabel: "Reversión",
        periodReturns: { early: 3, mid: 4, late: 9 },
        excessReturnPct: 6,
        maxDrawdownPct: 10,
      }),
      row({
        strategyType: "macd_signal_cross",
        label: "MACD",
        periodReturns: { early: 2, mid: 3, late: 7 },
        excessReturnPct: 4,
      }),
    ];
    const ctx = {
      symbol: "TEF",
      timeframe: "1d" as const,
      horizon: "swing" as const,
      riskTolerance: "moderate" as const,
      evidenceLevel: "in_sample_only" as const,
    };
    const without = runCoachDualAudit({ rows, ctx });
    const withEmpty = runCoachDualAudit({ rows, ctx, llmFindings: [] });
    expect(without.recommendations.map((r) => r.row.strategyType)).toEqual(
      withEmpty.recommendations.map((r) => r.row.strategyType),
    );
  });

  it("reads prior dualAudit hint from coachFacts", () => {
    expect(readPriorCoachAuditHint(null)).toBeNull();
    expect(readPriorCoachAuditHint({})).toBeNull();
    const hint = readPriorCoachAuditHint({
      coachPass: "post_lab",
      dualAudit: { confidence: "weak", softWeak: true },
    });
    expect(hint).toEqual({
      confidence: "weak",
      softWeak: true,
      coachPass: "post_lab",
    });
  });
});
