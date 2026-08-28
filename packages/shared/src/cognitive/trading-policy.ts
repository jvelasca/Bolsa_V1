/**
 * ART-TRADING-POLICY — manual operativo hard (RFC-008 D1).
 * Policy Gate es el único permiso de apertura automática.
 */

import type { ExitPolicyV1 } from "./exit-policy.js";

export type AssetClass =
  | "equities"
  | "fx"
  | "crypto"
  | "commodities"
  | "rates"
  | "options";

export type PolicyTemplateId =
  | "conservative"
  | "moderate"
  | "aggressive_swing"
  | "custom";

export type PrimaryTimeframe = "M5" | "M15" | "H1" | "H4" | "D1" | "W1";

export type AllowedOrderType =
  | "market"
  | "limit"
  | "stop"
  | "stop_limit"
  | "twap"
  | "vwap"
  | "iceberg";

export interface UniverseConstraints {
  allowedAssetClasses: AssetClass[];
  /** p.ej. nasdaq100, sp500, europe_large */
  allowedUniverses?: string[];
  minMarketCapUSD?: number;
  minAverageDailyVolumeUSD: number;
  maxSpreadBps?: number;
  minAtrPct?: number;
  maxAtrPct?: number;
  excludedSectors: string[];
  excludedTickers: string[];
  allowShorting: boolean;
  allowOtc: boolean;
  allowCrypto: boolean;
  allowCfds: boolean;
}

export interface ExposureConstraints {
  maxLeverage: number;
  maxOpenPositions: number;
  maxPortfolioConcentrationPct: number;
  maxSectorExposurePct: number;
  maxCorrelationWithOpenPositions?: number;
}

export interface RiskConstraints {
  maxRiskPerTradePct: number;
  hardDailyDrawdownLimitPct: number;
  hardWeeklyDrawdownLimitPct?: number;
  hardMaxDrawdownLimitPct: number;
  minRewardToRiskRatio: number;
  stopLossRequired: boolean;
  minTakeProfitRMultiple?: number;
}

export interface BlackoutConstraints {
  blockPreEarningsHours: number;
  blockPostEarningsHours: number;
  blockFedFomc: boolean;
  blockEcb: boolean;
  blockHighImpactMacro: boolean;
  /** CPI, PMI, NFP, etc. */
  blockedMacroEventTypes: string[];
  blockMnaRumors: boolean;
  blockDividendsHours?: number;
  blockSplitsHours?: number;
  allowedTradingHoursUTC?: { start: string; end: string };
}

export interface HorizonConstraints {
  primaryTimeframe: PrimaryTimeframe;
  minHoldingPeriodMinutes: number;
  maxHoldingPeriodDays: number;
}

export interface ExecutionConstraints {
  allowedOrderTypes: AllowedOrderType[];
  defaultOrderType: AllowedOrderType;
}

export interface EvidenceThresholds {
  /** Credibility / EdgeScore 0–100 */
  minimumRequiredCredibility: number;
  minimumWalkForwardEfficiency: number;
  maxMonteCarloPValue: number;
  minimumDsr?: number;
  requireEdgeReportForAutoLive: boolean;
}

export interface TradingPolicyV1 {
  artifactType: "ART-TRADING-POLICY";
  schemaVersion: "1.0.0";
  policyId: string;
  version: string;
  templateId: PolicyTemplateId;
  name: string;
  description?: string;
  universe: UniverseConstraints;
  exposure: ExposureConstraints;
  risk: RiskConstraints;
  blackouts: BlackoutConstraints;
  horizon: HorizonConstraints;
  execution: ExecutionConstraints;
  evidence: EvidenceThresholds;
  /** V1.27 — gestión T1/T2; opcional en policies custom/legacy. */
  exit?: ExitPolicyV1;
  /** refs a WeightRules versionadas (D6); vacío en D1 */
  weightRuleSetId?: string | null;
  updatedAt: string;
  createdAt: string;
}

export type PolicyRuleStatus = "PASSED" | "FAILED" | "SKIPPED";

export interface PolicyRuleResult {
  rule: string;
  limit: string;
  actual: string;
  status: PolicyRuleStatus;
  message?: string;
}

export interface PolicyGateInput {
  policy: TradingPolicyV1;
  instrument: {
    symbol: string;
    assetClass: AssetClass;
    marketCapUSD?: number;
    averageDailyVolumeUSD?: number;
    sector?: string;
    spreadBps?: number;
    atrPct?: number;
  };
  proposed: {
    riskPctOfAccount: number;
    rewardToRiskRatio: number;
    leverage: number;
    hasStopLoss: boolean;
    openPositionsCount: number;
    portfolioConcentrationPct: number;
    sectorExposurePct?: number;
  };
  context?: {
    hoursToEarnings?: number | null;
    hoursSinceEarnings?: number | null;
    highImpactMacroActive?: boolean;
    fedFomcActive?: boolean;
    ecbActive?: boolean;
  };
  evidence?: {
    credibility?: number | null;
    walkForwardEfficiency?: number | null;
    monteCarloPValue?: number | null;
    edgeReportPresent?: boolean;
    autoLive?: boolean;
  };
  /** Circuit breaker F4 — % drawdown (omitido = SKIPPED). */
  accountDrawdown?: {
    dailyPct?: number | null;
    weeklyPct?: number | null;
    maxPct?: number | null;
  };
}

export interface PolicyGateResult {
  passed: boolean;
  policyId: string;
  policyVersion: string;
  evaluatedRules: PolicyRuleResult[];
  vetoReasons: string[];
}
