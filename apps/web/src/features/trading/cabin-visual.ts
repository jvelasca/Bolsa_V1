/**
 * V2.31 — Premium Visual System (cabina Mercado A–B).
 * Tres tamaños: héroe · operativa · meta. Números financieros tabulares.
 * Display-only · sin paneles nuevos · sin controles AUTO.
 *
 * @see docs/engineering/traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md
 */

import { cn } from "@/lib/utils";

export const CABIN_VISUAL_VERSION = "v2.31";

/**
 * Tipografía de cabina — solo 3 tamaños.
 * Floor = meta (~11px). No usar text-[9px] / text-[10px] en nivel A–B.
 */
export const CABIN_TYPE = {
  hero: "cabin-type-hero text-foreground",
  operativa: "cabin-type-operativa text-foreground",
  meta: "cabin-type-meta text-muted-foreground",
  eyebrow:
    "cabin-type-meta font-semibold uppercase tracking-wider text-muted-foreground/90",
  /** @deprecated V2.31 — alias de `hero`. */
  heroTitle: "cabin-type-hero text-foreground",
  /** @deprecated V2.31 — alias de `operativa`. */
  body: "cabin-type-operativa text-foreground",
  /** Número operativo (B): tabular · semibold · sin relleno. */
  value:
    "cabin-type-operativa font-semibold tabular-nums tracking-tight text-foreground",
} as const;

export type CabinTypeSize = "hero" | "operativa" | "meta";
export type CabinNumTone = "pos" | "neg" | "neu";

/** Números financieros: tabular + peso + color semántico (texto, no cards). */
export const CABIN_NUM = {
  base: "font-semibold tabular-nums tracking-tight",
  hero: "cabin-type-hero tabular-nums tracking-tight",
  pos: "text-emerald-700 dark:text-emerald-300",
  neg: "text-rose-700 dark:text-rose-300",
  neu: "text-foreground",
} as const;

export function cabinNumTone(value: number | null | undefined): CabinNumTone {
  if (value == null || !Number.isFinite(value) || value === 0) return "neu";
  return value > 0 ? "pos" : "neg";
}

export function cabinNumClass(opts?: {
  size?: CabinTypeSize;
  signed?: boolean;
  value?: number | null;
}): string {
  const size = opts?.size ?? "operativa";
  const tone = opts?.signed ? cabinNumTone(opts.value) : "neu";
  return cn(
    size === "hero"
      ? CABIN_TYPE.hero
      : size === "meta"
        ? CABIN_TYPE.meta
        : CABIN_TYPE.operativa,
    CABIN_NUM.base,
    CABIN_NUM[tone],
  );
}

/** Grid B-level (Entrada · Stop · Riesgo · T1…). Labels = meta. */
export const CABIN_KV_GRID =
  "grid grid-cols-2 gap-x-3 gap-y-0.5 cabin-type-meta text-muted-foreground";
