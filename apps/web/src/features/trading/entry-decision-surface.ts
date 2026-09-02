/**
 * V1.62 — Entry Decision Surface helpers (tono, headline, ejecución).
 * V1.71 — unknown/failed → REVISAR · assertNever.
 * Display-only — no firma · no BUY.
 */

import type {
  EntryOperatingCtaV1,
  EntryOperatingPhaseV1,
  ExecutionStateV1,
} from "@bolsa/shared";
import { assertNever } from "@bolsa/shared";

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
      return assertNever(phase);
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
      return assertNever(phase);
  }
}

export type EntryExecutionCopyV1 =
  | "NO REQUERIDA"
  | "PENDIENTE"
  | "EJECUTADA"
  | "REVISAR";

export function entryExecutionStateLabel(
  phase: EntryOperatingPhaseV1,
  primaryCta: EntryOperatingCtaV1,
  execution?: ExecutionStateV1 | null,
): EntryExecutionCopyV1 {
  const lifecycle = execution?.lifecycle;
  if (lifecycle === "filled" || lifecycle === "reconciled") return "EJECUTADA";
  if (lifecycle === "unknown" || lifecycle === "failed") return "REVISAR";
  if (
    lifecycle === "in_flight" ||
    lifecycle === "submit" ||
    execution?.orderState === "pending"
  ) {
    return "PENDIENTE";
  }
  if (phase === "confirmada") return "PENDIENTE";
  if (phase === "disparada" || phase === "propuesta") {
    if (primaryCta.kind === "review_confirm") return "PENDIENTE";
  }
  return "NO REQUERIDA";
}

export function entryDecisionLabel(primaryCta: EntryOperatingCtaV1): string {
  return primaryCta.label;
}

export function formatEntryLevel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(2);
}
