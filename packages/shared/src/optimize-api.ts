import type { ChartTimeframe } from './chart-timeframes.js';

export type OptimizeStrategyFamily =
  | 'sma_crossover'
  | 'rsi_mean_reversion'
  | 'macd_signal_cross';

export interface OosMetricsDto {
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  score: number;
  sharpeRatio?: number | null;
}

export interface SmaGridTrialDto {
  /** SMA / MACD fast period (absent or 0 for RSI). */
  fastPeriod?: number | null;
  /** SMA / MACD slow period. */
  slowPeriod?: number | null;
  signalPeriod?: number | null;
  /** RSI period. */
  period?: number | null;
  oversold?: number | null;
  overbought?: number | null;
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  score: number;
  /** Out-of-sample metrics when hold-out was enabled. */
  oosMetrics?: OosMetricsDto | null;
}

export type OptimizeEngine = 'auto' | 'h0' | 'vectorbt' | 'optuna';

export interface OptimizeSmaGridRequestDto {
  instrumentId: string;
  strategyFamily?: OptimizeStrategyFamily;
  fastPeriods?: number[];
  slowPeriods?: number[];
  /** RSI search space. */
  periods?: number[];
  oversoldLevels?: number[];
  overboughtLevels?: number[];
  /** MACD [fast, slow, signal] triples. */
  macdTriples?: number[][];
  initialCash?: number;
  barLimit?: number;
  timeframe?: ChartTimeframe;
  maxTrials?: number;
  engine?: OptimizeEngine;
  /** Hold-out fraction (e.g. 0.2). Omit or 0 to disable. */
  oosPct?: number | null;
  /** Expanding walk-forward folds (2–5). When set, overrides oosPct; H0 only. */
  walkForwardFolds?: number | null;
  /** CPCV ligero groups (4–6). Overrides walkForwardFolds and oosPct; H0 only. */
  cpcvGroups?: number | null;
  /** Bars purged from train before each test block (0–20). */
  cpcvPurgeBars?: number | null;
  /** Bars embargoed from train after each test block (0–20). */
  cpcvEmbargoBars?: number | null;
}

export interface WalkForwardFoldDto {
  index: number;
  trainBarCount: number;
  testBarCount: number;
  testStartTimestamp?: string | null;
  bestParams: Record<string, number>;
  isScore: number;
  oosMetrics?: OosMetricsDto | null;
  /** Per-fold OOS/IS score ratio when IS > 0. */
  walkForwardEfficiency?: number | null;
}

export interface WalkForwardSummaryDto {
  nFolds: number;
  mode: string;
  meanOosScore: number;
  stdOosScore: number;
  foldCount: number;
  foldScores: number[];
  folds: WalkForwardFoldDto[];
  /** Mean IS score of selected fold champions. */
  meanIsScore?: number | null;
  /**
   * Lab WFE = meanOosScore / meanIsScore when meanIsScore > 0.
   * Not CPCV/PBO; same score objective as the grid (return − 0.25×maxDD).
   */
  walkForwardEfficiency?: number | null;
  /** Share of folds with OOS score ≥ 0 (0–1). */
  positiveOosFoldShare?: number | null;
  /** Coefficient of variation of fold OOS scores (std / |mean|); lower = more stable. */
  oosCv?: number | null;
}

export interface CpcvPathDto {
  index: number;
  testGroupIndices: number[];
  trainBarCount: number;
  testBarCount: number;
  testStartTimestamp?: string | null;
  bestParams: Record<string, number>;
  isScore: number;
  oosMetrics?: OosMetricsDto | null;
  walkForwardEfficiency?: number | null;
}

/** CSCV PBO lab lite (Bailey et al.). Lower is better; ≥0.5 ≈ coin flip. */
export interface PboSummaryDto {
  pbo: number;
  splitCount: number;
  segmentCount: number;
  strategyCount: number;
  meanLogit: number;
  stdLogit: number;
  belowMedianCount: number;
  mode: 'cscv_lab' | string;
  warnThreshold?: number;
  badThreshold?: number;
}

export interface CpcvSummaryDto {
  nGroups: number;
  nTestGroups: number;
  purgeBars: number;
  embargoBars: number;
  pathCount: number;
  mode: string;
  meanOosScore: number;
  stdOosScore: number;
  foldCount: number;
  foldScores: number[];
  paths: CpcvPathDto[];
  meanIsScore?: number | null;
  walkForwardEfficiency?: number | null;
  positiveOosFoldShare?: number | null;
  oosCv?: number | null;
  pbo?: PboSummaryDto | null;
}

/** Compact EdgeReport from optimize lab (MC + PSR/DSR + lab WFE). Not full cognitive persist. */
export interface LabEdgeReportLiteDto {
  artifactType: string;
  schemaVersion: string;
  edgeReportId: string;
  strategyOrSignalRef: string;
  credibility: number;
  edgeScore: number;
  band: 'skill' | 'uncertain' | 'luck' | string;
  notes?: string[];
  autoLiveEligible?: boolean;
  blockReasons?: string[];
  suite: {
    trialsN: number;
    walkForwardEfficiency?: number | null;
    wfeSource?: 'lab_score' | 'sharpe' | null;
    monteCarloPValue?: number | null;
    psr?: number | null;
    dsr?: number | null;
    historicalWinRate?: number | null;
    sampleTradesCount?: number | null;
  };
  sampleTradesCount?: number;
  mode: 'lab_lite' | string;
  /** Echo of CSCV PBO when computed with CPCV. */
  pbo?: number | null;
  /** P8 — id in cognitive `edge_reports` after optimize persist (not auto-live). */
  persistedEdgeReportId?: string | null;
}

export interface OptimizeSmaGridResultDto {
  instrumentId: string;
  barCount: number;
  baseline: SmaGridTrialDto;
  trials: SmaGridTrialDto[];
  engine: string;
  /** Estimated / planned trials for this search space. */
  trialsTotal?: number;
  strategyFamily?: OptimizeStrategyFamily | string;
  oosPct?: number | null;
  isBarCount?: number | null;
  oosBarCount?: number | null;
  splitTimestamp?: string | null;
  walkForward?: WalkForwardSummaryDto | null;
  cpcv?: CpcvSummaryDto | null;
  edgeReport?: LabEdgeReportLiteDto | null;
  /** Top-level PBO when CPCV CSCV ran (also under cpcv.pbo). */
  pbo?: PboSummaryDto | null;
}

export interface OptimizeSmaGridResponseDto {
  data: OptimizeSmaGridResultDto;
  runId?: string | null;
}

export type OptimizationRunStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface OptimizationRunDto {
  id: string;
  instrumentId: string;
  symbol: string;
  status: OptimizationRunStatus;
  payload: OptimizeSmaGridRequestDto & { trialsTotal?: number };
  result?: OptimizeSmaGridResultDto | null;
  error?: string | null;
  engine?: string | null;
  bestScore?: number | null;
  /** Trials completed so far (also set while status=processing). */
  trialCount?: number | null;
  barCount?: number | null;
  createdAt: string;
  updatedAt: string;
  completedAt?: string | null;
}

export interface OptimizationRunResponseDto {
  data: OptimizationRunDto;
}

export interface OptimizationRunsListResponseDto {
  data: OptimizationRunDto[];
}
