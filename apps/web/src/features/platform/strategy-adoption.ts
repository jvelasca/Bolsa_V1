/**
 * Adopción TOP → TRADING por instrumento × cuenta (ADR-019 U4).
 *
 * Distinto de `lab-adoption-memory` (params Lab). Aquí: estado de puente producto.
 * Tras ADR-020: proyección del mandato vigente + estados candidata/propuesta/obsoleta.
 * Historial de playbooks: `operating-mandate.ts` (MandateTenure).
 *
 * @see docs/adr/020-operating-mandate-tenure.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md §5.1
 */

import {
  applyMandateChange,
  notifyMandateStoreListeners,
  seedMandateFromAdoption,
  type MandateActor,
  type MandateReason,
} from "@/features/platform/operating-mandate";

export const STRATEGY_ADOPTION_KEY = "bolsa-strategy-adoption-v1";
export const STRATEGY_ADOPTION_ENGINE = "strategy-adoption-v1" as const;

export type StrategyAdoptionState =
  | "none"
  | "candidata"
  | "adoptada"
  | "propuesta"
  | "obsoleta";

export const STRATEGY_ADOPTION_LABELS: Record<StrategyAdoptionState, string> = {
  none: "Sin adopción",
  candidata: "Candidata",
  adoptada: "Adoptada",
  propuesta: "Propuesta",
  obsoleta: "Obsoleta",
};

export type StrategyAdoptionRecord = {
  engine: typeof STRATEGY_ADOPTION_ENGINE;
  instrumentId: string;
  accountId: string;
  state: Exclude<StrategyAdoptionState, "none">;
  strategyDefinitionId?: string | null;
  strategyLabel?: string | null;
  timeframe?: string | null;
  updatedAt: string;
  /** Tenure abierto asociado (si estado adoptada). */
  mandateTenureId?: string | null;
};

export type StrategyAdoptionStore = Record<string, StrategyAdoptionRecord>;

export function adoptionKey(instrumentId: string, accountId: string): string {
  return `${instrumentId}::${accountId}`;
}

export function readAdoptionStore(): StrategyAdoptionStore {
  if (typeof localStorage === "undefined") return {};
  try {
    const raw = localStorage.getItem(STRATEGY_ADOPTION_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StrategyAdoptionStore;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeAdoptionStore(store: StrategyAdoptionStore): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STRATEGY_ADOPTION_KEY, JSON.stringify(store));
  notifyMandateStoreListeners();
}

export function getAdoption(
  instrumentId: string,
  accountId: string | null | undefined,
): StrategyAdoptionRecord | null {
  if (!accountId) return null;
  const rec = readAdoptionStore()[adoptionKey(instrumentId, accountId)] ?? null;
  if (
    rec?.state === "adoptada" &&
    rec.strategyDefinitionId &&
    !rec.mandateTenureId
  ) {
    const seeded = seedMandateFromAdoption({
      instrumentId,
      accountId,
      strategyDefinitionId: rec.strategyDefinitionId,
      strategyLabel: rec.strategyLabel,
      timeframe: rec.timeframe,
      updatedAt: rec.updatedAt,
    });
    if (seeded) {
      const store = readAdoptionStore();
      const next = {
        ...rec,
        mandateTenureId: seeded.id,
      };
      store[adoptionKey(instrumentId, accountId)] = next;
      writeAdoptionStore(store);
      return next;
    }
  }
  return rec;
}

export function getAdoptionState(
  instrumentId: string,
  accountId: string | null | undefined,
): StrategyAdoptionState {
  return getAdoption(instrumentId, accountId)?.state ?? "none";
}

export function setAdoption(input: {
  instrumentId: string;
  accountId: string;
  state: Exclude<StrategyAdoptionState, "none">;
  strategyDefinitionId?: string | null;
  strategyLabel?: string | null;
  timeframe?: string | null;
  actor?: MandateActor;
  reason?: MandateReason;
  sourceTopId?: string | null;
  sourceTopVersion?: number | null;
  evidenceLevel?: "in_sample_only" | "lab_validated" | null;
}): StrategyAdoptionRecord {
  let mandateTenureId: string | null = null;

  if (input.state === "adoptada") {
    const { opened } = applyMandateChange({
      instrumentId: input.instrumentId,
      accountId: input.accountId,
      open: {
        strategyDefinitionId: input.strategyDefinitionId,
        strategyLabelSnapshot: input.strategyLabel,
        timeframe: input.timeframe,
        actor: input.actor ?? "user",
        reason: input.reason,
        sourceTopId: input.sourceTopId,
        sourceTopVersion: input.sourceTopVersion,
        evidenceLevel: input.evidenceLevel,
      },
    });
    mandateTenureId = opened?.id ?? null;
  } else if (input.state === "obsoleta") {
    applyMandateChange({
      instrumentId: input.instrumentId,
      accountId: input.accountId,
      open: null,
      // reason obsolete is implicit by closing without reopen
    });
  } else if (
    input.state === "propuesta" &&
    input.reason === "propose_accepted"
  ) {
    const { opened } = applyMandateChange({
      instrumentId: input.instrumentId,
      accountId: input.accountId,
      open: {
        strategyDefinitionId: input.strategyDefinitionId,
        strategyLabelSnapshot: input.strategyLabel,
        timeframe: input.timeframe,
        actor: input.actor ?? "user",
        reason: "propose_accepted",
        sourceTopId: input.sourceTopId,
        sourceTopVersion: input.sourceTopVersion,
        evidenceLevel: input.evidenceLevel,
      },
    });
    mandateTenureId = opened?.id ?? null;
  }

  const store = readAdoptionStore();
  const record: StrategyAdoptionRecord = {
    engine: STRATEGY_ADOPTION_ENGINE,
    instrumentId: input.instrumentId,
    accountId: input.accountId,
    state: input.state,
    strategyDefinitionId: input.strategyDefinitionId ?? null,
    strategyLabel: input.strategyLabel ?? null,
    timeframe: input.timeframe ?? null,
    updatedAt: new Date().toISOString(),
    mandateTenureId,
  };
  store[adoptionKey(input.instrumentId, input.accountId)] = record;
  writeAdoptionStore(store);
  return record;
}

export function clearAdoption(instrumentId: string, accountId: string): void {
  applyMandateChange({
    instrumentId,
    accountId,
    open: null,
  });
  const store = readAdoptionStore();
  delete store[adoptionKey(instrumentId, accountId)];
  writeAdoptionStore(store);
}
