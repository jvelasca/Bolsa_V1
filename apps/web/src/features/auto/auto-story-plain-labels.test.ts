import { describe, expect, it } from "vitest";
import {
  AUTO_STORY_PLAIN_LABELS,
  plainStageLabel,
} from "./auto-story-plain-labels";

describe("plainStageLabel", () => {
  it("traduce las etapas clave a lenguaje de usuario", () => {
    expect(plainStageLabel("FILL", "Fill")).toBe("Operación ejecutada");
    expect(plainStageLabel("RESERVATION", "Reserva")).toBe("Capital apartado");
    expect(plainStageLabel("SETTLEMENT", "Liquidación")).toBe(
      "Resultado de la venta",
    );
    expect(plainStageLabel("SELECTION", "Selección · TOP-N")).toBe(
      "Elegida entre las mejores",
    );
  });

  it("cubre las 14 etapas del modelo", () => {
    expect(Object.keys(AUTO_STORY_PLAIN_LABELS)).toHaveLength(14);
  });

  it("un id desconocido degrada a la etiqueta técnica recibida", () => {
    expect(plainStageLabel("UNKNOWN", "Etapa X")).toBe("Etapa X");
  });
});
