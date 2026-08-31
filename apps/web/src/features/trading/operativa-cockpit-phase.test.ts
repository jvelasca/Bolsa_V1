import { describe, expect, it } from "vitest";
import {
  mercadoCockpitNoLevelsCopy,
  mercadoCockpitPrimaryCta,
  mercadoCockpitShowsPlanLevels,
  resolveMercadoCockpitPhase,
  resolveMercadoTrailingCopy,
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

  it("fill pendiente → confirmada (antes que propuesta)", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: true,
        orderPendingFill: true,
        tradePlanStatus: "TRIGGERED",
        hasOperationalPlan: true,
      }),
    ).toBe("confirmada");
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

  it("WATCH + hasOperationalPlan → preparada", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "WATCH",
        hasOperationalPlan: true,
      }),
    ).toBe("preparada");
  });

  it("BLOCKED + hasOperationalPlan → bloqueada (nunca preparada)", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "BLOCKED",
        hasOperationalPlan: true,
      }),
    ).toBe("bloqueada");
  });

  it("EXPIRED + hasOperationalPlan → caducada (nunca preparada)", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "EXPIRED",
        hasOperationalPlan: true,
      }),
    ).toBe("caducada");
  });

  it("CANCELLED + hasOperationalPlan → caducada", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "CANCELLED",
        hasOperationalPlan: true,
      }),
    ).toBe("caducada");
  });

  it("plan residual sin status operable → vigilar (no preparada)", () => {
    expect(
      resolveMercadoCockpitPhase({
        instrumentId: "i1",
        inEstudio: true,
        hasOpenPosition: false,
        inConfirmQueue: false,
        tradePlanStatus: "FILLED",
        hasOperationalPlan: true,
      }),
    ).toBe("vigilar");
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

describe("mercadoCockpitShowsPlanLevels", () => {
  it("anti-ruido: vigilar/descubierto/bloqueada/caducada sin niveles", () => {
    expect(mercadoCockpitShowsPlanLevels("vigilar")).toBe(false);
    expect(mercadoCockpitShowsPlanLevels("descubierto")).toBe(false);
    expect(mercadoCockpitShowsPlanLevels("bloqueada")).toBe(false);
    expect(mercadoCockpitShowsPlanLevels("caducada")).toBe(false);
    expect(mercadoCockpitShowsPlanLevels("preparada")).toBe(true);
    expect(mercadoCockpitShowsPlanLevels("posicion")).toBe(true);
  });
});

describe("mercadoCockpitPrimaryCta", () => {
  it("labels de producto V1.24", () => {
    expect(mercadoCockpitPrimaryCta("vigilar")).toBe("Ver análisis");
    expect(mercadoCockpitPrimaryCta("preparada")).toBe("Revisar operación");
    expect(mercadoCockpitPrimaryCta("bloqueada")).toBe(
      "Ver motivo del bloqueo",
    );
    expect(mercadoCockpitPrimaryCta("caducada")).toBe("Ver análisis");
    expect(mercadoCockpitPrimaryCta("disparada")).toBe("Confirmar");
    expect(mercadoCockpitPrimaryCta("confirmada")).toBe("Ver operaciones");
    expect(mercadoCockpitPrimaryCta("posicion")).toBe("Mantener");
  });
});

describe("mercadoCockpitNoLevelsCopy", () => {
  it("explica la ausencia de plan solo donde no hay niveles", () => {
    expect(mercadoCockpitNoLevelsCopy("vigilar")).toMatch(/supervisión/i);
    expect(mercadoCockpitNoLevelsCopy("descubierto")).toMatch(/Estudio/);
    expect(mercadoCockpitNoLevelsCopy("sin_contexto")).toMatch(/Selecciona/);
    expect(mercadoCockpitNoLevelsCopy("bloqueada")).toMatch(/bloqueado/i);
    expect(mercadoCockpitNoLevelsCopy("caducada")).toMatch(/caducado/i);
    expect(mercadoCockpitNoLevelsCopy("posicion")).toBeNull();
    expect(mercadoCockpitNoLevelsCopy("preparada")).toBeNull();
  });
});

describe("resolveMercadoTrailingCopy", () => {
  const base = {
    entry: 100,
    stopVigente: 95,
    trailingActive: true,
    trailingStopHint: 101,
  };

  it("fuera de posición no muestra trailing", () => {
    expect(
      resolveMercadoTrailingCopy({ ...base, phase: "preparada" }).show,
    ).toBe(false);
  });

  it("sugerencia no recogida → Stop sugerido · No aplicado", () => {
    const copy = resolveMercadoTrailingCopy({ ...base, phase: "posicion" });
    expect(copy.show).toBe(true);
    expect(copy.stopVigenteLabel).toBe("Stop operativo");
    expect(copy.stopSugeridoLabel).toBe("Stop sugerido");
    expect(copy.stopVigente).toBe(95);
    expect(copy.stopSugerido).toBe(101);
    expect(copy.applied).toBe(false);
    expect(copy.statusLabel).toBe("No aplicado");
  });

  it("stop vigente ya por encima de la sugerencia → aplicado, sin aviso", () => {
    const copy = resolveMercadoTrailingCopy({
      ...base,
      phase: "posicion",
      stopVigente: 103,
    });
    expect(copy.applied).toBe(true);
    expect(copy.statusLabel).toBeNull();
  });

  it("short: aplicado cuando el stop vigente está por debajo de la sugerencia", () => {
    const copy = resolveMercadoTrailingCopy({
      phase: "posicion",
      entry: 100,
      stopVigente: 104,
      trailingActive: true,
      trailingStopHint: 106,
      direction: "short",
    });
    expect(copy.applied).toBe(true);
    expect(copy.statusLabel).toBeNull();
  });

  it("short: no aplicado cuando el stop vigente aún no recoge la sugerencia", () => {
    const copy = resolveMercadoTrailingCopy({
      phase: "posicion",
      entry: 100,
      stopVigente: 108,
      trailingActive: true,
      trailingStopHint: 106,
      direction: "short",
    });
    expect(copy.applied).toBe(false);
    expect(copy.statusLabel).toBe("No aplicado");
  });

  it("trail activo sin stop sugerido → Revisar", () => {
    const copy = resolveMercadoTrailingCopy({
      ...base,
      phase: "posicion",
      trailingStopHint: null,
    });
    expect(copy.show).toBe(true);
    expect(copy.statusLabel).toBe("Revisar");
    expect(copy.stopSugerido).toBeNull();
  });
});
