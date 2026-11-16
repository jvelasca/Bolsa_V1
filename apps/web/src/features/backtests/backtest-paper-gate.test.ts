import { describe, expect, it } from "vitest";
import type { BacktestRunDetailDto } from "@bolsa/shared";
import {
  buildPaperGate,
  resolvePaperNetEvidence,
} from "@/features/backtests/backtest-paper-gate";

function detail(
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

describe("buildPaperGate oos_validation", () => {
  it("warns when there is no OOS evidence", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 2,
      buyHoldReturnPct: 8,
      oosEvidence: { kind: "none" },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("warn");
    expect(oos?.requiresAck).toBe(true);
  });

  it("passes hold-out with positive OOS score", () => {
    const gate = buildPaperGate({
      detail: detail({ strategyDefinitionId: "strat-1" }),
      excessReturnPct: 3,
      buyHoldReturnPct: 7,
      oosEvidence: { kind: "holdout", oosScore: 4.2, oosReturnPct: 5 },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("pass");
    expect(oos?.requiresAck).toBeFalsy();
  });

  it("warns walk-forward when mean OOS is negative", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 1,
      buyHoldReturnPct: 0,
      oosEvidence: {
        kind: "walkforward",
        meanOosScore: -2.5,
        stdOosScore: 1.1,
        nFolds: 3,
      },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("warn");
    expect(oos?.detail).toMatch(/media OOS negativa/i);
  });

  it("warns walk-forward when WFE is weak even if mean OOS > 0", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: {
        kind: "walkforward",
        meanOosScore: 3,
        stdOosScore: 0.4,
        nFolds: 3,
        walkForwardEfficiency: 0.35,
        oosCv: 0.2,
        positiveOosFoldShare: 1,
      },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("warn");
    expect(oos?.detail).toMatch(/WFE/i);
  });

  it("warns when PBO is elevated", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 1,
      buyHoldReturnPct: 0,
      oosEvidence: {
        kind: "cpcv",
        meanOosScore: 2,
        pathCount: 10,
        walkForwardEfficiency: 0.6,
        positiveOosFoldShare: 0.8,
        oosCv: 0.3,
        pbo: 0.62,
      },
    });
    const pbo = gate.checks.find((c) => c.id === "pbo");
    expect(pbo?.status).toBe("warn");
    expect(pbo?.detail).toMatch(/PBO/i);
  });

  it("warns on EdgeReport lab band luck", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: {
        kind: "holdout",
        oosScore: 3,
        credibility: 40,
        edgeBand: "luck",
        monteCarloPValue: 0.4,
        dsr: 0.2,
      },
    });
    const edge = gate.checks.find((c) => c.id === "edge_report");
    expect(edge?.status).toBe("warn");
    expect(edge?.requiresAck).toBe(true);
  });

  it("passes EdgeReport lab when band not luck and MC ok", () => {
    const gate = buildPaperGate({
      detail: detail({ strategyDefinitionId: "s1" }),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: {
        kind: "walkforward",
        meanOosScore: 4,
        nFolds: 3,
        walkForwardEfficiency: 0.75,
        positiveOosFoldShare: 1,
        oosCv: 0.2,
        credibility: 72,
        edgeBand: "uncertain",
        monteCarloPValue: 0.02,
        dsr: 0.7,
      },
    });
    const edge = gate.checks.find((c) => c.id === "edge_report");
    expect(edge?.status).toBe("pass");
  });

  it("passes CPCV with healthy WFE", () => {
    const gate = buildPaperGate({
      detail: detail({ strategyDefinitionId: "strat-cpcv" }),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: {
        kind: "cpcv",
        meanOosScore: 3,
        pathCount: 10,
        walkForwardEfficiency: 0.7,
        oosCv: 0.2,
        positiveOosFoldShare: 0.8,
        wfeSource: "lab_score",
      },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("pass");
    expect(oos?.label).toMatch(/CPCV/i);
  });

  it("passes walk-forward with healthy WFE and stability", () => {
    const gate = buildPaperGate({
      detail: detail({ strategyDefinitionId: "strat-wf" }),
      excessReturnPct: 2,
      buyHoldReturnPct: 1,
      oosEvidence: {
        kind: "walkforward",
        meanOosScore: 4,
        stdOosScore: 0.5,
        nFolds: 3,
        walkForwardEfficiency: 0.72,
        oosCv: 0.12,
        positiveOosFoldShare: 1,
      },
    });
    const oos = gate.checks.find((c) => c.id === "oos_validation");
    expect(oos?.status).toBe("pass");
    expect(oos?.detail).toMatch(/WFE 0\.72/i);
  });

  it("still hard-blocks when there are no trades", () => {
    const gate = buildPaperGate({
      detail: detail({
        tradeCount: 0,
        winCount: 0,
        strategyDefinitionId: "s1",
      }),
      excessReturnPct: 5,
      buyHoldReturnPct: 1,
      oosEvidence: { kind: "holdout", oosScore: 9 },
    });
    expect(gate.canDeploy).toBe(false);
    expect(gate.hardBlockers).toContain("has_trades");
  });

  it("hard-blocks deploy without saved StrategyDefinition (API requires it)", () => {
    const gate = buildPaperGate({
      detail: detail(),
      excessReturnPct: 5,
      buyHoldReturnPct: 1,
      oosEvidence: { kind: "holdout", oosScore: 9 },
    });
    expect(gate.canDeploy).toBe(false);
    expect(gate.hardBlockers).toContain("saved_strategy");
  });
});

const GOOD_NET = {
  returnBasis: "net" as const,
  netReturnPct: 6.5,
  expectancyCurrency: 12.4,
  roundTripCostBps: 32,
  netTradeCount: 18,
};

function goodDetail() {
  return detail({ strategyDefinitionId: "strat-net" });
}

function goodOos() {
  return { kind: "holdout" as const, oosScore: 4.2, oosReturnPct: 5 };
}

describe("buildPaperGate net profit (P1)", () => {
  it("pasa con medición neta, fricción suficiente y esperanza positiva", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 7,
      oosEvidence: goodOos(),
      netEvidence: GOOD_NET,
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("pass");
    expect(net?.detail).toMatch(/32 bps/);
    expect(gate.checks.find((c) => c.id === "expectancy")?.status).toBe("pass");
    expect(gate.canDeploy).toBe(true);
  });

  it("bloquea un run bruto (returnBasis gross) aunque gane in-sample", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 30,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, returnBasis: "gross", netReturnPct: null },
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("fail");
    expect(gate.hardBlockers).toContain("net_profit");
    expect(gate.canDeploy).toBe(false);
  });

  it("bloquea retorno neto no positivo tras costes", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, netReturnPct: -0.4 },
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("fail");
    expect(net?.detail).toMatch(/Retorno neto -0\.4%/);
  });

  it("bloquea fricción declarada por debajo del suelo de 22 bps", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, roundTripCostBps: 10 },
    });
    expect(gate.checks.find((c) => c.id === "net_profit")?.status).toBe("fail");
  });

  it("avisa (no fabrica) si no declara la fricción aplicada", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, roundTripCostBps: null },
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("warn");
    expect(net?.requiresAck).toBe(true);
  });

  it("avisa con ack en runs anteriores al gate neto (hueco ≠ 0)", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("warn");
    expect(net?.requiresAck).toBe(true);
    expect(net?.detail).toMatch(/anterior al gate P1/i);
    expect(gate.checks.some((c) => c.id === "expectancy")).toBe(false);
  });

  it("avisa si dice medir neto pero no trae retorno neto", () => {
    const gate = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, netReturnPct: null },
    });
    const net = gate.checks.find((c) => c.id === "net_profit");
    expect(net?.status).toBe("warn");
    expect(net?.detail).toMatch(/no trae el retorno neto/i);
  });

  it("avisa con esperanza no positiva o no medida", () => {
    const negative = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, expectancyCurrency: -1.2 },
    });
    expect(negative.checks.find((c) => c.id === "expectancy")?.status).toBe(
      "warn",
    );

    const absent = buildPaperGate({
      detail: goodDetail(),
      excessReturnPct: 3,
      buyHoldReturnPct: 1,
      oosEvidence: goodOos(),
      netEvidence: { ...GOOD_NET, expectancyCurrency: null },
    });
    const exp = absent.checks.find((c) => c.id === "expectancy");
    expect(exp?.status).toBe("warn");
    expect(exp?.requiresAck).toBe(true);
  });
});

describe("resolvePaperNetEvidence", () => {
  it("lee la base y el neto del mismo payload, sin mezclar", () => {
    const net = resolvePaperNetEvidence(
      { totalReturnPct: 9 },
      {
        returnBasis: "net",
        netReturnPct: 4.1,
        expectancyCurrency: 8,
        roundTripCostBps: 32,
        netTradeCount: 22,
      },
    );
    expect(net).toEqual({
      returnBasis: "net",
      netReturnPct: 4.1,
      expectancyCurrency: 8,
      roundTripCostBps: 32,
      netTradeCount: 22,
    });
  });

  it("devuelve huecos (null) cuando no hay medición neta", () => {
    const net = resolvePaperNetEvidence({ totalReturnPct: 9 }, null);
    expect(net.returnBasis).toBeNull();
    expect(net.netReturnPct).toBeNull();
    expect(net.expectancyCurrency).toBeNull();
    expect(net.roundTripCostBps).toBeNull();
  });
});
