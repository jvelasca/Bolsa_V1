/**
 * P12 / FIE F2.0–F2.3 — Gate fundamental para rastreadores + snapshot FA v3.
 *
 * Fuente: Yahoo quoteSummary (cliente httpx en `bolsa_market`, no yfinance).
 * Motor canónico: docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 *
 * F2.0: PE/cap + pack value · F2.1: Piotroski · F2.2: sectorBandsVersion ·
 * F2.3/F2.4: dcfUpside / grahamUpside + WACC sector (`fund_wacc_sector_v1`).
 */

import type { RuleOperator } from './strategy-rules.js';
import {
  FUND_SECTOR_BANDS_VERSION,
  defaultSectorBandConditions,
} from './fundamentals-sector-bands.js';

/** Alineado con Python `bolsa_market.instrument_fundamentals.FUNDAMENTALS_SOURCE_VERSION`. */
export const FUNDAMENTALS_SOURCE_VERSION = 'yahoo_quote_summary_v3';

/** Métricas evaluables en el gate (deben existir en snapshot fundamentals). */
export type FundamentalMetric =
  | 'marketCap'
  | 'trailingPe'
  | 'forwardPe'
  | 'roe'
  | 'debtToEquity'
  | 'currentRatio'
  | 'altmanZ'
  | 'fcfYield'
  | 'operatingMargin'
  | 'revenueGrowth'
  | 'piotroski'
  | 'dcfUpside'
  | 'grahamUpside'
  | 'roic'
  | 'beneishM';

/**
 * Snapshot fundamental persistido en `Instrument.profileSnapshot.fundamentals`.
 * Campos opcionales: cobertura Yahoo unequal por ticker/mercado.
 */
export interface InstrumentFundamentalsV1 {
  marketCap?: number | null;
  trailingPe?: number | null;
  forwardPe?: number | null;
  sector?: string | null;
  roe?: number | null;
  roa?: number | null;
  operatingMargin?: number | null;
  profitMargin?: number | null;
  revenueGrowth?: number | null;
  earningsGrowth?: number | null;
  debtToEquity?: number | null;
  currentRatio?: number | null;
  quickRatio?: number | null;
  totalCash?: number | null;
  totalDebt?: number | null;
  ebitda?: number | null;
  freeCashflow?: number | null;
  /** freeCashflow / marketCap cuando ambos > 0. */
  fcfYield?: number | null;
  priceToBook?: number | null;
  trailingEps?: number | null;
  bookValuePerShare?: number | null;
  sharesOutstanding?: number | null;
  totalAssets?: number | null;
  retainedEarnings?: number | null;
  totalLiabilities?: number | null;
  altmanZ?: number | null;
  altmanMethod?: string | null;
  altmanEbitSource?: string | null;
  /** 0–9 cuando haya series YoY suficientes (F2.1). */
  piotroski?: number | null;
  piotroskiMethod?: string | null;
  /** F2.7 — ROIC NOPAT/IC (`roic_nopat_ic_v1`). */
  roic?: number | null;
  roicMethod?: string | null;
  nopat?: number | null;
  investedCapital?: number | null;
  roicTaxRate?: number | null;
  roicTaxSource?: string | null;
  /** F2.8 — Beneish M-Score (`beneish_m_annual_v1`). */
  beneishM?: number | null;
  beneishMethod?: string | null;
  /** F2.3 — Graham Number por acción (`graham_number_v1`). */
  grahamNumber?: number | null;
  grahamMethod?: string | null;
  /** (Graham − price) / price. */
  grahamUpside?: number | null;
  /** F2.6 — beta Yahoo (CAPM); null si ausente. */
  beta?: number | null;
  /** F2.6 — volumen medio acciones/día (Yahoo). */
  averageVolume?: number | null;
  /** F2.6 — ADV notional ≈ averageVolume × price (USD). */
  advUsd?: number | null;
  /**
   * Tasa descuento DCF: CAPM (`fund_capm_v1`) si hay beta;
   * si no, WACC sector (`fund_wacc_sector_v1`).
   */
  wacc?: number | null;
  waccMethod?: string | null;
  /** F2.6 — r_f usado en CAPM (solo si waccMethod=fund_capm_v1). */
  capmRf?: number | null;
  /** F2.6 — ERP usado en CAPM (solo si waccMethod=fund_capm_v1). */
  capmErp?: number | null;
  /** F2.3/F2.4 — valor equity DCF FCF 2 etapas (`dcf_fcf_2stage_wacc_v1`). */
  dcfEquityValue?: number | null;
  /** (DCF − marketCap) / marketCap. Escenario base. */
  dcfUpside?: number | null;
  dcfMethod?: string | null;
  /** F2.5 — bear/base/bull (`dcf_scenarios_v1`). Null si DCF base no computable. */
  dcfScenarios?: DcfScenariosV1 | null;
  fetchedAt?: string;
  sourceVersion?: string;
}

/** Pierna de escenario DCF (F2.5). */
export interface DcfScenarioLegV1 {
  equityValue: number;
  upside: number;
  growth: number;
  wacc: number;
}

export interface DcfScenariosV1 {
  method: 'dcf_scenarios_v1' | string;
  bear: DcfScenarioLegV1;
  base: DcfScenarioLegV1;
  bull: DcfScenarioLegV1;
}

export interface FundamentalConditionV1 {
  metric: FundamentalMetric;
  operator: RuleOperator;
  value: number;
}

export interface FundamentalGateV1 {
  operator: 'all' | 'any';
  conditions: FundamentalConditionV1[];
  /** Sectores permitidos (vacío = cualquiera). */
  sectors?: string[];
  /** Máxima antigüedad de datos en días (default 30). */
  maxAgeDays?: number;
  /**
   * F2.2 — si presente, Python reescribe umbrales banded según `fundamentals.sector`.
   * Valores de `conditions` = fallback para sector desconocido.
   */
  sectorBandsVersion?: typeof FUND_SECTOR_BANDS_VERSION | string;
}

export interface StrategyDraftFundamentalConditionPreviewDto {
  metric: FundamentalMetric;
  label: string;
  operator: RuleOperator;
  valueLabel: string;
}

export interface StrategyDraftFundamentalPreviewDto {
  enabled: boolean;
  conditions: StrategyDraftFundamentalConditionPreviewDto[];
  sectors: string[];
  maxAgeDays: number;
  dataSource: string;
  refreshNote: string;
  rejectNote: string;
}

export type BuildFundamentalGateOptions = {
  maxTrailingPe?: number | null;
  minMarketCapMillions?: number | null;
  /** Ratio, p.ej. 0.15 = 15%. */
  minRoe?: number | null;
  maxDebtToEquity?: number | null;
  minCurrentRatio?: number | null;
  minAltmanZ?: number | null;
  /** Ratio, p.ej. 0.03 = 3%. */
  minFcfYield?: number | null;
  minOperatingMargin?: number | null;
  minRevenueGrowth?: number | null;
  /** Entero 0–9; solo aplica si el snapshot tiene Piotroski completo. */
  minPiotroski?: number | null;
  /** F2.3 — upside DCF mínimo (ratio, p.ej. 0.2 = +20%). */
  minDcfUpside?: number | null;
  /** F2.3 — upside Graham mínimo (ratio). */
  minGrahamUpside?: number | null;
  /** F2.7 — ROIC mínimo (ratio, p.ej. 0.08 = 8%). */
  minRoic?: number | null;
  /** F2.8 — Beneish M máximo (típicamente −1.78; menor = menos sospechoso). */
  maxBeneishM?: number | null;
  sectors?: string[];
  maxAgeDays?: number;
  /** Default `all`. */
  operator?: 'all' | 'any';
  /**
   * F2.2 — activa `sectorBandsVersion` y rellena condiciones default
   * para métricas banded aún no fijadas en la UI.
   */
  useSectorBands?: boolean;
};

function pushCondition(
  conditions: FundamentalConditionV1[],
  metric: FundamentalMetric,
  operator: RuleOperator,
  value: number | null | undefined,
): void {
  if (value == null || !Number.isFinite(value)) return;
  conditions.push({ metric, operator, value });
}

export function buildFundamentalGate(
  options: BuildFundamentalGateOptions,
): FundamentalGateV1 | undefined {
  const conditions: FundamentalConditionV1[] = [];
  if (options.maxTrailingPe != null && options.maxTrailingPe > 0) {
    pushCondition(conditions, 'trailingPe', 'lte', options.maxTrailingPe);
  }
  if (options.minMarketCapMillions != null && options.minMarketCapMillions > 0) {
    pushCondition(conditions, 'marketCap', 'gte', options.minMarketCapMillions * 1_000_000);
  }
  pushCondition(conditions, 'roe', 'gte', options.minRoe);
  pushCondition(conditions, 'debtToEquity', 'lte', options.maxDebtToEquity);
  pushCondition(conditions, 'currentRatio', 'gte', options.minCurrentRatio);
  pushCondition(conditions, 'altmanZ', 'gte', options.minAltmanZ);
  pushCondition(conditions, 'fcfYield', 'gte', options.minFcfYield);
  pushCondition(conditions, 'operatingMargin', 'gte', options.minOperatingMargin);
  pushCondition(conditions, 'revenueGrowth', 'gte', options.minRevenueGrowth);
  if (options.minPiotroski != null && options.minPiotroski >= 0) {
    pushCondition(conditions, 'piotroski', 'gte', options.minPiotroski);
  }
  pushCondition(conditions, 'dcfUpside', 'gte', options.minDcfUpside);
  pushCondition(conditions, 'grahamUpside', 'gte', options.minGrahamUpside);
  pushCondition(conditions, 'roic', 'gte', options.minRoic);
  pushCondition(conditions, 'beneishM', 'lte', options.maxBeneishM);

  if (options.useSectorBands) {
    const present = new Set(conditions.map((c) => c.metric));
    for (const seed of defaultSectorBandConditions()) {
      if (!present.has(seed.metric)) {
        conditions.push(seed);
        present.add(seed.metric);
      }
    }
  }

  if (
    conditions.length === 0 &&
    !(options.sectors?.length ?? 0) &&
    !options.useSectorBands
  ) {
    return undefined;
  }
  return {
    operator: options.operator ?? 'all',
    conditions,
    sectors: options.sectors?.length ? options.sectors : undefined,
    maxAgeDays: options.maxAgeDays ?? 30,
    ...(options.useSectorBands
      ? { sectorBandsVersion: FUND_SECTOR_BANDS_VERSION }
      : {}),
  };
}

/** Restaura campos de UI desde un gate persistido en la estrategia. */
export function scanFieldsFromFundamentalGate(gate: FundamentalGateV1 | undefined): {
  hybridMaxTrailingPe: number | null;
  hybridMinMarketCapMillions: number | null;
  hybridMinRoe: number | null;
  hybridMaxDebtToEquity: number | null;
  hybridMinCurrentRatio: number | null;
  hybridMinAltmanZ: number | null;
  hybridMinFcfYield: number | null;
  hybridMinOperatingMargin: number | null;
  hybridMinRevenueGrowth: number | null;
  hybridMinPiotroski: number | null;
  hybridMinDcfUpside: number | null;
  hybridMinGrahamUpside: number | null;
  hybridUseSectorBands: boolean;
} {
  const empty = {
    hybridMaxTrailingPe: null as number | null,
    hybridMinMarketCapMillions: null as number | null,
    hybridMinRoe: null as number | null,
    hybridMaxDebtToEquity: null as number | null,
    hybridMinCurrentRatio: null as number | null,
    hybridMinAltmanZ: null as number | null,
    hybridMinFcfYield: null as number | null,
    hybridMinOperatingMargin: null as number | null,
    hybridMinRevenueGrowth: null as number | null,
    hybridMinPiotroski: null as number | null,
    hybridMinDcfUpside: null as number | null,
    hybridMinGrahamUpside: null as number | null,
    hybridUseSectorBands: false,
  };
  if (!gate) return empty;

  const out = { ...empty, hybridUseSectorBands: Boolean(gate.sectorBandsVersion) };
  for (const condition of gate.conditions ?? []) {
    const { metric, operator, value } = condition;
    if (metric === 'trailingPe' && operator === 'lte') out.hybridMaxTrailingPe = value;
    if (metric === 'marketCap' && operator === 'gte') {
      out.hybridMinMarketCapMillions = value / 1_000_000;
    }
    if (metric === 'roe' && operator === 'gte') out.hybridMinRoe = value;
    if (metric === 'debtToEquity' && operator === 'lte') out.hybridMaxDebtToEquity = value;
    if (metric === 'currentRatio' && operator === 'gte') out.hybridMinCurrentRatio = value;
    if (metric === 'altmanZ' && operator === 'gte') out.hybridMinAltmanZ = value;
    if (metric === 'fcfYield' && operator === 'gte') out.hybridMinFcfYield = value;
    if (metric === 'operatingMargin' && operator === 'gte') out.hybridMinOperatingMargin = value;
    if (metric === 'revenueGrowth' && operator === 'gte') out.hybridMinRevenueGrowth = value;
    if (metric === 'piotroski' && operator === 'gte') out.hybridMinPiotroski = value;
    if (metric === 'dcfUpside' && operator === 'gte') out.hybridMinDcfUpside = value;
    if (metric === 'grahamUpside' && operator === 'gte') out.hybridMinGrahamUpside = value;
  }
  return out;
}

const METRIC_LABELS: Record<FundamentalMetric, string> = {
  marketCap: 'Capitalización',
  trailingPe: 'PER trailing',
  forwardPe: 'PER forward',
  roe: 'ROE',
  debtToEquity: 'Deuda/Equity',
  currentRatio: 'Current ratio',
  altmanZ: 'Altman Z',
  fcfYield: 'FCF Yield',
  operatingMargin: 'Margen operativo',
  revenueGrowth: 'Crec. ingresos',
  piotroski: 'Piotroski F',
  dcfUpside: 'DCF upside',
  grahamUpside: 'Graham upside',
  roic: 'ROIC',
  beneishM: 'Beneish M',
};

const OPERATOR_LABELS: Record<RuleOperator, string> = {
  lt: '<',
  lte: '≤',
  gt: '>',
  gte: '≥',
  eq: '=',
};

const PCT_METRICS = new Set<FundamentalMetric>([
  'roe',
  'roic',
  'fcfYield',
  'operatingMargin',
  'revenueGrowth',
  'dcfUpside',
  'grahamUpside',
]);

function formatFundamentalValue(metric: FundamentalMetric, value: number): string {
  if (metric === 'marketCap') {
    const millions = value / 1_000_000;
    return millions >= 1000 ? `${(millions / 1000).toFixed(1)} B€` : `${millions.toFixed(0)} M€`;
  }
  if (PCT_METRICS.has(metric)) {
    return `${(value * 100).toFixed(1)}%`;
  }
  const rounded = Number.isInteger(value) ? String(value) : value.toFixed(2);
  return rounded;
}

/** Vista previa legible del gate fundamental para UI de asistente IA. */
export function buildFundamentalGatePreview(
  gate: FundamentalGateV1 | undefined | null,
): StrategyDraftFundamentalPreviewDto | null {
  if (!gate) return null;
  if (
    !gate.conditions?.length &&
    !(gate.sectors?.length ?? 0) &&
    !gate.sectorBandsVersion
  ) {
    return null;
  }
  const conditions = (gate.conditions ?? []).map((condition) => ({
    metric: condition.metric,
    label: METRIC_LABELS[condition.metric],
    operator: condition.operator,
    valueLabel: `${OPERATOR_LABELS[condition.operator]} ${formatFundamentalValue(condition.metric, condition.value)}`,
  }));
  const bandsNote = gate.sectorBandsVersion
    ? ` Umbrales por sector activos (${gate.sectorBandsVersion}).`
    : '';
  return {
    enabled: true,
    conditions,
    sectors: gate.sectors ?? [],
    maxAgeDays: gate.maxAgeDays ?? 30,
    dataSource: 'Yahoo Finance (quoteSummary v3)',
    refreshNote:
      'Antes del scan se refrescan fundamentales en lote desde Yahoo (P14). Instrumentos sin datos recientes pueden quedar fuera.' +
      bandsNote,
    rejectNote:
      'Si PER, capitalización u otros ratios del gate no cumplen el filtro, el instrumento se descarta antes del rating técnico.',
  };
}

/** Score_FUND [-1, 1] → 0–100 para UI. */
export function fundScoreToDisplay100(scoreFund: number | null | undefined): number | null {
  if (scoreFund == null || !Number.isFinite(scoreFund)) return null;
  const clamped = Math.max(-1, Math.min(1, scoreFund));
  return Math.round(((clamped + 1) / 2) * 100);
}
