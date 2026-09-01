/**
 * V1.62 — Entry Decision Surface helpers (tono, headline, ejecución).
 * Display-only — no firma · no BUY.
 */

import type {
  EntryOperatingCtaV1,
  EntryOperatingPhaseV1,
  ExecutionStateV1,
} from "@bolsa/shared";

export type EntryVisualToneV1 = "sky" | "amber" | "teal" | "rose" | "muted";

export function entryPhaseTone(
  phase: EntryOperatingPhaseV1,
  opts: {
    entriesBlocked?: boolean;
    gateStatus?: string | null;
  } = {},
): EntryVisualToneV1 {
  if (opts.entriesBlocked) return "rose";
  const gate = opts.gateStatus?.toUpperCase();
  if (gate === "VETO" || gate === "DEFERRED") return "rose";
  switch (phase) {
    case "preparada":
      return "sky";
    case "disparada":
    case "propuesta":
      return "amber";
    case "confirmada":
      return "teal";
    default:
      return "muted";
  }
}

export function entryPhaseToneClasses(tone: EntryVisualToneV1): string {
  switch (tone) {
    case "sky":
      return "border-sky-700/30 bg-sky-500/5";
    case "amber":
      return "border-amber-700/30 bg-amber-500/5";
    case "teal":
      return "border-teal-700/30 bg-teal-500/5";
    case "rose":
      return "border-rose-700/30 bg-rose-500/5";
    case "muted":
      return "border-border/60 bg-muted/15";
  }
}

export function entryPhaseHeadline(phase: EntryOperatingPhaseV1): string {
  switch (phase) {
    case "preparada":
      return "Entrada preparada";
    case "disparada":
      return "Disparo activo";
    case "propuesta":
      return "Propuesta lista";
    case "confirmada":
      return "En ejecución";
    default:
      return "Entrada";
  }
}

export type EntryExecutionCopyV1 = "NO REQUERIDA" | "PENDIENTE" | "EJECUTADA";

export function entryExecutionStateLabel(
  phase: EntryOperatingPhaseV1,
  primaryCta: EntryOperatingCtaV1,
  execution?: ExecutionStateV1 | null,
): EntryExecutionCopyV1 {
  if (execution?.lifecycle === "filled") return "EJECUTADA";
  if (
    execution?.lifecycle === "in_flight" ||
    execution?.lifecycle === "unknown" ||
    execution?.orderState === "pending"
  ) {
    return "PENDIENTE";
  }
  if (phase === "confirmada") return "PENDIENTE";
  if (phase === "disparada" || phase === "propuesta") {
    if (primaryCta.kind === "review_confirm") return "PENDIENTE";
  }
  if (primaryCta.kind === "none") return "NO REQUERIDA";
  return "NO REQUERIDA";
}

export function entryDecisionLabel(primaryCta: EntryOperatingCtaV1): string {
  return primaryCta.label;
}

export function formatEntryLevel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}
