/**
 * Fundamental Card DTO — contrato base F1 (FIE §12) + derived F2.x–F2.8.
 * Solo lectura; UI no recalcula Score_FUND.
 *
 * Pilares = components Score_FUND: value | quality | growth | risk
 * Derived incluye: Altman, Piotroski, Graham, DCF/escenarios, CAPM/WACC,
 * ROIC, Beneish, beta, ADV.
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 * @see docs/engineering/fa-status-and-test-plan-2026-07-31.md
 */

import type { DcfScenariosV1, InstrumentFundamentalsV1 } from './fundamentals-gate.js';

export const FUND_CARD_SCHEMA_VERSION = 'fund_card_v1' as const;
export const SCORE_FUND_VERSION = 'fund_score_v1' as const;

export type FundamentalDataConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

/** Pilares F1 = mismos keys que ScoreFundResult.components. */
export interface FundamentalPillarsV1 {
  value: number;
  quality: number;
  growth: number;
  risk: number;
}

export interface FundamentalCardDerivedV1 {
  fcfYield: number | null;
  altmanZ: number | null;
  altmanMethod: string | null;
  altmanEbitSource: string | null;
  piotroski: number | null;
  piotroskiMethod: string | null;
  roic: number | null;
  roicMethod: string | null;
  beneishM: number | null;
  beneishMethod: string | null;
  grahamNumber: number | null;
  grahamMethod: string | null;
  grahamUpside: number | null;
  /** F2.6 — beta Yahoo (input CAPM). */
  beta: number | null;
  /** F2.6 — ADV notional USD/día. */
  advUsd: number | null;
  averageVolume: number | null;
  /** Tasa descuento DCF (CAPM o WACC sector). */
  wacc: number | null;
  waccMethod: string | null;
  /** r_f / ERP versionados cuando ke viene de CAPM; null si WACC sector. */
  capmRf: number | null;
  capmErp: number | null;
  dcfEquityValue: number | null;
  dcfUpside: number | null;
  dcfMethod: string | null;
  /** F2.5 — bear/base/bull; null si DCF no computable. */
  dcfScenarios: DcfScenariosV1 | null;
  totalAssets: number | null;
  retainedEarnings: number | null;
  totalLiabilities: number | null;
}

export interface FundamentalCardMetadataV1 {
  provider: string;
  sourceVersion: string | null;
  scoreVersion: string;
  fetchedAt: string | null;
  staleDays: number | null;
  isStale: boolean;
  /** Confianza de datos (Python); UI solo pinta. */
  confidence: FundamentalDataConfidence;
  /** Cobertura de pesos de pilares Score_FUND [0..1]. */
  coverage: number | null;
  /** Corte DÍA D (YYYY-MM-DD) si se pidió asOf. */
  asOfDate?: string | null;
  /**
   * live = sin corte · snapshot = pack ≤ D · blocked = pack posterior a D
   * (scores/ratios nulled; sin look-ahead).
   */
  pointInTime?: 'live' | 'snapshot' | 'blocked' | 'reconstructed' | null;
}

/** Keys siempre presentes; ausentes → null (no omitir en JSON). */
export type FundamentalCardFactsV1 = {
  [K in keyof Pick<
    InstrumentFundamentalsV1,
    | 'marketCap'
    | 'trailingPe'
    | 'forwardPe'
    | 'sector'
    | 'roe'
    | 'roa'
    | 'operatingMargin'
    | 'profitMargin'
    | 'revenueGrowth'
    | 'earningsGrowth'
    | 'debtToEquity'
    | 'currentRatio'
    | 'quickRatio'
    | 'totalCash'
    | 'totalDebt'
    | 'ebitda'
    | 'freeCashflow'
    | 'priceToBook'
  >]: InstrumentFundamentalsV1[K] | null | undefined;
};

export interface FundamentalCardDto {
  schemaVersion: typeof FUND_CARD_SCHEMA_VERSION | string;
  instrumentId: string;
  ticker: string;
  scoreFund: number | null;
  /** Escala inequívoca 0–100 (neutro 50). */
  scoreDisplay100: number | null;
  distress: boolean;
  pillars: FundamentalPillarsV1 | null;
  facts: FundamentalCardFactsV1;
  derived: FundamentalCardDerivedV1;
  metadata: FundamentalCardMetadataV1;
  assessmentId?: string | null;
  /** Evidencias = claims del Score_FUND. */
  narrativeFacts: string[];
  warnings: string[];
}

export interface FundamentalCardResponseDto {
  data: FundamentalCardDto;
}

/** PR3 — chip compacto en filas de lista (subset del card; sin recalc). */
export interface FundamentalChipDto {
  instrumentId: string;
  ticker: string;
  scoreDisplay100: number | null;
  confidence: FundamentalDataConfidence;
  isStale: boolean;
  distress: boolean;
  /** Atajos visuales opcionales. */
  roe?: number | null;
  debtToEquity?: number | null;
  altmanZ?: number | null;
}

export interface FundamentalChipQueryRequestV1 {
  instrumentIds: string[];
}

export interface FundamentalChipQueryResponseV1 {
  data: FundamentalChipDto[];
}

/** Proyecta card → chip (UI / tests). */
export function fundamentalCardToChip(card: FundamentalCardDto): FundamentalChipDto {
  return {
    instrumentId: card.instrumentId,
    ticker: card.ticker,
    scoreDisplay100: card.scoreDisplay100,
    confidence: card.metadata.confidence,
    isStale: card.metadata.isStale,
    distress: card.distress,
    roe: card.facts.roe ?? null,
    debtToEquity: card.facts.debtToEquity ?? null,
    altmanZ: card.derived.altmanZ ?? null,
  };
}

/** F1b — respuesta copiloto (Ollama o heurística). */
export interface FundamentalCopilotPayloadV1 {
  paragraphs: string[];
  disclaimer: string;
}

export interface FundamentalExplainResponseV1 {
  engine: string;
  payload: FundamentalCopilotPayloadV1 | null;
  provider: string | null;
  model: string | null;
  card?: FundamentalCardDto;
}
