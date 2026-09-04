import { describe, expect, it } from "vitest";
import type { OperationalPlanViewV1 } from "@bolsa/shared";
import { buildOperationalPlanChartLevels } from "@/features/charts/operational-plan-chart-levels";

function plan(
  partial: Partial<OperationalPlanViewV1> = {},
): OperationalPlanViewV1 {
  return {
    phase: "position",
    phaseLabel: "Posición activa",
    direction: "long",
    entry: 100,
    stopVigente: 95,
    stopInicial: 95,
    target1: 110,
    target2: 120,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: 2,
    riskR: 1,
    currentPrice: 104,
    unrealizedR: 0.8,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: true,
    emptyCopy: "sin plan",
    ...partial,
  };
}

describe("buildOperationalPlanChartLevels", () => {
  it("proyecta entrada / stop vigente / T1 / T2", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan(),
      showLevels: true,
    });
    expect(levels.map((l) => l.kind)).toEqual([
      "entry",
      "stopVigente",
      "target1",
      "target2",
    ]);
    expect(levels.map((l) => l.price)).toEqual([100, 95, 110, 120]);
  });

  it("anti-ruido: sin permiso de niveles (vigilar) no dibuja nada", () => {
    expect(
      buildOperationalPlanChartLevels({ plan: plan(), showLevels: false }),
    ).toEqual([]);
  });

  it("sin plan no dibuja nada", () => {
    expect(
      buildOperationalPlanChartLevels({
        plan: plan({ hasPlan: false }),
        showLevels: true,
      }),
    ).toEqual([]);
  });

  it("omite niveles no finitos", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan({ target1: null, target2: null }),
      showLevels: true,
    });
    expect(levels.map((l) => l.kind)).toEqual(["entry", "stopVigente"]);
  });

  it("trailing sugerido es advisory y nunca comparte estilo con el stop vigente", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan({ trailingActive: true, trailingStopHint: 101 }),
      showLevels: true,
      includeTrailing: true,
    });
    const stop = levels.find((l) => l.kind === "stopVigente")!;
    const trail = levels.find((l) => l.kind === "trailingHint")!;
    expect(trail.advisory).toBe(true);
    expect(stop.advisory).toBe(false);
    expect(trail.style).toBe("dashed");
    expect(stop.style).toBe("solid");
    expect(trail.color).not.toBe(stop.color);
    expect(trail.width).toBeLessThan(stop.width);
    // El trail no reemplaza el stop vigente: ambos niveles coexisten.
    expect(stop.price).toBe(95);
    expect(trail.price).toBe(101);
  });

  it("includeTrailing: false oculta la propuesta trail", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan({ trailingActive: true, trailingStopHint: 101 }),
      showLevels: true,
      includeTrailing: false,
    });
    expect(levels.some((l) => l.kind === "trailingHint")).toBe(false);
  });

  it("V2.14 — prepared phase draws trigger (not entry duplicate)", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan({ phase: "prepared", phaseLabel: "Preparada" }),
      showLevels: true,
    });
    expect(levels.some((l) => l.kind === "trigger")).toBe(true);
    expect(levels.find((l) => l.kind === "trigger")?.title).toBe("Trigger");
    expect(levels.some((l) => l.kind === "entry")).toBe(false);
  });

  it("V2.14 — bootstrap stop is advisory amber, not technical red", () => {
    const levels = buildOperationalPlanChartLevels({
      plan: plan(),
      showLevels: true,
      stopIsBootstrap: true,
    });
    const boot = levels.find((l) => l.kind === "stopBootstrap")!;
    expect(boot.advisory).toBe(true);
    expect(boot.style).toBe("dashed");
    expect(boot.title).toMatch(/emergencia/i);
    expect(levels.some((l) => l.kind === "stopVigente")).toBe(false);
  });
});
