/**
 * Niveles del plan operativo para el gráfico (proyección pura, sin lightweight-charts).
 *
 * Fuente = `OperationalPlanView` (la misma que Operativa / Hoy / Journal): no hay
 * un segundo stop. El trailing es **advisory** y nunca comparte estilo con el
 * stop vigente (ADR-041 · ADR-033).
 * V2.14 — trigger line · bootstrap stop = advisory (ámbar), no rojo técnico.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §2
 */

import type { OperationalPlanViewV1 } from "@bolsa/shared";

export type OperationalPlanChartLevelKind =
  | "entry"
  | "trigger"
  | "stopVigente"
  | "stopBootstrap"
  | "target1"
  | "target2"
  | "trailingHint";

export type OperationalPlanChartLevelStyle = "solid" | "dashed";

export type OperationalPlanChartLevel = {
  /** ID estable de la priceLine (permite reconciliar sin recrear el gráfico). */
  id: string;
  kind: OperationalPlanChartLevelKind;
  price: number;
  title: string;
  color: string;
  style: OperationalPlanChartLevelStyle;
  width: 1 | 2;
  /** Propuesta, no autoridad: el trail/bootstrap no manda sobre el stop vigente. */
  advisory: boolean;
};

export const OPERATIONAL_PLAN_LEVEL_ID_PREFIX = "plan-level";

const LEVEL_COLORS = {
  entry: "#38bdf8",
  /** Trigger de ruptura — distinto de entry (fill). */
  trigger: "#a78bfa",
  stopVigente: "#ef4444",
  /** Emergency bootstrap −5% — never same red as technical stop. */
  stopBootstrap: "#f59e0b",
  target1: "#22c55e",
  target2: "#4ade80",
  /** Ámbar punteado: se lee como propuesta, no como protección vigente. */
  trailingHint: "#f59e0b",
} as const;

function finite(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function levelId(kind: OperationalPlanChartLevelKind): string {
  return `${OPERATIONAL_PLAN_LEVEL_ID_PREFIX}:${kind}`;
}

/**
 * Niveles a pintar. `showLevels: false` (VIGILAR / DESCUBIERTO) devuelve vacío:
 * sin plan no se dibuja Entrada/Stop/T1/T2.
 */
export function buildOperationalPlanChartLevels(input: {
  plan: OperationalPlanViewV1 | null | undefined;
  showLevels: boolean;
  /** El trail solo tiene sentido en posición abierta. */
  includeTrailing?: boolean;
  /**
   * V2.14 — optional trigger price (breakout). When omitted and phase=prepared,
   * uses entry as trigger line.
   */
  triggerPrice?: number | null;
  /**
   * V2.14 — when true, stopVigente is painted as emergency bootstrap (amber advisory).
   */
  stopIsBootstrap?: boolean;
  /**
   * V2.14 — when plan has no stop but we have an emergency suggestion, paint it advisory.
   */
  bootstrapStopPrice?: number | null;
}): OperationalPlanChartLevel[] {
  const plan = input.plan;
  if (!input.showLevels || !plan || !plan.hasPlan) return [];

  const levels: OperationalPlanChartLevel[] = [];

  const trigger = finite(input.triggerPrice)
    ? input.triggerPrice
    : plan.phase === "prepared" && finite(plan.entry)
      ? plan.entry
      : null;

  if (finite(trigger) && plan.phase === "prepared") {
    levels.push({
      id: levelId("trigger"),
      kind: "trigger",
      price: trigger,
      title: "Trigger",
      color: LEVEL_COLORS.trigger,
      style: "dashed",
      width: 1,
      advisory: false,
    });
  }

  if (finite(plan.entry) && plan.phase !== "prepared") {
    levels.push({
      id: levelId("entry"),
      kind: "entry",
      price: plan.entry,
      title: "Entrada",
      color: LEVEL_COLORS.entry,
      style: "dashed",
      width: 1,
      advisory: false,
    });
  } else if (finite(plan.entry) && plan.phase === "prepared") {
    // Keep entry visible when distinct from trigger (same price → skip duplicate)
    if (!finite(trigger) || Math.abs(plan.entry - trigger) > 1e-9) {
      levels.push({
        id: levelId("entry"),
        kind: "entry",
        price: plan.entry,
        title: "Entrada",
        color: LEVEL_COLORS.entry,
        style: "dashed",
        width: 1,
        advisory: false,
      });
    }
  }

  if (finite(plan.stopVigente)) {
    if (input.stopIsBootstrap) {
      levels.push({
        id: levelId("stopBootstrap"),
        kind: "stopBootstrap",
        price: plan.stopVigente,
        title: "Stop emergencia (−5 %)",
        color: LEVEL_COLORS.stopBootstrap,
        style: "dashed",
        width: 1,
        advisory: true,
      });
    } else {
      levels.push({
        id: levelId("stopVigente"),
        kind: "stopVigente",
        price: plan.stopVigente,
        title: "Stop vigente",
        color: LEVEL_COLORS.stopVigente,
        style: "solid",
        width: 2,
        advisory: false,
      });
    }
  } else if (finite(input.bootstrapStopPrice)) {
    levels.push({
      id: levelId("stopBootstrap"),
      kind: "stopBootstrap",
      price: input.bootstrapStopPrice,
      title: "Stop emergencia (−5 %)",
      color: LEVEL_COLORS.stopBootstrap,
      style: "dashed",
      width: 1,
      advisory: true,
    });
  }
  if (finite(plan.target1)) {
    levels.push({
      id: levelId("target1"),
      kind: "target1",
      price: plan.target1,
      title: "T1",
      color: LEVEL_COLORS.target1,
      style: "solid",
      width: 2,
      advisory: false,
    });
  }
  if (finite(plan.target2)) {
    levels.push({
      id: levelId("target2"),
      kind: "target2",
      price: plan.target2,
      title: "T2",
      color: LEVEL_COLORS.target2,
      style: "dashed",
      width: 1,
      advisory: false,
    });
  }
  if (
    input.includeTrailing !== false &&
    plan.trailingActive &&
    finite(plan.trailingStopHint)
  ) {
    levels.push({
      id: levelId("trailingHint"),
      kind: "trailingHint",
      price: plan.trailingStopHint,
      title: "Stop sugerido (trail)",
      color: LEVEL_COLORS.trailingHint,
      style: "dashed",
      width: 1,
      advisory: true,
    });
  }

  return levels;
}

/** Firma estable para reconciliar priceLines sin recrearlas cada render. */
export function operationalPlanChartLevelsSignature(
  levels: readonly OperationalPlanChartLevel[],
): string {
  return levels.map((l) => `${l.kind}@${l.price}`).join("|");
}
