import { describe, expect, it } from "vitest";
import {
  mercadoCockpitPrimaryCta,
  resolveMercadoCockpitPhase,
} from "@/features/trading/operativa-cockpit-phase";

describe("resolveMercadoCockpitPhase", () => {
  it("sin instrumento → sin_contexto", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: null,
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
      }),
    ).toBe("sin_contexto");
  });

  it("posición abierta gana sobre plan y cola", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: true,
        inConfirmQueue: true,
        tradePlanStatus: "TRIGGERED",
        hasOperationalPlan: true,
      }),
    ).toBe("posicion");
  });

  it("cola Confirm → propuesta", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: true,
        tradePlanStatus: "ARMED",
        hasOperationalPlan: true,
      }),
    ).toBe("propuesta");
  });

  it("TRIGGERED → disparada", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "TRIGGERED",
        hasOperationalPlan: true,
      }),
    ).toBe("disparada");
  });

  it("ARMED / plan → preparada", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "ARMED",
        hasOperationalPlan: true,
      }),
    ).toBe("preparada");
  });

  it("en Estudio sin plan → vigilar", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        hasOperationalPlan: false,
      }),
    ).toBe("vigilar");
  });

  it("fuera de Estudio → descubierto", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: false,
        hasOpenPosition: false,
        inConfirmQueue: false,
      }),
    ).toBe("descubierto");
  });
});

describe("mercadoCockpitPrimaryCta", () => {
  it("labels de producto", () => {
    expect(mercadoCockpitPrimaryCta("vigilar")).toBe("Seguir");
    expect(mercadoCockpitPrimaryCta("preparada")).toBe("Preparar operación");
    expect(mercadoCockpitPrimaryCta("disparada")).toBe("Revisar y confirmar");
    expect(mercadoCockpitPrimaryCta("posicion")).toBe("Mantener");
  });
});
