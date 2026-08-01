/**
 * ART-FACT-SET — Market Knowledge Layer (RFC-008 D2).
 * Indicadores → hechos interpretables (no son la decisión).
 */

export type FactKey =
  | 'trend.primary'
  | 'momentum'
  | 'exhaustion'
  | 'participation'
  | 'volatility'
  | 'structure.sma'
  | 'fund.valuation'
  | 'fund.quality'
  | 'fund.growth'
  | 'fund.solvency'
  | 'fund.size'
  | 'macro.volatility_regime'
  | 'macro.yield_curve'
  | 'macro.credit'
  | 'macro.breadth'
  | 'macro.risk_appetite';

export type TrendPrimaryValue =
  | 'strong_bullish'
  | 'bullish'
  | 'weak'
  | 'bearish'
  | 'strong_bearish'
  | 'unknown';

export type MomentumValue = 'strong' | 'neutral' | 'weak' | 'unknown';
export type ExhaustionValue = 'true' | 'false' | 'unknown';
export type ParticipationValue =
  | 'institutional_bias'
  | 'aligned'
  | 'diverging'
  | 'unknown';
export type VolatilityValue = 'high' | 'normal' | 'low' | 'unknown';
export type StructureSmaValue =
  | 'bullish_stack'
  | 'bearish_stack'
  | 'mixed'
  | 'unknown';

export interface MarketFactV1 {
  factId: string;
  key: FactKey;
  value: string;
  /** 0–1 credibilidad del hecho (cobertura de datos / umbral) */
  confidence: number;
  claim: string;
  refs?: Record<string, string>;
}

export interface FactSetV1 {
  artifactType: 'ART-FACT-SET';
  schemaVersion: '1.0.0';
  factSetId: string;
  instrumentId: string;
  timestamp: string;
  source: 'technical_v1';
  facts: MarketFactV1[];
}
