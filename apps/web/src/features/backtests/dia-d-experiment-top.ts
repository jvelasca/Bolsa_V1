/**
 * TOP experimento DÍA D (F-D) — ADR-021.
 * No pisa Finalistas operativos (F-hoy) en BD.
 */

import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";

export const DIA_D_EXPERIMENT_TOP_KEY = "bolsa-dia-d-experiment-top-v1";
export const DIA_D_EXPERIMENT_TOP_ENGINE = "dia-d-experiment-top-v1" as const;

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
  /**
   * R6 — id de la fila de Evidence en servidor (`source=dia_d_experiment_top`).
   * Sirve de traza auditable; `null` si el experimento solo vive en la caché.
   */
  evidenceId?: string | null;
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
  if (typeof localStorage === "undefined") return emptyStore();
  try {
    const raw = localStorage.getItem(DIA_D_EXPERIMENT_TOP_KEY);
    if (!raw) return emptyStore();
    const parsed = JSON.parse(raw) as DiaDExperimentTopStore;
    if (!parsed?.byKey || typeof parsed.byKey !== "object") return emptyStore();
    return { engine: DIA_D_EXPERIMENT_TOP_ENGINE, byKey: parsed.byKey };
  } catch {
    return emptyStore();
  }
}

export function writeDiaDExperimentTopStore(
  store: DiaDExperimentTopStore,
): void {
  if (typeof localStorage === "undefined") return;
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
  /**
   * Sello del servidor. Cuando el experimento ya se guardó en servidor, la caché
   * local refleja **su** `savedAt`; el cliente no inventa otro.
   */
  savedAt?: string;
  /** Id de la evidencia en servidor (traza auditable). */
  evidenceId?: string | null;
}): DiaDExperimentTop {
  const record: DiaDExperimentTop = {
    engine: DIA_D_EXPERIMENT_TOP_ENGINE,
    instrumentId: input.instrumentId,
    timeframe: input.timeframe,
    asOfDiaD: input.asOfDiaD,
    savedAt: input.savedAt ?? new Date().toISOString(),
    slots: input.slots,
    coachHeadline: input.coachHeadline ?? null,
    productionTop1AtSave: input.productionTop1AtSave ?? null,
    evidenceId: input.evidenceId ?? null,
  };
  const store = readDiaDExperimentTopStore();
  store.byKey[
    diaDExperimentKey(input.instrumentId, input.timeframe, input.asOfDiaD)
  ] = record;
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

/**
 * R6 — hidrata la caché local con el experimento **durable** del servidor.
 *
 * La lectura de los paneles es síncrona (en render), así que el servidor no
 * puede ser el único camino de lectura en caliente: se guarda una copia local y
 * se descarta la que sea más vieja que la del servidor. Nunca "pisa" un registro
 * más reciente con uno anterior.
 */
export function hydrateDiaDExperimentTop(
  row: import("@bolsa/shared").DiaDExperimentTopV1,
): DiaDExperimentTop {
  const production = row.productionTop1AtSave
    ? {
        strategyDefinitionId:
          row.productionTop1AtSave.strategyDefinitionId ?? null,
        label: row.productionTop1AtSave.label ?? null,
        strategyType: row.productionTop1AtSave.strategyType ?? null,
      }
    : null;
  const record: DiaDExperimentTop = {
    engine: DIA_D_EXPERIMENT_TOP_ENGINE,
    instrumentId: row.instrumentId,
    timeframe: row.timeframe,
    asOfDiaD: row.asOfDiaD,
    savedAt: row.savedAt,
    slots: row.slots,
    coachHeadline: row.coachHeadline ?? null,
    productionTop1AtSave: production,
    evidenceId: row.id,
  };
  const store = readDiaDExperimentTopStore();
  const key = diaDExperimentKey(row.instrumentId, row.timeframe, row.asOfDiaD);
  const existing = store.byKey[key];
  if (existing && existing.savedAt >= record.savedAt) return existing;
  store.byKey[key] = record;
  writeDiaDExperimentTopStore(store);
  return record;
}
