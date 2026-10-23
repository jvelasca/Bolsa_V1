import { describe, expect, it } from "vitest";
import type {
  EstudioChainAttributionV1,
  EstudioChainCycleV1,
  EstudioChainValueV1,
  EstudioDailyValueV1,
} from "./estudio-daily-ops.js";
import {
  deriveValueSummary,
  describeAttribution,
} from "./estudio-daily-summary.js";

const baseValue = (
  overrides: Partial<EstudioDailyValueV1> = {},
): EstudioDailyValueV1 => ({
  instrumentId: "inst-1",
  symbol: "AAA",
  status: "ok",
  reason: null,
  asOfBarDate: "2026-10-17",
  computedAt: "2026-10-17T22:00:00Z",
  opinion: {
    stance: "COMPRA",
    dictamenStars: 4,
    channel: "auto",
    autoSource: null,
    reasons: ["tendencia alcista", "volumen"],
    gateStatus: null,
    engineVersion: null,
  },
  indicators: {
    io: 0.7,
    fa: 0.6,
    ta: 0.5,
    confidence: null,
    regime: "alcista",
  },
  plan: {
    decisionId: "tp-1",
    status: "TRIGGERED",
    direction: "LONG",
    entry: 100,
    structuralStop: 95,
    target1: 110,
    target2: 120,
    riskAmount: 5,
    expectedRR: 2,
    whyNot: [],
  },
  whyNot: [],
  strategy: {
    presetKey: "estudio_auto",
    strategyDefinitionId: "sd-1",
    strategyVersion: 1,
    planId: "tp-1",
    signalId: "edo-2026-10-17-estudio_auto-inst-1",
  },
  selector: null,
  ...overrides,
});

const chainValue = (cycles: EstudioChainCycleV1[]): EstudioChainValueV1 =>
  ({
    instrumentId: "inst-1",
    cycles,
    measured: true,
    complete: true,
    unmeasured: [],
    strategy: {},
    strategyDiaD: {},
  }) as unknown as EstudioChainValueV1;

const attribution = (
  state: EstudioChainAttributionV1["state"],
): EstudioChainAttributionV1 =>
  ({
    state,
    planId: null,
    signalId: null,
    cycles: [],
    reason: null,
  }) as unknown as EstudioChainAttributionV1;

describe("deriveValueSummary", () => {
  it("responde qué propone con los niveles del plan TRIGGERED", () => {
    const summary = deriveValueSummary(baseValue());
    expect(summary.proposal.headline).toContain("compra");
    expect(summary.proposal.headline).toContain("100");
    expect(summary.proposal.detail).toContain("Stop 95");
    expect(summary.proposal.measurement).toBe("COMPLETE");
  });

  it("declara el hueco de señal sin inventar un plan", () => {
    const summary = deriveValueSummary(
      baseValue({
        status: "no_signal",
        plan: null,
        reason: "sin señal de apertura",
      }),
    );
    expect(summary.proposal.headline).toContain("no propone entrada");
    expect(summary.missing.headline).toContain("señal de apertura");
    expect(summary.missing.measurement).toBe("COMPLETE");
  });

  it("no afirma «validada» cuando la validación no se pasa", () => {
    const summary = deriveValueSummary(baseValue());
    expect(summary.validation.headline).toContain("no medida");
    expect(summary.validation.validated).toBeNull();
    expect(summary.validation.headline.toLowerCase()).not.toContain(
      "validada ·",
    );
  });

  it("separa la validación estadística de la clasificación del selector", () => {
    const summary = deriveValueSummary(baseValue(), {
      validation: { k: 0, target: 32, windowVerdict: "INCONCLUSIVE" },
    });
    expect(summary.validation.headline).toContain("no validada");
    expect(summary.validation.headline).toContain("K=0/32");
    expect(summary.validation.headline).toContain("INCONCLUSIVE");
    expect(summary.validation.validated).toBe(false);
    expect(summary.validation.detail).toContain("NO es una validación");
  });

  it("rotula el #1 de la foto como clasificación, nunca como validación", () => {
    const summary = deriveValueSummary(
      baseValue({
        selector: {
          measured: true,
          runId: "run-9",
          bar: "2026-10-17",
          assetId: "inst-1",
          presetKey: "estudio_auto",
          strategyVersion: "1",
          isWinner: true,
          reason: null,
        },
      }),
    );
    expect(summary.classification.rank).toBe(1);
    expect(summary.classification.headline).toContain("#1 de la foto");
    expect(summary.classification.headline).toContain("run-9");
    expect(summary.classification.detail).toContain("NO una validación");
  });

  it("no rotula ganador cuando la foto no lo sella", () => {
    const summary = deriveValueSummary(
      baseValue({
        selector: {
          measured: true,
          runId: "run-9",
          bar: "2026-10-17",
          assetId: null,
          presetKey: null,
          strategyVersion: null,
          isWinner: null,
          reason: "no_rank_one",
        },
      }),
    );
    expect(summary.classification.rank).toBeNull();
    expect(summary.classification.headline).toContain(
      "sin veredicto de puesto",
    );
  });

  it("dice qué falta para actuar cuando no hay ciclo adoptado", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([]),
    });
    expect(summary.missing.headline).toContain("adopte esta propuesta");
    expect(summary.technical.cycleIds).toEqual([]);
  });

  it("declara el ciclo adoptado sin pedir nada más", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([
        {
          cycleId: "cyc-1",
          closed: true,
          attribution: attribution("exact"),
        } as unknown as EstudioChainCycleV1,
      ]),
    });
    expect(summary.missing.headline).toContain("Nada pendiente");
    expect(summary.technical.cycleIds).toEqual(["cyc-1"]);
    expect(summary.technical.attribution?.state).toBe("exact");
    expect(summary.technical.attributionLabel).toContain("atribuida");
  });
});

describe("describeAttribution", () => {
  it("traduce los cinco estados aceptados", () => {
    expect(describeAttribution(attribution("exact"))).toContain("atribuida");
    expect(describeAttribution(attribution("mismatch"))).toContain(
      "NO atribuida",
    );
    expect(describeAttribution(attribution("not_proposed"))).toContain(
      "Sin atribución al parte",
    );
    expect(describeAttribution(attribution("unmeasured"))).toContain(
      "no medible",
    );
    expect(describeAttribution(attribution("ambiguous"))).toContain("ambigua");
  });

  it("un hueco se declara como hueco, no como estado", () => {
    expect(describeAttribution(null)).toContain("Sin dato de atribución");
  });
});
