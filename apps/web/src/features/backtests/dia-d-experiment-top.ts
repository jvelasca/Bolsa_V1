/**
 * TOP experimento DÍA D (F-D) — ADR-021.
 * No pisa Finalistas operativos (F-hoy) en BD.
 */

import type { InstrumentStrategyTopSlotV1 } from '@bolsa/shared';

export const DIA_D_EXPERIMENT_TOP_KEY = 'bolsa-dia-d-experiment-top-v1';
export const DIA_D_EXPERIMENT_TOP_ENGINE = 'dia-d-experiment-top-v1' as const;

export type DiaDExperimentTop1Ref = {
  strategyDefinitionId: string | null;
  label: string | null;
  strategyType?: string | null;
};

export type DiaDExperimentTop = {
  engine: typeof DIA_D_EXPERIMENT_TOP_ENGINE;
  instrumentId: string;
  timeframe: string;
  asOfDiaD: string;
  savedAt: string;
  slots: InstrumentStrategyTopSlotV1[];
  coachHeadline?: string | null;
  /** F-hoy #1 al guardar el experimento (referencia). */
  productionTop1AtSave?: DiaDExperimentTop1Ref | null;
};

export type DiaDExperimentTopStore = {
  engine: typeof DIA_D_EXPERIMENT_TOP_ENGINE;
  /** Clave `instrumentId::timeframe::asOfDiaD` */
  byKey: Record<string, DiaDExperimentTop>;
};

let revision = 0;
const listeners = new Set<() => void>();

function bump(): void {
  revision += 1;
  for (const l of listeners) l();
}

export function subscribeDiaDExperimentTop(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

export function getDiaDExperimentTopSnapshot(): number {
  return revision;
}

export function diaDExperimentKey(
  instrumentId: string,
  timeframe: string,
  asOfDiaD: string,
): string {
  return `${instrumentId}::${timeframe}::${asOfDiaD}`;
}

function emptyStore(): DiaDExperimentTopStore {
  return { engine: DIA_D_EXPERIMENT_TOP_ENGINE, byKey: {} };
}

export function readDiaDExperimentTopStore(): DiaDExperimentTopStore {
  if (typeof localStorage === 'undefined') return emptyStore();
  try {
    const raw = localStorage.getItem(DIA_D_EXPERIMENT_TOP_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as DiaDExperimentTopStore;
    if (!parsed?.byKey || typeof parsed.byKey !== 'object') return emptyStore();
    return { engine: DIA_D_EXPERIMENT_TOP_ENGINE, byKey: parsed.byKey };
  } catch {
    return emptyStore();
  }
}

export function writeDiaDExperimentTopStore(store: DiaDExperimentTopStore): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(
    DIA_D_EXPERIMENT_TOP_KEY,
    JSON.stringify({ engine: DIA_D_EXPERIMENT_TOP_ENGINE, byKey: store.byKey }),
  );
  bump();
}

export function saveDiaDExperimentTop(input: {
  instrumentId: string;
  timeframe: string;
  asOfDiaD: string;
  slots: InstrumentStrategyTopSlotV1[];
  coachHeadline?: string | null;
  productionTop1AtSave?: DiaDExperimentTop1Ref | null;
}): DiaDExperimentTop {
  const record: DiaDExperimentTop = {
    engine: DIA_D_EXPERIMENT_TOP_ENGINE,
    instrumentId: input.instrumentId,
    timeframe: input.timeframe,
    asOfDiaD: input.asOfDiaD,
    savedAt: new Date().toISOString(),
    slots: input.slots,
    coachHeadline: input.coachHeadline ?? null,
    productionTop1AtSave: input.productionTop1AtSave ?? null,
  };
  const store = readDiaDExperimentTopStore();
  store.byKey[diaDExperimentKey(input.instrumentId, input.timeframe, input.asOfDiaD)] =
    record;
  // Cap: últimos 40 experimentos
  const keys = Object.keys(store.byKey);
  if (keys.length > 40) {
    const sorted = keys
      .map((k) => ({ k, at: store.byKey[k]!.savedAt }))
      .sort((a, b) => a.at.localeCompare(b.at));
    for (const row of sorted.slice(0, keys.length - 40)) {
      delete store.byKey[row.k];
    }
  }
  writeDiaDExperimentTopStore(store);
  return record;
}

export function getDiaDExperimentTop(
  instrumentId: string,
  timeframe: string,
  asOfDiaD: string,
): DiaDExperimentTop | null {
  return (
    readDiaDExperimentTopStore().byKey[
      diaDExperimentKey(instrumentId, timeframe, asOfDiaD)
    ] ?? null
  );
}

export function getDiaDExperimentTop1(
  instrumentId: string,
  timeframe: string,
  asOfDiaD: string,
): InstrumentStrategyTopSlotV1 | null {
  const exp = getDiaDExperimentTop(instrumentId, timeframe, asOfDiaD);
  if (!exp?.slots?.length) return null;
  return [...exp.slots].sort((a, b) => a.rank - b.rank)[0] ?? null;
}

export function clearDiaDExperimentTop(
  instrumentId: string,
  timeframe: string,
  asOfDiaD: string,
): void {
  const store = readDiaDExperimentTopStore();
  delete store.byKey[diaDExperimentKey(instrumentId, timeframe, asOfDiaD)];
  writeDiaDExperimentTopStore(store);
}
