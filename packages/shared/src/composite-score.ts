/**
 * FIE F3 — Composite Investment Score (`composite_score_v1_1` / `composite_card_v1`).
 *
 * Piernas: Technical · Fundamental (Score_FUND) · Risk Profile · Liquidity ·
 * Market Regime · Portfolio Constraints (stub).
 * Python calcula; UI/LLM solo leen. Desbloquea diseño de Paper D (auto-paper).
 * v1.1: buckets ADV/mcap calibrados (US mega ≠ IBEX large).
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

export const COMPOSITE_SCHEMA_VERSION = 'composite_card_v1' as const;
export const COMPOSITE_SCORE_VERSION = 'composite_score_v1_1' as const;

export type CompositeDataConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

export type CompositeLegStatusV1 = 'ok' | 'missing' | 'stub' | 'not_evaluated';

export interface CompositeLegV1 {
  key:
    | 'technical'
    | 'fundamental'
    | 'riskProfile'
    | 'liquidity'
    | 'marketRegime'
    | 'portfolioConstraints';
  label: string;
  score: number | null;
  weight: number;
  status: CompositeLegStatusV1;
  method?: string | null;
  note?: string | null;
}

export interface CompositeWeightsV1 {
  ta: number;
  fund: number;
  macro: number;
  news: number;
  liquidity: number;
  riskProfile: number;
  horizon: string;
  regime: string;
  rationale: string;
  sizeHint: number;
  vetoNewLong: boolean;
  weightRulesVersion: string;
}

export interface CompositeCardMetadataV1 {
  scoreVersion: typeof COMPOSITE_SCORE_VERSION | string;
  schemaVersion: typeof COMPOSITE_SCHEMA_VERSION | string;
  confidence: CompositeDataConfidence;
  coverage: number | null;
  horizon: string;
  regime: string;
  fundSourceVersion?: string | null;
  technicalMethod?: string | null;
  paperDUnlocked: boolean;
  /** Corte DÍA D si se pidió asOf. */
  asOfDate?: string | null;
  pointInTime?: 'live' | 'snapshot' | 'blocked' | 'reconstructed' | null;
  fundPointInTime?: 'live' | 'snapshot' | 'blocked' | 'reconstructed' | null;
  /** true si la pierna TA usó OHLCV dateTo ≤ asOf. */
  taCutToAsOf?: boolean;
}

export interface CompositeCardDto {
  schemaVersion: typeof COMPOSITE_SCHEMA_VERSION | string;
  instrumentId: string;
  ticker: string;
  /** Combined ∈ [-1, +1]. */
  combinedScore: number | null;
  scoreDisplay100: number | null;
  legs: CompositeLegV1[];
  weights: CompositeWeightsV1;
  metadata: CompositeCardMetadataV1;
  warnings: string[];
  narrativeFacts: string[];
}

export interface CompositeCardResponseDto {
  data: CompositeCardDto;
}

export interface CompositeChipDto {
  instrumentId: string;
  ticker: string;
  /** Combined 0–100 (neutral 50). */
  scoreDisplay100: number | null;
  confidence: CompositeDataConfidence;
  combinedScore: number | null;
  regime: string;
  paperDUnlocked: boolean;
  /** Pierna técnica 0–100 (hub Instrumentos I2). */
  technicalDisplay100?: number | null;
}

export interface CompositeChipQueryRequestV1 {
  instrumentIds: string[];
  horizon?: string;
  regime?: string;
}

export interface CompositeChipQueryResponseV1 {
  data: CompositeChipDto[];
}
