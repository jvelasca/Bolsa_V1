/**
 * Zona del tablero Lab TOP-3 (una candidata Coach → una columna editable).
 * Lab no escribe Finalistas: el siguiente paso es Reanalizar con Coach.
 */

import type { OptimizeSeed } from '@/features/backtests/backtest-optimize-seed';
import type { LabHandoffSaveResult } from '@/features/backtests/lab-coach-handoff';
import type { BacktestStrategyType, StrategyDefinitionV1 } from '@bolsa/shared';

export type LabBoardZone = {
  id: string;
  rank: 1 | 2 | 3;
  /** null = zona vacía (TOP con &lt;3 candidatas optimizables). */
  seed: OptimizeSeed | null;
  /** Job ya encolado desde Coach («Pasar al Lab»). */
  jobId?: string | null;
  /** Varios jobs (p. ej. H0+Optuna) → el panel une resultados. */
  jobIds?: string[] | null;
  stars?: number;
  starsCapped?: boolean;
  coachLabel?: string;
};

/** Snapshot del Mejor (o ancla) para el puente Lab → Coach. */
export type LabCoachHandoffCandidate = {
  zoneId: string;
  rank: 1 | 2 | 3;
  /** true si Mejor &gt; ancla (OOS/IS según ranking). */
  improved: boolean;
  hasResult: boolean;
  label: string;
  score: number;
  strategyType: BacktestStrategyType | string | null;
  seedLabel?: string;
  /**
   * Persiste el Mejor. `ok:false` = fallo de API (bloquea handoff).
   * `null` = no aplica (sin mejora).
   */
  ensureBestStrategy: () => Promise<
    | (LabHandoffSaveResult & {
        definition?: StrategyDefinitionV1;
      })
    | null
  >;
};

export type LabZoneHandle = {
  getHandoff: () => LabCoachHandoffCandidate | null;
};

/** Payload del CTA «Reanalizar con Coach». */
export type LabReanalyzeRequest = {
  /** Zonas que mejoraron → se re-simulan y entran al ranking Coach. */
  improved: Array<{
    zoneId: string;
    rank: 1 | 2 | 3;
    strategyId: string;
    label: string;
    presetKey?: string | null;
    strategyType?: string | null;
  }>;
  /**
   * Zonas sin mejora que el usuario marca «llevar».
   * No se reanalizan; el Coach las muestra con badge.
   */
  carried: Array<{
    zoneId: string;
    rank: 1 | 2 | 3;
    label: string;
    strategyType?: string | null;
    seedLabel?: string;
  }>;
};

/** Rellena siempre 3 zonas (vacías al final). */
export function padLabZones(zones: LabBoardZone[]): LabBoardZone[] {
  const out = zones.slice(0, 3).map((z, i) => ({
    ...z,
    rank: ((i + 1) as 1 | 2 | 3),
  }));
  while (out.length < 3) {
    const rank = (out.length + 1) as 1 | 2 | 3;
    out.push({
      id: `empty-${rank}`,
      rank,
      seed: null,
    });
  }
  return out;
}
