/**
 * CORE B v0–v0.1 — memoria de adopciones Lab (localStorage).
 *
 * Persiste el último Mejor adoptado/guardado por instrumento·TF para:
 * - espacio guiado en la siguiente pasada Lab
 * - hint UI (sin cambiar el ranking del Mejor)
 * - stamp opcional en coachFacts al guardar Finalistas
 *
 * v0.1: si el heatmap marca meseta, el espacio guiado se **ensancha**;
 * si el Mejor está localizado (pico), se **estrecha**. Sin meta → v0 (±fijo).
 *
 * v0.2: sin semilla Coach, la familia Lab por defecto usa adopción → horizonte
 * del perfil (`resolveDefaultLabFamily` en coach-profile-policy).
 *
 * No es Belief / Discovery. Lab sigue siendo determinista (grids OOS/WF).
 *
 * @see docs/engineering/assistant-play-funnel-design-2026-07-29.md §6
 */

import type { ChartTimeframe, OptimizeStrategyFamily } from '@bolsa/shared';
import {
  clampRange,
  defaultMacdSpace,
  type OptimizeSearchSpace,
  type RsiSearchSpace,
  type SmaSearchSpace,
} from '@/features/backtests/backtest-optimize-space';
import type { OosEvidenceKind } from '@/features/backtests/backtest-oos-evidence';

export const LAB_ADOPTION_MEMORY_KEY = 'bolsa-lab-adoption-memory-v1';
export const LAB_ADOPTION_ENGINE = 'lab-adoption-v1';

export type LabAdoptionParams = {
  fastPeriod?: number | null;
  slowPeriod?: number | null;
  signalPeriod?: number | null;
  period?: number | null;
  oversold?: number | null;
  overbought?: number | null;
};

/** Snapshot de meseta heatmap al adoptar (CORE-B v0.1). */
export type LabAdoptionPlateauMeta = {
  isPlateau: boolean;
  neighborCount: number;
  closeNeighborCount: number;
};

export type LabAdoptionRecord = {
  engine: typeof LAB_ADOPTION_ENGINE;
  instrumentId: string;
  timeframe: string;
  family: OptimizeStrategyFamily;
  params: LabAdoptionParams;
  paramsLabel: string;
  strategyId?: string | null;
  oosKind?: OosEvidenceKind | null;
  oosScore?: number | null;
  score?: number | null;
  maxDrawdownPct?: number | null;
  profileId?: string | null;
  plateau?: LabAdoptionPlateauMeta | null;
  adoptedAt: string;
};

type MemoryStore = Record<string, LabAdoptionRecord>;

/** Half-widths (param units) for guided SMA/RSI space. */
export type GuidedSpaceHalfWidths = {
  smaFast: number;
  smaSlow: number;
  rsiPeriod: number;
  rsiBand: number;
};

/** v0 defaults · meseta más ancha · pico más estrecho. */
export function guidedHalfWidthsForPlateau(
  plateau: LabAdoptionPlateauMeta | null | undefined,
): GuidedSpaceHalfWidths {
  if (plateau?.isPlateau === true) {
    return { smaFast: 10, smaSlow: 25, rsiPeriod: 7, rsiBand: 10 };
  }
  if (plateau?.isPlateau === false) {
    return { smaFast: 3, smaSlow: 8, rsiPeriod: 2, rsiBand: 3 };
  }
  return { smaFast: 5, smaSlow: 15, rsiPeriod: 4, rsiBand: 5 };
}

function memoryKey(instrumentId: string, timeframe: string): string {
  return `${instrumentId}|${String(timeframe)}`;
}

function readStore(): MemoryStore {
  try {
    const raw = localStorage.getItem(LAB_ADOPTION_MEMORY_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as MemoryStore;
  } catch {
    return {};
  }
}

function writeStore(store: MemoryStore): void {
  try {
    localStorage.setItem(LAB_ADOPTION_MEMORY_KEY, JSON.stringify(store));
  } catch {
    // quota
  }
}

export function labAdoptionMemoryKey(
  instrumentId: string,
  timeframe: ChartTimeframe | string,
): string {
  return memoryKey(instrumentId, String(timeframe));
}

export function readLabAdoption(
  instrumentId: string | null | undefined,
  timeframe: ChartTimeframe | string | null | undefined,
): LabAdoptionRecord | null {
  if (!instrumentId || !timeframe) return null;
  const rec = readStore()[memoryKey(instrumentId, String(timeframe))];
  if (!rec || rec.engine !== LAB_ADOPTION_ENGINE) return null;
  if (rec.instrumentId !== instrumentId) return null;
  return rec;
}

export function rememberLabAdoption(
  record: Omit<LabAdoptionRecord, 'engine' | 'adoptedAt'> & {
    adoptedAt?: string;
  },
): LabAdoptionRecord {
  const full: LabAdoptionRecord = {
    ...record,
    engine: LAB_ADOPTION_ENGINE,
    adoptedAt: record.adoptedAt ?? new Date().toISOString(),
  };
  const store = readStore();
  store[memoryKey(full.instrumentId, full.timeframe)] = full;
  writeStore(store);
  return full;
}

export function clearLabAdoption(
  instrumentId: string,
  timeframe: ChartTimeframe | string,
): void {
  const store = readStore();
  delete store[memoryKey(instrumentId, String(timeframe))];
  writeStore(store);
}

/** Hint compacto para banner Lab (solo lectura). */
export function formatLabAdoptionHint(rec: LabAdoptionRecord): string {
  const kind =
    rec.oosKind && rec.oosKind !== 'none' ? rec.oosKind : 'IS';
  const oos =
    rec.oosScore != null && Number.isFinite(rec.oosScore)
      ? ` · OOS ${rec.oosScore.toFixed(2)}`
      : '';
  const meseta =
    rec.plateau?.isPlateau === true
      ? ' · meseta'
      : rec.plateau?.isPlateau === false
        ? ' · pico'
        : '';
  return `Adopción previa · ${rec.paramsLabel} · ${kind}${oos}${meseta}`;
}

/** Stamp en coachFacts al guardar Finalistas post-Lab. */
export function buildLabAdoptionFacts(
  rec: LabAdoptionRecord | null,
): Record<string, unknown> | null {
  if (!rec) return null;
  return {
    labAdoption: {
      engine: rec.engine,
      family: rec.family,
      params: rec.params,
      paramsLabel: rec.paramsLabel,
      strategyId: rec.strategyId ?? null,
      oosKind: rec.oosKind ?? null,
      oosScore: rec.oosScore ?? null,
      score: rec.score ?? null,
      maxDrawdownPct: rec.maxDrawdownPct ?? null,
      profileId: rec.profileId ?? null,
      plateau: rec.plateau ?? null,
      adoptedAt: rec.adoptedAt,
    },
  };
}

/**
 * Espacio guiado alrededor del último Mejor.
 * Misma familia; no cambia el criterio de ranking del Mejor.
 * Anchura según meseta heatmap (v0.1).
 */
export function guidedSpaceFromAdoption(
  rec: LabAdoptionRecord,
): OptimizeSearchSpace | null {
  const hw = guidedHalfWidthsForPlateau(rec.plateau);

  if (rec.family === 'sma_crossover') {
    const f = rec.params.fastPeriod;
    const s = rec.params.slowPeriod;
    if (f == null || s == null || !Number.isFinite(f) || !Number.isFinite(s)) {
      return null;
    }
    const space: SmaSearchSpace = {
      family: 'sma_crossover',
      fast: clampRange({
        min: Math.max(2, f - hw.smaFast),
        max: f + hw.smaFast,
        step: 2,
      }),
      slow: clampRange({
        min: Math.max(f + 5, s - hw.smaSlow),
        max: s + hw.smaSlow,
        step: 5,
      }),
    };
    return space;
  }

  if (rec.family === 'rsi_mean_reversion') {
    const p = rec.params.period;
    const os = rec.params.oversold;
    const ob = rec.params.overbought;
    if (
      p == null ||
      os == null ||
      ob == null ||
      !Number.isFinite(p) ||
      !Number.isFinite(os) ||
      !Number.isFinite(ob)
    ) {
      return null;
    }
    const space: RsiSearchSpace = {
      family: 'rsi_mean_reversion',
      period: clampRange({
        min: Math.max(2, p - hw.rsiPeriod),
        max: p + hw.rsiPeriod,
        step: 2,
      }),
      oversold: clampRange(
        { min: Math.max(5, os - hw.rsiBand), max: os + hw.rsiBand, step: 5 },
        5,
      ),
      overbought: clampRange(
        {
          min: Math.max(50, ob - hw.rsiBand),
          max: Math.min(95, ob + hw.rsiBand),
          step: 5,
        },
        50,
      ),
    };
    return space;
  }

  if (rec.family === 'macd_signal_cross') {
    return defaultMacdSpace();
  }

  return null;
}

/** ¿Debemos aplicar espacio guiado a esta familia de semilla? */
export function shouldApplyGuidedSpace(
  rec: LabAdoptionRecord | null,
  family: OptimizeStrategyFamily,
): boolean {
  return Boolean(rec && rec.family === family);
}
