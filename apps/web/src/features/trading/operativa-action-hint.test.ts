/**
 * S4 · Vía de actuación de la ventana maximizada de DECISIÓN.
 *
 * Guarda la separación entre «lo que el dictamen dice», «lo que la cartera mide»
 * y «lo que la ventana puede proponer». La pista nunca autoriza: describe.
 *
 * @see docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md
 */

import { describe, expect, it } from "vitest";
import {
  OPERATIVA_BLOCK_REASON_IDS,
  operativaBlockReasonDefinition,
  resolveOperativaActionHint,
  resolveOperativaBlockReason,
  type ResolveOperativaActionHintInput,
} from "@/features/trading/operativa-action-hint";

function input(
  overrides: Partial<ResolveOperativaActionHintInput> = {},
): ResolveOperativaActionHintInput {
  return {
    carteraStateId: "recomendacion_favorable",
    hasOpenPosition: false,
    hasAccount: true,
    positionMeasured: true,
    studiesMeasured: true,
    canEnqueueConfirm: true,
    entriesBlocked: false,
    requiresEstudio: false,
    inEstudio: true,
    ...overrides,
  };
}

describe("resolveOperativaActionHint", () => {
  it("sin datos suficientes no describe ninguna vía y no afirma «sin posición»", () => {
    const hint = resolveOperativaActionHint(
      input({ carteraStateId: "sin_datos", positionMeasured: false }),
    );
    expect(hint.id).toBe("sin_actuacion");
    expect(hint.canAct).toBe(false);
    expect(hint.detail.toLowerCase()).not.toContain("sin posición");
  });

  it("recomendación favorable con todas las compuertas abiertas describe entrada", () => {
    const hint = resolveOperativaActionHint(input());
    expect(hint.id).toBe("entrada_disponible");
    expect(hint.blockedReason).toBeNull();
    expect(hint.canAct).toBe(true);
    expect(hint.detail).toContain("Confirm");
  });

  it("con posición abierta la vía es la salida en ACCIÓN, no una entrada", () => {
    for (const carteraStateId of [
      "posicion_abierta",
      "posicion_sin_respaldo",
    ] as const) {
      const hint = resolveOperativaActionHint(
        input({ carteraStateId, hasOpenPosition: true }),
      );
      expect(hint.id).toBe("salida_en_accion");
      expect(hint.canAct).toBe(true);
    }
  });

  it("evaluado sin oportunidad no fabrica una entrada aunque el contexto técnico sea bueno", () => {
    const hint = resolveOperativaActionHint(
      input({ carteraStateId: "evaluado_sin_oportunidad" }),
    );
    expect(hint.id).toBe("sin_actuacion");
    expect(hint.canAct).toBe(false);
    expect(hint.detail).toContain("no emitió compra");
  });

  it("declara el primer bloqueo con la precedencia de canPropose", () => {
    const cases: Array<[Partial<ResolveOperativaActionHintInput>, string]> = [
      [{ hasAccount: false }, "sin_cuenta"],
      [{ positionMeasured: false }, "cartera_sin_medir"],
      [{ studiesMeasured: false }, "estudios_sin_medir"],
      [{ canEnqueueConfirm: false }, "modo_sin_propuesta"],
      [{ entriesBlocked: true }, "entradas_bloqueadas"],
      [{ requiresEstudio: true, inEstudio: false }, "fuera_de_estudio"],
    ];

    for (const [overrides, reason] of cases) {
      const hint = resolveOperativaActionHint(input(overrides));
      expect(hint.id).toBe("entrada_bloqueada");
      expect(hint.blockedReason).toBe(reason);
      expect(hint.canAct).toBe(false);
      expect(hint.detail).toBe(operativaBlockReasonDefinition(reason as never).detail);
    }
  });

  it("el orden de motivos es estable y no acumula varios bloqueos", () => {
    expect(
      OPERATIVA_BLOCK_REASON_IDS.every(
        (id) => typeof operativaBlockReasonDefinition(id).detail === "string",
      ),
    ).toBe(true);
    // Varias condiciones fallando a la vez: gana la primera de la lista.
    expect(
      resolveOperativaBlockReason(
        input({
          hasAccount: false,
          positionMeasured: false,
          studiesMeasured: false,
          entriesBlocked: true,
        }),
      ),
    ).toBe("sin_cuenta");
  });

  it("ninguna pista usa claves internas como etiqueta", () => {
    for (const carteraStateId of [
      "recomendacion_favorable",
      "evaluado_sin_oportunidad",
      "posicion_abierta",
      "posicion_sin_respaldo",
      "sin_datos",
    ] as const) {
      for (const hasOpenPosition of [true, false]) {
        const hint = resolveOperativaActionHint(
          input({ carteraStateId, hasOpenPosition }),
        );
        expect(hint.label).not.toMatch(/[a-z]+_[a-z]+/);
      }
    }
  });
});
