import { describe, expect, it, beforeEach } from "vitest";
import {
  DIA_D_EXPERIMENT_TOP_KEY,
  getDiaDExperimentTop1,
  saveDiaDExperimentTop,
} from "@/features/backtests/dia-d-experiment-top";
import {
  buildCounterfactualOos,
  buildDiaDReconciliation,
  resolveDiaDIdentity,
} from "@/features/backtests/dia-d-reconciliation";

describe("dia-d-experiment-top", () => {
  beforeEach(() => {
    localStorage.removeItem(DIA_D_EXPERIMENT_TOP_KEY);
  });

  it("saves and reads F-D #1 without touching other keys", () => {
    saveDiaDExperimentTop({
      instrumentId: "inst-1",
      timeframe: "1d",
      asOfDiaD: "2025-08-01",
      slots: [
        {
          rank: 1,
          label: "SMA D",
          stars: 5,
          score: 1,
          source: "optimized",
          strategyDefinitionId: "s-d",
          strategyType: "sma_crossover",
        },
      ],
      productionTop1AtSave: {
        strategyDefinitionId: "s-hoy",
        label: "RSI hoy",
        strategyType: "rsi_mean_reversion",
      },
    });
    const top1 = getDiaDExperimentTop1("inst-1", "1d", "2025-08-01");
    expect(top1?.strategyDefinitionId).toBe("s-d");
    expect(getDiaDExperimentTop1("inst-1", "1d", "2024-01-01")).toBeNull();
  });
});

describe("dia-d-reconciliation", () => {
  it("detects same id / family / different", () => {
    expect(
      resolveDiaDIdentity(
        { strategyDefinitionId: "a", label: "A", strategyType: "sma" },
        { strategyDefinitionId: "a", label: "A", strategyType: "sma" },
      ),
    ).toBe("same_id");
    expect(
      resolveDiaDIdentity(
        { strategyDefinitionId: "a", label: "A", strategyType: "sma" },
        { strategyDefinitionId: "b", label: "B", strategyType: "sma" },
      ),
    ).toBe("same_family");
    expect(
      resolveDiaDIdentity(
        { strategyDefinitionId: "a", label: "A", strategyType: "sma" },
        { strategyDefinitionId: "b", label: "B", strategyType: "rsi" },
      ),
    ).toBe("different");
  });

  it("maps bands to SAME_* and DRIFT_*", () => {
    expect(
      buildDiaDReconciliation({
        experimentSlot: {
          strategyDefinitionId: "a",
          label: "A",
          strategyType: "sma",
        },
        productionSlot: {
          strategyDefinitionId: "a",
          label: "A",
          strategyType: "sma",
        },
        evidenceBand: "favorable",
        oosReturnPct: 12,
      }).code,
    ).toBe("SAME_CONFIRMED");

    expect(
      buildDiaDReconciliation({
        experimentSlot: {
          strategyDefinitionId: "a",
          label: "A",
          strategyType: "sma",
        },
        productionSlot: {
          strategyDefinitionId: "b",
          label: "B",
          strategyType: "rsi",
        },
        evidenceBand: "favorable",
        oosReturnPct: 8,
      }).code,
    ).toBe("DRIFT_BETTER");

    expect(
      buildDiaDReconciliation({
        experimentSlot: {
          strategyDefinitionId: "a",
          label: "A",
          strategyType: "sma",
        },
        productionSlot: {
          strategyDefinitionId: "b",
          label: "B",
          strategyType: "rsi",
        },
        evidenceBand: "adverse",
        oosReturnPct: -10,
      }).code,
    ).toBe("DRIFT_WORSE");

    expect(
      buildDiaDReconciliation({
        experimentSlot: {
          strategyDefinitionId: "a",
          label: "A",
          strategyType: "sma",
        },
        productionSlot: null,
        evidenceBand: "favorable",
      }).code,
    ).toBe("INCONCLUSIVE");
  });

  it("includes counterfactual delta in summary when ready", () => {
    const r = buildDiaDReconciliation({
      experimentSlot: {
        strategyDefinitionId: "a",
        label: "F-D",
        strategyType: "sma",
      },
      productionSlot: {
        strategyDefinitionId: "b",
        label: "F-hoy",
        strategyType: "rsi",
      },
      evidenceBand: "favorable",
      oosReturnPct: 10,
      counterfactual: buildCounterfactualOos({
        experimentReturnPct: 10,
        productionReturnPct: 4,
        productionTradeCount: 2,
        identity: "different",
        status: "ready",
      }),
    });
    expect(r.code).toBe("DRIFT_BETTER");
    expect(r.counterfactual?.deltaReturnPp).toBe(6);
    expect(r.summary).toMatch(/Contrafactual F-hoy#1/);
    expect(r.summary).toMatch(/\+6\.0 pp/);
  });
});
