/**
 * Plantillas base ART-TRADING-POLICY (RFC-008 D1).
 */

import type { TradingPolicyV1 } from './trading-policy.js';

const now = '2026-07-22T00:00:00.000Z';

function baseMeta(
  templateId: TradingPolicyV1['templateId'],
  name: string,
  description: string,
): Pick<
  TradingPolicyV1,
  | 'artifactType'
  | 'schemaVersion'
  | 'policyId'
  | 'version'
  | 'templateId'
  | 'name'
  | 'description'
  | 'updatedAt'
  | 'createdAt'
  | 'weightRuleSetId'
> {
  return {
    artifactType: 'ART-TRADING-POLICY',
    schemaVersion: '1.0.0',
    policyId: `POL-${templateId.toUpperCase()}-V1`,
    version: '1.0.0',
    templateId,
    name,
    description,
    weightRuleSetId: null,
    updatedAt: now,
    createdAt: now,
  };
}

export const CONSERVATIVE_TRADING_POLICY: TradingPolicyV1 = {
  ...baseMeta(
    'conservative',
    'Conservador',
    'Preservación de capital: large-cap líquidas, sin apalancamiento, blackouts estrictos.',
  ),
  universe: {
    allowedAssetClasses: ['equities'],
    allowedUniverses: ['sp500', 'nasdaq100'],
    minMarketCapUSD: 10_000_000_000,
    minAverageDailyVolumeUSD: 20_000_000,
    maxSpreadBps: 15,
    minAtrPct: 0.3,
    maxAtrPct: 4,
    excludedSectors: ['biotech'],
    excludedTickers: [],
    allowShorting: false,
    allowOtc: false,
    allowCrypto: false,
    allowCfds: false,
  },
  exposure: {
    maxLeverage: 1,
    maxOpenPositions: 8,
    maxPortfolioConcentrationPct: 8,
    maxSectorExposurePct: 20,
    maxCorrelationWithOpenPositions: 0.65,
  },
  risk: {
    maxRiskPerTradePct: 0.5,
    hardDailyDrawdownLimitPct: 1.5,
    hardWeeklyDrawdownLimitPct: 3,
    hardMaxDrawdownLimitPct: 8,
    minRewardToRiskRatio: 2.5,
    stopLossRequired: true,
    minTakeProfitRMultiple: 2,
  },
  blackouts: {
    blockPreEarningsHours: 48,
    blockPostEarningsHours: 24,
    blockFedFomc: true,
    blockEcb: true,
    blockHighImpactMacro: true,
    blockedMacroEventTypes: ['CPI', 'PCE', 'NFP', 'PMI', 'FOMC', 'ECB'],
    blockMnaRumors: true,
    blockDividendsHours: 24,
    blockSplitsHours: 48,
    allowedTradingHoursUTC: { start: '13:30', end: '20:00' },
  },
  horizon: {
    primaryTimeframe: 'D1',
    minHoldingPeriodMinutes: 60 * 24,
    maxHoldingPeriodDays: 90,
  },
  execution: {
    allowedOrderTypes: ['limit', 'stop', 'stop_limit'],
    defaultOrderType: 'limit',
  },
  evidence: {
    minimumRequiredCredibility: 80,
    minimumWalkForwardEfficiency: 0.7,
    maxMonteCarloPValue: 0.05,
    minimumDsr: 0.7,
    requireEdgeReportForAutoLive: true,
  },
};

export const MODERATE_TRADING_POLICY: TradingPolicyV1 = {
  ...baseMeta(
    'moderate',
    'Moderado',
    'Equilibrio crecimiento/riesgo: mid+large cap, R:R 2:1, blackouts estándar.',
  ),
  universe: {
    allowedAssetClasses: ['equities'],
    allowedUniverses: ['sp500', 'nasdaq100', 'russell1000'],
    minMarketCapUSD: 2_000_000_000,
    minAverageDailyVolumeUSD: 5_000_000,
    maxSpreadBps: 25,
    minAtrPct: 0.4,
    maxAtrPct: 6,
    excludedSectors: [],
    excludedTickers: [],
    allowShorting: false,
    allowOtc: false,
    allowCrypto: false,
    allowCfds: false,
  },
  exposure: {
    maxLeverage: 1,
    maxOpenPositions: 12,
    maxPortfolioConcentrationPct: 12,
    maxSectorExposurePct: 30,
    maxCorrelationWithOpenPositions: 0.75,
  },
  risk: {
    maxRiskPerTradePct: 1,
    hardDailyDrawdownLimitPct: 2,
    hardWeeklyDrawdownLimitPct: 5,
    hardMaxDrawdownLimitPct: 12,
    minRewardToRiskRatio: 2,
    stopLossRequired: true,
    minTakeProfitRMultiple: 2,
  },
  blackouts: {
    blockPreEarningsHours: 24,
    blockPostEarningsHours: 12,
    blockFedFomc: true,
    blockEcb: true,
    blockHighImpactMacro: true,
    blockedMacroEventTypes: ['CPI', 'NFP', 'FOMC'],
    blockMnaRumors: true,
    blockDividendsHours: 12,
    blockSplitsHours: 24,
  },
  horizon: {
    primaryTimeframe: 'D1',
    minHoldingPeriodMinutes: 60 * 4,
    maxHoldingPeriodDays: 45,
  },
  execution: {
    allowedOrderTypes: ['market', 'limit', 'stop', 'stop_limit'],
    defaultOrderType: 'limit',
  },
  evidence: {
    minimumRequiredCredibility: 70,
    minimumWalkForwardEfficiency: 0.6,
    maxMonteCarloPValue: 0.05,
    minimumDsr: 0.55,
    requireEdgeReportForAutoLive: true,
  },
};

export const AGGRESSIVE_SWING_TRADING_POLICY: TradingPolicyV1 = {
  ...baseMeta(
    'aggressive_swing',
    'Swing agresivo',
    'Mayor riesgo por trade y universo más amplio; sigue exigiendo stop y Edge para auto-live.',
  ),
  universe: {
    allowedAssetClasses: ['equities'],
    allowedUniverses: ['nasdaq100', 'russell2000', 'sp500'],
    minMarketCapUSD: 500_000_000,
    minAverageDailyVolumeUSD: 2_000_000,
    maxSpreadBps: 40,
    minAtrPct: 0.8,
    maxAtrPct: 10,
    excludedSectors: [],
    excludedTickers: [],
    allowShorting: true,
    allowOtc: false,
    allowCrypto: false,
    allowCfds: false,
  },
  exposure: {
    maxLeverage: 1.5,
    maxOpenPositions: 15,
    maxPortfolioConcentrationPct: 18,
    maxSectorExposurePct: 40,
    maxCorrelationWithOpenPositions: 0.85,
  },
  risk: {
    maxRiskPerTradePct: 1.5,
    hardDailyDrawdownLimitPct: 3,
    hardWeeklyDrawdownLimitPct: 7,
    hardMaxDrawdownLimitPct: 18,
    minRewardToRiskRatio: 1.8,
    stopLossRequired: true,
    minTakeProfitRMultiple: 1.8,
  },
  blackouts: {
    blockPreEarningsHours: 12,
    blockPostEarningsHours: 4,
    blockFedFomc: true,
    blockEcb: false,
    blockHighImpactMacro: true,
    blockedMacroEventTypes: ['CPI', 'FOMC', 'NFP'],
    blockMnaRumors: false,
    blockSplitsHours: 12,
  },
  horizon: {
    primaryTimeframe: 'H4',
    minHoldingPeriodMinutes: 60,
    maxHoldingPeriodDays: 21,
  },
  execution: {
    allowedOrderTypes: ['market', 'limit', 'stop', 'stop_limit', 'vwap'],
    defaultOrderType: 'market',
  },
  evidence: {
    minimumRequiredCredibility: 65,
    minimumWalkForwardEfficiency: 0.55,
    maxMonteCarloPValue: 0.08,
    minimumDsr: 0.45,
    requireEdgeReportForAutoLive: true,
  },
};

export const TRADING_POLICY_TEMPLATES: Record<
  'conservative' | 'moderate' | 'aggressive_swing',
  TradingPolicyV1
> = {
  conservative: CONSERVATIVE_TRADING_POLICY,
  moderate: MODERATE_TRADING_POLICY,
  aggressive_swing: AGGRESSIVE_SWING_TRADING_POLICY,
};

export function getTradingPolicyTemplate(
  id: 'conservative' | 'moderate' | 'aggressive_swing',
): TradingPolicyV1 {
  return structuredClone(TRADING_POLICY_TEMPLATES[id]);
}
