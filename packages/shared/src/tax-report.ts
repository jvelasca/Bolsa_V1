import type { CostBasisMethod, TaxJurisdiction } from "./account-settings.js";

export interface RealizedGainLineDto {
  id: string;
  instrumentId: string;
  symbol: string;
  sellTransactionId: string;
  executedAt: string;
  quantity: number;
  sellPrice: number;
  proceeds: number;
  costBasis: number;
  realizedGain: number;
  method: CostBasisMethod;
  /** Fechas de adquisición de los lotes consumidos (FIFO). */
  acquisitionDates: string[];
}

export interface UnrealizedGainLineDto {
  instrumentId: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  marketPrice: number | null;
  costBasis: number;
  marketValue: number | null;
  unrealizedGain: number | null;
}

export interface TaxReportSummaryDto {
  accountId: string;
  currency: string;
  method: CostBasisMethod;
  jurisdiction: TaxJurisdiction;
  year: number;
  periodLabel: string;
  realizedLines: RealizedGainLineDto[];
  totalGains: number;
  totalLosses: number;
  netRealizedGain: number;
  estimatedTaxLiability: number | null;
  unrealizedLines: UnrealizedGainLineDto[];
  totalUnrealizedGain: number | null;
  feesPaidTotal: number;
  dividendWithholdingPct: number;
  openPositionCount: number;
}
