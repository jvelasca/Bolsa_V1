/**
 * S4-agregador-evidencia — regresión falsable del read-model puro.
 *
 * Invariantes cubiertos:
 * 1. Nunca se emite la confirmación reservada (`NO_CONFIRMED` invariante en todo el powerset).
 * 2. Ninguna capa promociona a la siguiente (`ventana + contraste + OOS` siguen sin confirmar).
 * 3. `UNKNOWN ≠ 0`: un hueco se declara, nunca se colapsa a 0 ni a un veredicto afirmado.
 * 4. El lens `SAME_CONFIRMED` de Trading no entra en el agregado.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildDiaDEvidenceAggregate,
  type DiaDEvidenceAggregateInput,
  type DiaDEvidenceOosFacts,
  type DiaDEvidenceReconciliationFacts,
  type DiaDEvidenceWindowFacts,
} from "@/features/auto-monitor/dia-d-evidence-aggregate";

const WINDOW: DiaDEvidenceWindowFacts = {
  loaded: true,
  verdict: "READY",
  days: 4,
  episodes: 2,
  cycles: 32,
};

const RECONCILIATION: DiaDEvidenceReconciliationFacts = {
  loaded: true,
  verdict: "MATCH",
  match: 3,
  divergent: 0,
  notMeasured: 0,
};

const OOS: DiaDEvidenceOosFacts = {
  loaded: true,
  oosSupported: 1,
  mixed: 0,
  refuted: 0,
  notMeasured: 0,
};

function input(
  over: Partial<DiaDEvidenceAggregateInput>,
): DiaDEvidenceAggregateInput {
  return { window: null, reconciliation: null, oos: null, ...over };
}

describe("buildDiaDEvidenceAggregate · nunca confirma", () => {
  it("devuelve NO_CONFIRMED en todo el powerset de capas medidas", () => {
    for (const w of [true, false]) {
      for (const r of [true, false]) {
        for (const o of [true, false]) {
          const result = buildDiaDEvidenceAggregate(
            input({
              window: w ? WINDOW : null,
              reconciliation: r ? RECONCILIATION : null,
              oos: o ? OOS : null,
            }),
          );
          expect(result.verdict).toBe("NO_CONFIRMED");
          expect(/\bCONFIRMED\b/.test(JSON.stringify(result))).toBe(false);
          expect(result.layers[3]!.id).toBe("paper");
          expect(result.layers[3]!.state).toBe("gap");
        }
      }
    }
  });

  it("el word-boundary distingue el token reservado del rótulo permitido", () => {
    expect(/\bCONFIRMED\b/.test("CONFIRMED")).toBe(true);
    expect(/\bCONFIRMED\b/.test("NO_CONFIRMADO")).toBe(false);
    expect(/\bCONFIRMED\b/.test("NO_CONFIRMED")).toBe(false);
  });
});

describe("buildDiaDEvidenceAggregate · rollup OOS con contradicción", () => {
  it("soportados y refutados a la vez se declaran MIXED, no REFUTED", () => {
    const result = buildDiaDEvidenceAggregate(
      input({
        oos: {
          loaded: true,
          oosSupported: 2,
          mixed: 0,
          refuted: 1,
          notMeasured: 0,
        },
      }),
    );
    const oos = result.layers.find((layer) => layer.id === "oos");
    expect(oos?.state).toBe("measured");
    if (oos && oos.state === "measured") {
      expect(oos.verdictToken).toBe("MIXED");
      expect(oos.verdictLabel).toBe("Resultado mixto");
    }
  });

  it("solo refutados se declaran REFUTED", () => {
    const result = buildDiaDEvidenceAggregate(
      input({
        oos: {
          loaded: true,
          oosSupported: 0,
          mixed: 0,
          refuted: 3,
          notMeasured: 0,
        },
      }),
    );
    const oos = result.layers.find((layer) => layer.id === "oos");
    if (oos && oos.state === "measured") {
      expect(oos.verdictToken).toBe("REFUTED");
    } else {
      throw new Error("la capa OOS debería estar medida");
    }
  });
});

describe("buildDiaDEvidenceAggregate · OOS con contadores ausentes (UNKNOWN != 0)", () => {
  function oosLayer(over: Partial<DiaDEvidenceOosFacts>) {
    const result = buildDiaDEvidenceAggregate(
      input({ oos: { ...OOS, ...over } }),
    );
    return {
      result,
      oos: result.layers.find((layer) => layer.id === "oos"),
    };
  }

  it("soportados medidos y mixtos/refutados ausentes ⇒ hueco, no «Soportado»", () => {
    // Caso exacto del audit: 2 soportados, sin dato en mixtos y refutados.
    const { result, oos } = oosLayer({
      oosSupported: 2,
      mixed: null,
      refuted: null,
      notMeasured: 0,
    });
    expect(oos?.state).toBe("gap");
    if (oos && oos.state === "gap") {
      expect(oos.gapLabel).toBe("Sin dato todavía");
      // La muestra parcial se conserva: no se colapsa a 0 ni se pierde.
      expect(oos.measurement).toContain("soportados 2");
    }
    expect(result.maxLayerReached).not.toBe("oos");
  });

  it("basta un contador ausente para no afirmar el veredicto", () => {
    const { oos } = oosLayer({
      oosSupported: 1,
      mixed: 0,
      refuted: null,
      notMeasured: 0,
    });
    expect(oos?.state).toBe("gap");
  });

  it("con los tres contadores pero evidencia sin medir ⇒ hueco", () => {
    const { oos } = oosLayer({
      oosSupported: 1,
      mixed: 0,
      refuted: 0,
      notMeasured: 2,
    });
    expect(oos?.state).toBe("gap");
    if (oos && oos.state === "gap") {
      expect(oos.measurement).toContain("sin medir 2");
    }
  });

  it("nunca colapsa un contador ausente a 0 en la muestra parcial", () => {
    const { oos } = oosLayer({
      oosSupported: null,
      mixed: null,
      refuted: null,
      notMeasured: null,
    });
    expect(oos?.state).toBe("gap");
    if (oos && oos.state === "gap") {
      expect(oos.measurement).not.toMatch(/\b0\b/);
    }
  });

  it("con datos suficientes el veredicto sí se afirma", () => {
    const supported = oosLayer({
      oosSupported: 2,
      mixed: 0,
      refuted: 0,
      notMeasured: 0,
    });
    expect(supported.oos?.state).toBe("measured");
    if (supported.oos && supported.oos.state === "measured") {
      expect(supported.oos.verdictToken).toBe("OOS_SUPPORTED");
    }
    const mixed = oosLayer({
      oosSupported: 2,
      mixed: 0,
      refuted: 1,
      notMeasured: 0,
    });
    expect(mixed.oos?.state).toBe("measured");
    if (mixed.oos && mixed.oos.state === "measured") {
      expect(mixed.oos.verdictToken).toBe("MIXED");
    }
  });
});

describe("buildDiaDEvidenceAggregate · no promoción", () => {
  it("ventana + contraste + OOS medidos no cierran la operativa", () => {
    const result = buildDiaDEvidenceAggregate(
      input({ window: WINDOW, reconciliation: RECONCILIATION, oos: OOS }),
    );
    expect(result.verdict).toBe("NO_CONFIRMED");
    expect(result.maxLayerReached).toBe("oos");
    const paper = result.layers.find((layer) => layer.id === "paper");
    expect(paper?.state).toBe("gap");
    expect(result.gapLayerIds).toContain("paper");
  });

  it("reporta la capa más fuerte medida sin promocionar la siguiente", () => {
    expect(
      buildDiaDEvidenceAggregate(input({ window: WINDOW })).maxLayerReached,
    ).toBe("window");
    expect(
      buildDiaDEvidenceAggregate(input({ reconciliation: RECONCILIATION }))
        .maxLayerReached,
    ).toBe("reconciliation");
    expect(
      buildDiaDEvidenceAggregate(
        input({ window: WINDOW, reconciliation: RECONCILIATION }),
      ).maxLayerReached,
    ).toBe("reconciliation");
    expect(
      buildDiaDEvidenceAggregate(input({ oos: OOS })).maxLayerReached,
    ).toBe("oos");
  });
});

describe("buildDiaDEvidenceAggregate · UNKNOWN != 0", () => {
  it("sin entradas, las cuatro capas son hueco declarado", () => {
    const result = buildDiaDEvidenceAggregate(input({}));
    expect(result.gapLayerIds).toHaveLength(4);
    for (const layer of result.layers) expect(layer.state).toBe("gap");
  });

  it("NOT_MEASURED en el contraste se declara hueco, no cero", () => {
    const result = buildDiaDEvidenceAggregate(
      input({
        reconciliation: {
          ...RECONCILIATION,
          verdict: "NOT_MEASURED",
          match: null,
          divergent: null,
          notMeasured: null,
        },
      }),
    );
    const recon = result.layers.find((layer) => layer.id === "reconciliation");
    expect(recon?.state).toBe("gap");
    if (recon && recon.state === "gap") {
      expect(recon.gapLabel).toBe("Sin dato todavía");
    }
  });

  it("una ventana presente sin veredicto no se colapsa a un valor afirmado", () => {
    const result = buildDiaDEvidenceAggregate(
      input({ window: { ...WINDOW, verdict: null } }),
    );
    expect(result.layers[0]!.state).toBe("gap");
  });
});

describe("buildDiaDEvidenceAggregate · sin promoción de identidad de Trading", () => {
  it("el constructor no conoce el lens SAME_CONFIRMED de Trading", () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        "src/features/auto-monitor/dia-d-evidence-aggregate.ts",
      ),
      "utf8",
    );
    expect(source.includes("SAME_CONFIRMED")).toBe(false);
    expect(/["']CONFIRMED["']/.test(source)).toBe(false);
  });
});
