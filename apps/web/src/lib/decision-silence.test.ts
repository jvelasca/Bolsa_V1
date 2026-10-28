import { describe, expect, it } from "vitest";
import {
  decisionSilenceBreakdown,
  decisionSilenceCause,
  decisionSilenceLabel,
  decisionSilenceReasonLabel,
  decisionSilenceSummary,
  isNotEvaluableCause,
  notEvaluableHolds,
} from "@/lib/decision-silence";

const WARMUP_INSUFFICIENT =
  "warmup_insufficient: sma period=200 requiere >= 201 barras (ventana: 120)";

function hold(reason: string | null | undefined) {
  return { reason };
}

describe("decisionSilenceCause", () => {
  it("clasifica el vocabulario cerrado por literal exacto", () => {
    expect(decisionSilenceCause("no_signal")).toBe("no_signal");
    expect(decisionSilenceCause("no_executable")).toBe("not_executable");
    expect(decisionSilenceCause("active_signal_disabled")).toBe("disabled");
    expect(decisionSilenceCause("no_snapshot")).toBe("not_evaluable");
    expect(decisionSilenceCause("evaluation_failed")).toBe("not_evaluable");
    expect(decisionSilenceCause("warmup_unmeasurable")).toBe("not_evaluable");
    // ADR-048 — el libro ilegible es un hueco del motor, no una conclusión de mercado.
    expect(decisionSilenceCause("gated_unavailable")).toBe("not_evaluable");
  });

  it("reconoce el warmup insuficiente por su prefijo estable, no por la prosa", () => {
    expect(decisionSilenceCause(WARMUP_INSUFFICIENT)).toBe("not_evaluable");
    expect(decisionSilenceCause("  warmup_insufficient: otra redacción")).toBe(
      "not_evaluable",
    );
  });

  it("no clasifica un prefijo a mitad de frase", () => {
    expect(decisionSilenceCause("el warmup_insufficient no aplica")).toBe(
      "unmeasured",
    );
    expect(decisionSilenceCause("warmup")).toBe("unmeasured");
  });

  it("sin motivo no se puede afirmar «sin señal»", () => {
    expect(decisionSilenceCause(null)).toBe("unmeasured");
    expect(decisionSilenceCause(undefined)).toBe("unmeasured");
    expect(decisionSilenceCause("   ")).toBe("unmeasured");
  });

  it("un motivo fuera del vocabulario no se presenta como causa conocida", () => {
    expect(decisionSilenceCause("invented_reason")).toBe("unmeasured");
  });
});

describe("decisionSilenceBreakdown", () => {
  it("cuenta cada causa por separado y no mezcla no evaluable con sin señal", () => {
    const breakdown = decisionSilenceBreakdown([
      hold("no_signal"),
      hold("no_signal"),
      hold("no_snapshot"),
      hold("gated_unavailable"),
      hold("active_signal_disabled"),
      hold("no_executable"),
      hold("sin_vocabulario"),
      hold(null),
    ]);

    expect(breakdown).toEqual({
      notEvaluable: 2,
      noSignal: 2,
      disabled: 1,
      notExecutable: 1,
      unmeasured: 2,
    });
  });

  it("sin declaraciones no inventa recuentos", () => {
    expect(decisionSilenceBreakdown([])).toEqual({
      notEvaluable: 0,
      noSignal: 0,
      disabled: 0,
      notExecutable: 0,
      unmeasured: 0,
    });
  });
});

describe("decisionSilenceSummary", () => {
  it("no dice «sin señal» cuando no hay ninguna declaración", () => {
    const summary = decisionSilenceSummary([]);

    expect(summary.total).toBe(0);
    expect(summary.headline).toBe("Sin HOLD declarados en la ventana");
    expect(summary.detail).toBeNull();
  });

  it("separa «sin señal» de «no evaluable» en el titular", () => {
    const summary = decisionSilenceSummary([
      hold("no_signal"),
      hold("warmup_insufficient: falta la serie"),
      hold("no_snapshot"),
    ]);

    expect(summary.headline).toBe("1 sin señal · 2 HOLD no evaluables");
    expect(summary.detail).toContain("2 no evaluables");
  });

  it("con TODO no evaluable no menciona «sin señal»", () => {
    const summary = decisionSilenceSummary([
      hold("no_snapshot"),
      hold("gated_unavailable"),
    ]);

    expect(summary.headline).toBe("Ningún HOLD con señal evaluada");
    expect(summary.headline).not.toContain("sin señal");
  });

  it("sin huecos, el titular cuenta solo los HOLD sin señal", () => {
    const summary = decisionSilenceSummary([
      hold("no_signal"),
      hold("no_signal"),
    ]);

    expect(summary.headline).toBe("2 HOLD sin señal");
    expect(summary.detail).toBeNull();
  });

  it("nombra el alcance leído cuando no es la ventana completa", () => {
    expect(decisionSilenceSummary([], "el día explicado").headline).toBe(
      "Sin HOLD declarados en el día explicado",
    );
  });
});

describe("etiquetas", () => {
  it("cada causa tiene etiqueta legible y nunca se rotula «sin señal» una no evaluable", () => {
    expect(decisionSilenceLabel("not_evaluable")).toBe("no evaluable");
    expect(decisionSilenceLabel("no_signal")).toBe("sin señal");
    expect(decisionSilenceLabel("unmeasured")).toBe("sin dato");
  });

  it("el motivo concreto se traduce sólo si es legible", () => {
    expect(decisionSilenceReasonLabel("gated_unavailable")).toBe(
      "libro no legible",
    );
    expect(decisionSilenceReasonLabel(WARMUP_INSUFFICIENT)).toBe(
      "warmup insuficiente",
    );
    expect(decisionSilenceReasonLabel("sin_vocabulario")).toBeNull();
    expect(decisionSilenceReasonLabel(null)).toBeNull();
  });
});

describe("notEvaluableHolds", () => {
  it("lista los no evaluables y los no medidos, sin arrastrar las decisiones", () => {
    const holds = [
      hold("no_signal"),
      hold("no_snapshot"),
      hold(null),
      hold("no_executable"),
    ];

    expect(notEvaluableHolds(holds).map((item) => item.reason)).toEqual([
      "no_snapshot",
      null,
    ]);
  });
});

describe("isNotEvaluableCause", () => {
  it("es la fuente única del conjunto «hueco a resolver»", () => {
    expect(isNotEvaluableCause("not_evaluable")).toBe(true);
    expect(isNotEvaluableCause("unmeasured")).toBe(true);
    // Una decisión declarada no es un hueco: la señal apagada y la no ejecutable se excluyen.
    expect(isNotEvaluableCause("no_signal")).toBe(false);
    expect(isNotEvaluableCause("disabled")).toBe(false);
    expect(isNotEvaluableCause("not_executable")).toBe(false);
  });

  it("coincide con las filas que devuelve notEvaluableHolds", () => {
    const holds = [
      hold("no_signal"),
      hold("no_snapshot"),
      hold("active_signal_disabled"),
      hold(null),
    ];
    const expected = holds.filter((item) =>
      isNotEvaluableCause(decisionSilenceCause(item.reason)),
    );
    expect(notEvaluableHolds(holds)).toEqual(expected);
  });
});
