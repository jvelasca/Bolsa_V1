import { describe, expect, it } from "vitest";
import {
  DIA_D_AS_RUN_ARMS,
  type DiaDAsRunArmV1,
  type DiaDAsRunAuditV1,
  type DiaDAsRunExecutionModelV1,
} from "./dia-d-as-run.js";

describe("DIA_D_AS_RUN_ARMS", () => {
  it("declara el orden canónico de los seis brazos del método", () => {
    expect(DIA_D_AS_RUN_ARMS).toEqual([
      "as_run",
      "hold_structural",
      "cash",
      "engine_params",
      "candidate",
      "market_bh",
    ]);
  });

  it("el benchmark de mercado es un brazo declarado, no un extra opcional", () => {
    expect(DIA_D_AS_RUN_ARMS).toContain("market_bh");
  });

  it("un brazo no medido no puede llevar un R inventado", () => {
    const arm: DiaDAsRunArmV1 = {
      arm: "candidate",
      measured: false,
      reason: "candidate_not_provided",
      realizedR: null,
      pnlCurrency: null,
      maeR: null,
      mfeR: null,
      capture: null,
      returnPct: null,
      exits: 0,
      stops: 0,
      targets: 0,
      legs: 0,
      reasonCodes: [],
      decisions: [],
    };
    expect(arm.measured).toBe(false);
    expect(arm.realizedR).toBeNull();
    expect(arm.reason).toBe("candidate_not_provided");
  });

  it("el modelo de ejecución declara la base de coste de los fills reales", () => {
    const execution: DiaDAsRunExecutionModelV1 = {
      commissionBps: 10,
      slippageBps: 5,
      spreadBps: 2,
      roundTripBps: 32,
      executionCostBps: 22,
      maxParticipationPct: 0.1,
      gapPolicy: "open",
      realFillsCostBasis: "effective",
    };
    expect(execution.realFillsCostBasis).toBe("effective");
  });

  it("la auditoría declara universo, manifest por vela y comparabilidad del benchmark", () => {
    const audit: DiaDAsRunAuditV1 = {
      pointInTime: {
        day: "2026-09-30",
        toDay: "2026-11-13",
        stateSource: "sim_auto_positions",
        sourceIsReconstructed: false,
        legsHash: "a".repeat(64),
        legs: [],
        candidateAsOf: null,
        universe: ["AAA"],
        universeSource: "declared",
      },
      data: {
        barsSource: "postgres:ohlcv_bars",
        timeframe: "1d",
        barsHash: "b".repeat(64),
        barsManifest: { AAA: [["2026-10-01", "c".repeat(64)]] },
        instruments: [
          {
            instrument: "AAA",
            bars: 1,
            firstBar: "2026-10-01",
            lastBar: "2026-10-01",
          },
        ],
      },
      versions: {
        engine: "dia-d-as-run-v2",
        schema: "DiaDAsRunArtifactV2",
        bump: "2.11.189-beta",
        strategy: null,
        mandate: null,
        paramsHash: "d".repeat(64),
      },
      params: { universe: "watch" },
      execution: {
        commissionBps: 10,
        slippageBps: 5,
        spreadBps: 2,
        roundTripBps: 32,
        executionCostBps: 22,
        maxParticipationPct: 0.1,
        gapPolicy: "open",
        realFillsCostBasis: "quoted",
      },
      benchmark: {
        universe: ["AAA"],
        capitalBasis: "initial_notional",
        capital: 1000,
        costBps: 32,
        toDay: "2026-11-13",
      },
      decisions: { as_run: [] },
      limits: [],
    };
    expect(audit.data.barsManifest?.AAA).toHaveLength(1);
    expect(audit.benchmark?.capitalBasis).toBe("initial_notional");
  });
});
