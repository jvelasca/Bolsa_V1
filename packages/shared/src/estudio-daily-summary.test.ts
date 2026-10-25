import { describe, expect, it } from "vitest";
import type {
  EstudioChainAttributionV1,
  EstudioChainCycleV1,
  EstudioChainValueV1,
  EstudioDailyValueV1,
} from "./estudio-daily-ops.js";
import {
  aggregateAttribution,
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

/** Ciclo durable mínimo: estado de atribución (o hueco) y si está cerrado. */
const chainCycle = (
  state: EstudioChainAttributionV1["state"] | null,
  closed: boolean | null = true,
  cycleId = "cyc-1",
): EstudioChainCycleV1 =>
  ({
    cycleId,
    closed,
    attribution: state === null ? null : attribution(state),
  }) as unknown as EstudioChainCycleV1;

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

  it("declara el ciclo EXACT adoptado sin pedir nada más", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("exact", true)]),
    });
    expect(summary.missing.headline).toContain("Nada pendiente");
    expect(summary.missing.detail).toContain("1 cerrado(s)");
    expect(summary.missing.measurement).toBe("COMPLETE");
    expect(summary.technical.cycleIds).toEqual(["cyc-1"]);
    expect(summary.technical.attribution?.state).toBe("exact");
    expect(summary.technical.attributionLabel).toContain("atribuida");
  });

  it("distingue el ciclo exact ABIERTO del cerrado en el detalle", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("exact", false)]),
    });
    expect(summary.missing.headline).toContain("Nada pendiente");
    expect(summary.missing.detail).toContain("1 abierto(s)");
    expect(summary.missing.detail).toContain("0 cerrado(s)");
    expect(summary.missing.measurement).toBe("COMPLETE");
  });

  it("un ciclo con OTRA identidad no se declara «Nada pendiente»", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("mismatch", true)]),
    });
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.headline).toContain("no corresponde");
    expect(summary.missing.detail).toContain("otra señal/plan");
    expect(summary.missing.measurement).toBe("COMPLETE");
    expect(summary.technical.attribution?.state).toBe("mismatch");
  });

  it("un ciclo sin propuesta adoptada se declara como tal, no como ejecutado", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("not_proposed", true)]),
    });
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.headline).toContain(
      "sin adoptar una propuesta de este parte",
    );
    expect(summary.missing.measurement).toBe("COMPLETE");
  });

  it("sin identidad suficiente declara el hueco como no medido", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("unmeasured", true)]),
    });
    expect(summary.missing.headline).toContain("No hay datos suficientes");
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.measurement).toBe("UNKNOWN");
  });

  it("declara la ambigüedad sin elegir un ciclo arbitrario", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle("ambiguous", true)]),
    });
    expect(summary.missing.headline).toContain("Atribución ambigua");
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.measurement).toBe("UNKNOWN");
  });

  it("con varios ciclos, uno exact y otro mismatch, la atribución es MIXTA", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([
        chainCycle("exact", true, "cyc-1"),
        chainCycle("mismatch", false, "cyc-2"),
      ]),
    });
    expect(summary.technical.attribution?.state).toBe("mixed");
    expect(summary.technical.attribution?.exactCount).toBe(1);
    expect(summary.technical.attribution?.counts).toEqual({
      exact: 1,
      mismatch: 1,
    });
    // Un `exact` dentro de un agregado mixto NO da la cadena por completa.
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.headline).toContain("al menos un ciclo atribuido");
    expect(summary.missing.headline).toContain("discrepante");
    expect(summary.missing.detail).toContain("Atribución mixta");
    expect(summary.missing.detail).toContain("exact 1");
    expect(summary.missing.detail).toContain("mismatch 1");
    expect(summary.missing.detail).toContain("Revisa el detalle");
    expect(summary.missing.measurement).toBe("PARTIAL");
  });

  it("una atribución mixta SIN exact no se declara «Nada pendiente»", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([
        chainCycle("mismatch", true, "cyc-1"),
        chainCycle("not_proposed", true, "cyc-2"),
      ]),
    });
    expect(summary.technical.attribution?.state).toBe("mixed");
    expect(summary.technical.attribution?.exactCount).toBe(0);
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.headline).toContain("ninguno está atribuido");
    expect(summary.missing.measurement).toBe("PARTIAL");
  });

  it("varios ciclos todos exact siguen siendo attribución exact", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([
        chainCycle("exact", true, "cyc-1"),
        chainCycle("exact", false, "cyc-2"),
      ]),
    });
    expect(summary.technical.attribution?.state).toBe("exact");
    expect(summary.technical.attribution?.cycles).toBe(2);
    expect(summary.technical.attribution?.exactCount).toBe(2);
    expect(summary.technical.attribution?.exactClosed).toBe(1);
    expect(summary.technical.attribution?.exactOpen).toBe(1);
  });

  it("la atribución del valor NO la decide el primer ciclo (regresión cycles[0])", () => {
    const firstMismatch = deriveValueSummary(baseValue(), {
      chain: chainValue([
        chainCycle("mismatch", true, "cyc-1"),
        chainCycle("exact", true, "cyc-2"),
      ]),
    });
    expect(firstMismatch.technical.attribution?.state).toBe("mixed");
    expect(firstMismatch.technical.attribution?.exactCount).toBe(1);
    expect(firstMismatch.technical.attributionLabel).toContain("mixta");
    expect(firstMismatch.missing.headline).toContain("al menos un ciclo");
    expect(firstMismatch.missing.headline).not.toContain("Nada pendiente");
    expect(firstMismatch.missing.measurement).toBe("PARTIAL");

    // El orden de los ciclos no cambia el dictamen: tampoco si el `exact` va primero.
    const firstExact = deriveValueSummary(baseValue(), {
      chain: chainValue([
        chainCycle("exact", true, "cyc-2"),
        chainCycle("mismatch", true, "cyc-1"),
      ]),
    });
    expect(firstExact.technical.attribution?.state).toBe("mixed");
    expect(firstExact.missing.headline).toBe(firstMismatch.missing.headline);
    expect(firstExact.missing.measurement).toBe("PARTIAL");
  });

  it("un ciclo sin atribución declarada cuenta como unmeasured", () => {
    const summary = deriveValueSummary(baseValue(), {
      chain: chainValue([chainCycle(null, true)]),
    });
    expect(summary.technical.attribution?.state).toBe("unmeasured");
    expect(summary.missing.headline).not.toContain("Nada pendiente");
    expect(summary.missing.measurement).toBe("UNKNOWN");
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
    expect(describeAttribution(attribution("mixed"))).toContain("mixta");
  });

  it("un hueco se declara como hueco, no como estado", () => {
    expect(describeAttribution(null)).toContain("Sin dato de atribución");
  });
});

describe("aggregateAttribution", () => {
  it("sin ciclos es un hueco declarado, no un «no atribuido»", () => {
    expect(aggregateAttribution([])).toBeNull();
    expect(aggregateAttribution(null)).toBeNull();
    expect(aggregateAttribution(undefined)).toBeNull();
  });

  it("no elige un ciclo representativo cuando los estados discrepan", () => {
    const aggregated = aggregateAttribution([
      chainCycle("exact", true, "cyc-1"),
      chainCycle("mismatch", true, "cyc-2"),
    ]);
    expect(aggregated?.state).toBe("mixed");
    expect(aggregated?.reason).toBe("mixed_attribution");
    expect(aggregated?.proposalId).toBeNull();
    expect(aggregated?.counts).toEqual({ exact: 1, mismatch: 1 });
    expect(aggregated?.closed).toBe(2);
    expect(aggregated?.open).toBe(0);
  });

  it("cuenta aparte los ciclos sin estado de cierre declarado", () => {
    const aggregated = aggregateAttribution([
      chainCycle("exact", null, "cyc-1"),
    ]);
    expect(aggregated?.closedUnknown).toBe(1);
    expect(aggregated?.open).toBe(0);
    expect(aggregated?.closed).toBe(0);
  });
});
