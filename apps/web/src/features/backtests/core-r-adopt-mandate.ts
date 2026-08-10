/**
 * Adoptar mandato desde cola CORE-R (SEMI Confirm · Fase C).
 *
 * Humano confirma propuesta «Valorar cambio» → tenure ADR-020.
 * No auto-adopta en AUTO execute. No pisa TOP.
 *
 * @see docs/engineering/list-auto-ops-2026-07-29.md §5.2
 * @see docs/adr/020-operating-mandate-tenure.md
 */

import type {
  InstrumentStrategyTopSlotV1,
  InstrumentStrategyTopV1,
} from "@bolsa/shared";
import {
  setAdoption,
  type StrategyAdoptionRecord,
} from "@/features/platform/strategy-adoption";
import {
  demoBookAllowsExecute,
  loadDemoBookPrefs,
  type DemoBookMode,
} from "@/features/trading/demo-book-prefs";
import type { CoreRVerdict } from "@/features/backtests/core-r-judgment";

export const CORE_R_ADOPT_VERDICTS: ReadonlySet<CoreRVerdict> = new Set([
  "consider_replace",
]);

export type CoreRAdoptMandateResult =
  | {
      ok: true;
      record: StrategyAdoptionRecord;
      slot: InstrumentStrategyTopSlotV1;
    }
  | { ok: false; reason: CoreRAdoptMandateDenyReason };

export type CoreRAdoptMandateDenyReason =
  | "no_account"
  | "not_semi"
  | "wrong_verdict"
  | "no_slot"
  | "no_strategy";

/** Slot #1 usable para adoptar mandato (strategyDefinitionId). */
export function coreRAdoptSlotFromTop(
  top: InstrumentStrategyTopV1 | null | undefined,
): InstrumentStrategyTopSlotV1 | null {
  if (!top?.slots?.length) return null;
  const byRank = top.slots.find((s) => s.rank === 1);
  const slot = byRank ?? top.slots[0] ?? null;
  if (!slot?.strategyDefinitionId) return null;
  return slot;
}

export function coreRAdoptAllowedForVerdict(verdict: CoreRVerdict): boolean {
  return CORE_R_ADOPT_VERDICTS.has(verdict);
}

export function coreRAdoptAllowedForMode(mode: DemoBookMode): boolean {
  // Solo SEMI: Confirm humano. AUTO execute no adopta mandato.
  return demoBookAllowsExecute(mode);
}

/**
 * ¿Mostrar CTA «Adoptar» en fila de cola?
 * SEMI + «Valorar cambio» + cuenta. TOP#1 se valida al pulsar (fetch si falta).
 */
export function canAdoptCoreRMandate(opts: {
  verdict: CoreRVerdict;
  mode?: DemoBookMode | null;
  accountId?: string | null;
  /** Si se pasa y no hay slot usable, oculta el CTA. */
  top?: InstrumentStrategyTopV1 | null;
}): boolean {
  const mode = opts.mode ?? loadDemoBookPrefs().mode;
  if (!opts.accountId) return false;
  if (!coreRAdoptAllowedForMode(mode)) return false;
  if (!coreRAdoptAllowedForVerdict(opts.verdict)) return false;
  if (
    opts.top !== undefined &&
    opts.top !== null &&
    !coreRAdoptSlotFromTop(opts.top)
  ) {
    return false;
  }
  return true;
}

/**
 * Abre mandato vigente desde Finalista TOP#1 (propuesta CORE-R aceptada).
 * Actor `core_r` + reason `propose_accepted` para churn M3.
 */
export function adoptMandateFromCoreR(opts: {
  instrumentId: string;
  accountId: string;
  verdict: CoreRVerdict;
  timeframe: string;
  top: InstrumentStrategyTopV1 | null | undefined;
  mode?: DemoBookMode | null;
}): CoreRAdoptMandateResult {
  const mode = opts.mode ?? loadDemoBookPrefs().mode;
  if (!opts.accountId) return { ok: false, reason: "no_account" };
  if (!coreRAdoptAllowedForMode(mode)) return { ok: false, reason: "not_semi" };
  if (!coreRAdoptAllowedForVerdict(opts.verdict)) {
    return { ok: false, reason: "wrong_verdict" };
  }
  const slot = coreRAdoptSlotFromTop(opts.top);
  if (!slot) return { ok: false, reason: "no_slot" };
  if (!slot.strategyDefinitionId) return { ok: false, reason: "no_strategy" };

  const evidenceLevel =
    opts.top?.evidenceLevel === "lab_validated" ||
    opts.top?.evidenceLevel === "in_sample_only"
      ? opts.top.evidenceLevel
      : null;

  const record = setAdoption({
    instrumentId: opts.instrumentId,
    accountId: opts.accountId,
    state: "adoptada",
    strategyDefinitionId: slot.strategyDefinitionId,
    strategyLabel: slot.label ?? null,
    timeframe: opts.timeframe || opts.top?.timeframe || "1d",
    actor: "core_r",
    reason: "propose_accepted",
    sourceTopId: opts.top?.id ?? null,
    sourceTopVersion: opts.top?.version ?? null,
    evidenceLevel,
  });

  return { ok: true, record, slot };
}

export function coreRAdoptDenyMessage(
  reason: CoreRAdoptMandateDenyReason,
): string {
  switch (reason) {
    case "no_account":
      return "Selecciona una cuenta activa.";
    case "not_semi":
      return "Adoptar mandato solo en modo SEMI (Operativa).";
    case "wrong_verdict":
      return "Solo para juicios «Valorar cambio».";
    case "no_slot":
      return "Sin Finalista #1 en TOP.";
    case "no_strategy":
      return "El Finalista #1 no tiene estrategia.";
    default:
      return "No se pudo adoptar.";
  }
}
