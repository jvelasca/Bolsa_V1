/**
 * Efectividad — skill vs luck + memoria + observed (RFC-008 D7).
 */

import type { EdgeBand } from './evidence-engine.js';
import type { ObservedInvestorProfile } from './investor-profile.js';

export type EffectivenessStatus = 'ready' | 'insufficient_data' | 'demo';

export interface EffectivenessMemoryCounts {
  accepted: number;
  rejected: number;
  deferred: number;
  reevaluatePending: number;
}

export interface EffectivenessPersistenceStats {
  decisionMemoryCount: number;
  trialCount: number;
  edgeReportCount: number;
  openConfidenceStates: number;
}

export interface EffectivenessSummaryV1 {
  status: EffectivenessStatus;
  asOf: string;
  trialsN: number;
  credibility: number | null;
  edgeScore: number | null;
  band: EdgeBand | null;
  memory: EffectivenessMemoryCounts;
  observed: ObservedInvestorProfile | null;
  headline: string;
  notes: string[];
  /** postgres | demo | postgres_unavailable */
  source?: string;
  persistence?: EffectivenessPersistenceStats;
}

export const BAND_LABEL: Record<EdgeBand, string> = {
  skill: 'Skill',
  uncertain: 'Incierta',
  luck: 'Luck / insuficiente',
};

export function effectivenessHeadline(band: EdgeBand | null, trialsN: number): string {
  if (trialsN < 1) return 'Sin TrialsLog — DSR/Credibility no son concluyentes';
  if (band === 'skill') return 'Señal compatible con skill (no garantía de PnL)';
  if (band === 'luck') return 'Evidencia insuficiente / posible luck — bloquear auto-live';
  if (band === 'uncertain') return 'Zona gris — paper/shadow antes de auto';
  return 'Sin EdgeReport';
}
