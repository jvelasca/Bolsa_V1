/**
 * U5 — proyección visual de orden F3 en gráfico (precio + etiqueta).
 *
 * Solo resuelve datos de cola SEMI; no firma ni ejecuta.
 * La línea en chart es efímera (`createPriceLine`); no se persiste como drawing.
 *
 * @see apps/web/src/features/charts/chart-f3-order-projection-layer.tsx
 * @see apps/web/src/features/trading/decision-package-chips.ts
 */

import type { DecisionAction } from "@bolsa/shared";
import {
  DECISION_ACTION_CHIP_LABEL,
  parseDecisionAction,
  pickQueueItemForInstrument,
} from "@/features/trading/decision-package-chips";

/** Id estable de la priceLine en lightweight-charts (no drawing store). */
export const F3_ORDER_PROJECTION_LINE_ID = "f3-order-projection" as const;

export type F3OrderProjectionView = {
  queueItemId: string;
  instrumentId: string;
  price: number;
  /** Etiqueta eje / título (p. ej. «F3 · LONG @ 12.34»). */
  label: string;
  action: DecisionAction | null;
  actionLabel: string;
  /** Color hex alineado con chips U4 (sin glow). */
  color: string;
};

const PACKAGE_PRICE_KEYS = [
  "suggestedPrice",
  "entryPrice",
  "limitPrice",
  "price",
  "lastClose",
  "referencePrice",
  "refPrice",
] as const;

/** Número finito > 0, o null (fail soft). */
export function coercePositivePrice(raw: unknown): number | null {
  if (typeof raw === "number") {
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  }
  if (typeof raw === "string" && raw.trim()) {
    const n = Number(raw.trim().replace(",", "."));
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  return null;
}

function readPackagePrice(
  pkg: Record<string, unknown> | null | undefined,
): number | null {
  if (!pkg || typeof pkg !== "object") return null;
  for (const key of PACKAGE_PRICE_KEYS) {
    const px = coercePositivePrice(pkg[key]);
    if (px != null) return px;
  }
  return null;
}

function readSessionPrice(session: unknown): number | null {
  if (!session || typeof session !== "object") return null;
  const s = session as Record<string, unknown>;
  const direct = coercePositivePrice(s.priceAtDecision);
  if (direct != null) return direct;
  const outcome = s.outcome;
  if (outcome && typeof outcome === "object") {
    return coercePositivePrice(
      (outcome as Record<string, unknown>).priceAtDecision,
    );
  }
  return null;
}

/**
 * Precio resoluble para proyección.
 * Prioridad: suggestedPrice → lastClose → decisionPackage → session/outcome.
 */
export function resolveF3ProjectionPrice(payload: {
  suggestedPrice?: unknown;
  lastClose?: unknown;
  decisionPackage?: Record<string, unknown> | null;
  decisionSession?: unknown;
}): number | null {
  return (
    coercePositivePrice(payload.suggestedPrice) ??
    coercePositivePrice(payload.lastClose) ??
    readPackagePrice(payload.decisionPackage ?? null) ??
    readSessionPrice(payload.decisionSession) ??
    null
  );
}

/** Acción compacta LONG/SHORT/… (misma tabla que U4). */
export function resolveF3ProjectionActionLabel(input: {
  packageAction?: unknown;
  recommendationAction?: unknown;
}): { action: DecisionAction; label: string } | null {
  const action =
    parseDecisionAction(input.packageAction) ??
    parseDecisionAction(input.recommendationAction);
  if (!action) return null;
  return { action, label: DECISION_ACTION_CHIP_LABEL[action] };
}

/** Formato compacto para el eje (sin €; la escala ya es precio). */
export function formatF3ProjectionPrice(price: number): string {
  if (!Number.isFinite(price)) return "—";
  const abs = Math.abs(price);
  if (abs >= 1000) return price.toFixed(2);
  if (abs >= 1) return price.toFixed(2);
  return price.toFixed(4).replace(/\.?0+$/, "") || String(price);
}

export function formatF3ProjectionLabel(input: {
  actionLabel?: string | null;
  price: number;
}): string {
  const px = formatF3ProjectionPrice(input.price);
  const side = input.actionLabel?.trim();
  if (side) return `F3 · ${side} @ ${px}`;
  return `F3 @ ${px}`;
}

export function f3ProjectionColor(action: DecisionAction | null): string {
  switch (action) {
    case "recommend_long":
      return "#059669";
    case "recommend_short":
    case "exit_hint":
    case "reduce":
      return "#e11d48";
    case "wait":
      return "#78716c";
    default:
      return "#57534e";
  }
}

/** Vista completa desde un ítem de cola; null si no hay precio. */
export function resolveF3OrderProjection(item: {
  id: string;
  payload: {
    instrumentId?: string;
    action?: unknown;
    suggestedPrice?: unknown;
    lastClose?: unknown;
    decisionPackage?: Record<string, unknown> | null;
    decisionSession?: unknown;
  };
}): F3OrderProjectionView | null {
  const instrumentId = item.payload.instrumentId;
  if (!instrumentId) return null;

  const price = resolveF3ProjectionPrice(item.payload);
  if (price == null) return null;

  const pkg = item.payload.decisionPackage ?? null;
  const side = resolveF3ProjectionActionLabel({
    packageAction: pkg?.action,
    recommendationAction: item.payload.action,
  });

  return {
    queueItemId: item.id,
    instrumentId,
    price,
    action: side?.action ?? null,
    actionLabel: side?.label ?? "",
    label: formatF3ProjectionLabel({
      actionLabel: side?.label,
      price,
    }),
    color: f3ProjectionColor(side?.action ?? null),
  };
}

/**
 * Proyección para el instrumento del gráfico activo (cola F3).
 * Preferencia: ítem activo de la cola si pertenece al instrumento.
 */
export function resolveF3OrderProjectionForInstrument<
  T extends {
    id: string;
    payload: {
      instrumentId?: string;
      action?: unknown;
      suggestedPrice?: unknown;
      lastClose?: unknown;
      decisionPackage?: Record<string, unknown> | null;
      decisionSession?: unknown;
    };
  },
>(
  items: T[],
  instrumentId: string | null | undefined,
  activeId?: string | null,
): F3OrderProjectionView | null {
  const item = pickQueueItemForInstrument(items, instrumentId, activeId);
  if (!item) return null;
  return resolveF3OrderProjection(item);
}
