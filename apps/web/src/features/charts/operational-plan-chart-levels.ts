/**
 * Niveles del plan operativo para el gráfico (proyección pura, sin lightweight-charts).
 *
 * Fuente = `OperationalPlanView` (la misma que Operativa / Hoy / Journal): no hay
 * un segundo stop. El trailing es **advisory** y nunca comparte estilo con el
 * stop vigente (ADR-041 · ADR-033).
 * V2.14 — trigger line · bootstrap stop = advisory (ámbar), no rojo técnico.
 * V2.30 — Chart Focus: Simple (Entrada · Stop · próximo objetivo) /
 * Completo (todas) · T1 alcanzado discreto (sin competir con T2).
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §2
 */

import type { OperationalPlanViewV1 } from "@bolsa/shared";
import type { ChartFocusModeV1 } from "@/features/charts/chart-focus-prefs";

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
  /** V2.30 — T1 tocado/alcanzado: no compite visualmente con el próximo objetivo. */
  dimmed?: boolean;
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
  /** T1 alcanzado: verde apagado (discreto). */
  target1Reached: "#86efac",
  target2: "#4ade80",
  /** T2 como próximo objetivo tras T1. */
  target2Next: "#22c55e",
  /** Ámbar punteado: se lee como propuesta, no como protección vigente. */
  trailingHint: "#f59e0b",
} as const;

function finite(n: number | null | undefined): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function levelId(kind: OperationalPlanChartLevelKind): string {
  return `${OPERATIONAL_PLAN_LEVEL_ID_PREFIX}:${kind}`;
}

function t1IsReached(plan: OperationalPlanViewV1): boolean {
  return Boolean(plan.target1Reached || plan.target1Touched);
}

function formatT1Title(opts: {
  t1Pct: number | null;
  reached: boolean;
}): string {
  const pct =
    opts.t1Pct != null && Number.isFinite(opts.t1Pct)
      ? ` · ${Math.round(opts.t1Pct)} %`
      : "";
  if (opts.reached) return `✓ T1 alcanzado${pct}`;
  return opts.t1Pct != null && Number.isFinite(opts.t1Pct)
    ? `T1 · ${Math.round(opts.t1Pct)}%`
    : "T1";
}

function formatT2Title(opts: {
  t2Pct: number | null;
  isNext: boolean;
}): string {
  if (opts.isNext) {
    const pct =
      opts.t2Pct != null && Number.isFinite(opts.t2Pct)
        ? ` · ${Math.round(opts.t2Pct)}%`
        : "";
    return `T2 · siguiente${pct}`;
  }
  return opts.t2Pct != null && Number.isFinite(opts.t2Pct)
    ? `T2 · ${Math.round(opts.t2Pct)}%`
    : "T2";
}

/**
 * Niveles a pintar. `showLevels: false` (VIGILAR / DESCUBIERTO) devuelve vacío:
 * sin plan no se dibuja Entrada/Stop/T1/T2.
 *
 * V2.30 `focusMode`:
 * - `simple` — Entrada (o Trigger en prepared) · Stop · próximo objetivo
 * - `completo` — todas las líneas (comportamiento previo)
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
  /** V2.26 — ExitPolicy reduce % for T1/T2 titles (never hardcode 25). */
  t1ReducePct?: number | null;
  t2ReducePct?: number | null;
  /** V2.30 — densidad de líneas en gráfico. Default `completo` (compat tests). */
  focusMode?: ChartFocusModeV1;
}): OperationalPlanChartLevel[] {
  const plan = input.plan;
  if (!input.showLevels || !plan || !plan.hasPlan) return [];

  const focusMode: ChartFocusModeV1 = input.focusMode ?? "completo";
  const simple = focusMode === "simple";
  const t1Reached = t1IsReached(plan);
  const t1Pct =
    input.t1ReducePct != null && Number.isFinite(input.t1ReducePct)
      ? Math.round(input.t1ReducePct)
      : null;
  const t2Pct =
    input.t2ReducePct != null && Number.isFinite(input.t2ReducePct)
      ? Math.round(input.t2ReducePct)
      : null;

  const levels: OperationalPlanChartLevel[] = [];

  const trigger = finite(input.triggerPrice)
    ? input.triggerPrice
    : plan.phase === "prepared" && finite(plan.entry)
      ? plan.entry
      : null;

  if (finite(trigger) && plan.phase === "prepared") {
    // Simple y Completo: Trigger es la referencia de ruptura en prepared.
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
    // Completo: entry visible when distinct from trigger.
    // Simple: solo Trigger (no duplicar).
    if (
      !simple &&
      (!finite(trigger) || Math.abs(plan.entry - trigger) > 1e-9)
    ) {
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

  // Simple: próximo objetivo = T1 (si no tocado) o T2 (si T1 alcanzado).
  // Completo: T1 discreto al alcanzarse + T2 enfatizado como siguiente.
  if (finite(plan.target1) && !(simple && t1Reached)) {
    const dimmed = t1Reached;
    levels.push({
      id: levelId("target1"),
      kind: "target1",
      price: plan.target1,
      title: formatT1Title({ t1Pct, reached: dimmed }),
      color: dimmed ? LEVEL_COLORS.target1Reached : LEVEL_COLORS.target1,
      style: dimmed ? "dashed" : "solid",
      width: dimmed ? 1 : 2,
      advisory: false,
      dimmed: dimmed || undefined,
    });
  }

  if (finite(plan.target2)) {
    const isNext = t1Reached;
    const includeT2 = !simple || isNext || !finite(plan.target1);
    if (includeT2) {
      levels.push({
        id: levelId("target2"),
        kind: "target2",
        price: plan.target2,
        title: formatT2Title({ t2Pct, isNext }),
        color: isNext ? LEVEL_COLORS.target2Next : LEVEL_COLORS.target2,
        style: isNext ? "solid" : "dashed",
        width: isNext ? 2 : 1,
        advisory: false,
      });
    }
  }

  if (
    !simple &&
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
  return levels
    .map(
      (l) =>
        `${l.kind}@${l.price}@${l.title}@${l.dimmed ? "d" : "n"}@${l.width}`,
    )
    .join("|");
}
