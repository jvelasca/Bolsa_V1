/**
 * ART: InstrumentStrategyTop — 3 estrategias AT candidatas por instrumento.
 * Semifinal del embudo coach → optimizar → TOP persistido.
 */

export type InstrumentStrategyTopStatus = 'draft' | 'semifinal' | 'active';

export type InstrumentStrategyTopSlotV1 = {
  rank: 1 | 2 | 3;
  label: string;
  /** Preset genérico si aplica. */
  strategyType?: string | null;
  strategyDefinitionId?: string | null;
  stars: number;
  score: number;
  starsCapped?: boolean;
  runId?: string | null;
  source: 'coach' | 'user' | 'optimized';
  totalReturnPct?: number | null;
  excessReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  lateReturnPct?: number | null;
};

export type InstrumentStrategyTopV1 = {
  artifactType?: 'ART-INSTRUMENT-TOP';
  schemaVersion?: '1.0.0';
  id: string;
  instrumentId: string;
  symbol?: string | null;
  timeframe: string;
  periodLabel?: string | null;
  status: InstrumentStrategyTopStatus;
  version: number;
  evidenceLevel: 'in_sample_only' | 'lab_validated';
  slots: InstrumentStrategyTopSlotV1[];
  coachHeadline?: string | null;
  coachFacts?: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
};

export type UpsertInstrumentStrategyTopRequestV1 = {
  instrumentId: string;
  symbol?: string | null;
  timeframe: string;
  periodLabel?: string | null;
  status?: InstrumentStrategyTopStatus;
  evidenceLevel?: 'in_sample_only' | 'lab_validated';
  slots: InstrumentStrategyTopSlotV1[];
  coachHeadline?: string | null;
  coachFacts?: Record<string, unknown> | null;
};
