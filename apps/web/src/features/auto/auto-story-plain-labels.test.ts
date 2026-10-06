import { describe, expect, it } from "vitest";
import {
  AUTO_STORY_PLAIN_LABELS,
  AUTO_STORY_PLAIN_STATE_LABELS,
  plainStageLabel,
  plainStateLabel,
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

describe("plainStateLabel", () => {
  it("traduce los estados a lenguaje de usuario (NO MEDIDO → Sin dato todavía)", () => {
    expect(plainStateLabel("NOT_MEASURED", "NO MEDIDO")).toBe(
      "Sin dato todavía",
    );
    expect(plainStateLabel("REACHED", "alcanzado")).toBe("Hecho");
    expect(plainStateLabel("PENDING", "pendiente")).toBe("Pendiente");
    expect(plainStateLabel("ABSENT", "ausente")).toBe("No ocurrió");
  });

  it("un estado desconocido degrada a la etiqueta técnica recibida", () => {
    expect(plainStateLabel("RARO", "estado X")).toBe("estado X");
    expect(Object.keys(AUTO_STORY_PLAIN_STATE_LABELS)).toHaveLength(4);
  });
});
