/**
 * Platform Kernel — contratos estables (ADR-010).
 * Radar (rastreadores), ejecución manual/auto y research comparten este núcleo.
 * UI y persistencia evolucionan; estos tipos no se rehacen.
 */

import type { ChartTimeframe } from './chart-timeframes.js';
import type { IndicatorSpec } from './research-platform.js';
import type { AlertChannelType } from './signal-alerts-api.js';
import type { SignalKind } from './signal-events.js';

/** Timeframes soportados por el kernel en fase P0–P2 (confirmado producto). */
export const KERNEL_TIMEFRAMES = ['1d', '1wk'] as const satisfies readonly ChartTimeframe[];

export type KernelTimeframe = (typeof KERNEL_TIMEFRAMES)[number];

export function isKernelTimeframe(value: string): value is KernelTimeframe {
  return (KERNEL_TIMEFRAMES as readonly string[]).includes(value);
}

/** Cuándo evaluar señales en rastreadores — bar close primero; realtime reservado. */
export type KernelEvaluationMode = 'bar_close' | 'realtime';

/** Origen de entidades creadas por usuario o IA. */
export type KernelEntityOrigin = 'manual' | 'assisted' | 'ai_generated' | 'preset' | 'imported';

// ─── Tracker (Rastreador) ───────────────────────────────────────────────────

/** Universo de un rastreador — lista o IDs explícitos (EU+US: hasta miles vía listas). */
export interface TrackerUniverseV1 {
  listId?: string;
  instrumentIds?: string[];
}

/**
 * Instancia desplegada de una estrategia sobre un mercado.
 * N rastreadores pueden referenciar la misma StrategyDefinition.
 */
export interface TrackerDefinitionV1 {
  id: string;
  name: string;
  strategyDefinitionId: string;
  /** Pin de versión; null = latest activa en BD */
  strategyVersion: number | null;
  universe: TrackerUniverseV1;
  timeframe: KernelTimeframe;
  barLimit: number;
  maxResults: number;
  evaluationMode: KernelEvaluationMode;
  rankBy?: {
    indicatorSpec: IndicatorSpec;
    direction: 'asc' | 'desc';
  };
  /** Política de ejecución por defecto al detectar hit (H3+) */
  defaultExecutionPolicyId?: string | null;
  schedule?: TrackerScheduleV1 | null;
  origin: KernelEntityOrigin;
  sourcePrompt?: string | null;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export type TrackerScheduleKind = 'manual' | 'on_bar_close' | 'cron';

export interface TrackerScheduleV1 {
  kind: TrackerScheduleKind;
  /** Expresión cron cuando kind === 'cron' */
  cron?: string;
  timezone?: string;
  /** Runtime P9 — última barra OHLCV procesada */
  lastBarTimestamp?: string | null;
  /** Runtime P9 — ISO último encolado */
  lastRunAt?: string | null;
}

// ─── Execution (manual / auto) ────────────────────────────────────────────

export type ExecutionMode =
  | 'inform_only'
  | 'alert'
  | 'paper_auto'
  | 'live_auto';

/**
 * Qué hacer cuando el motor emite SignalEvent (scan, alerta periódica o posición).
 */
export interface ExecutionPolicyV1 {
  id: string;
  name: string;
  mode: ExecutionMode;
  accountId?: string | null;
  strategyDefinitionId?: string | null;
  signalKinds: SignalKind[];
  channels?: AlertChannelType[];
  webhookUrl?: string | null;
  emailTo?: string | null;
  /** Requiere backtest manifest válido para la misma strategyVersion (guardrail) */
  requireValidatedBacktest: boolean;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Política sobre posición ya abierta en cartera. */
export type PositionExecutionMode = 'manual' | 'exit_strategy' | 'full_auto';

export interface PositionPolicyV1 {
  id: string;
  accountId: string;
  instrumentId: string;
  mode: PositionExecutionMode;
  exitStrategyDefinitionId?: string | null;
  executionPolicyId?: string | null;
  createdAt: string;
  updatedAt: string;
}

// ─── Manifests & jobs ─────────────────────────────────────────────────────

export const SCAN_MANIFEST_VERSION = '1.0' as const;

/** Artifact persistido de cada scan (paridad RunManifest). */
export interface ScanManifestV1 {
  manifestVersion: typeof SCAN_MANIFEST_VERSION;
  scanId: string;
  trackerDefinitionId?: string | null;
  strategyDefinitionId: string;
  strategyVersion: number;
  dataVersion: string;
  timeframe: KernelTimeframe;
  universe: TrackerUniverseV1;
  scannedCount: number;
  hitCount: number;
  engine: { name: string; version: string };
  cacheStats?: { hits: number; misses: number };
  dataSnapshots?: import('./research-platform.js').DataSnapshotRef[];
  /** Modo de scan (classic | hybrid). */
  scanMode?: 'classic' | 'hybrid';
  /** Versión del scorer IA (híbrido). */
  scorerVersion?: string | null;
  scorerId?: string | null;
  /** Hash estable del gate técnico + fundamental. */
  gateRuleHash?: string | null;
  /** Versión agregada de snapshots fundamentales usados. */
  fundamentalsVersion?: string | null;
  createdAt: string;
}

export type PlatformJobType =
  | 'scan'
  | 'backtest'
  | 'optimize'
  | 'feature_build'
  | 'ml_train'
  | 'ai_strategy_draft'
  | 'tracker_schedule';

export type PlatformJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

/** Job unificado — scan_jobs / optimization_runs / research convergen aquí (H2). */
export interface PlatformJobSpecV1 {
  id: string;
  type: PlatformJobType;
  status: PlatformJobStatus;
  payload: Record<string, unknown>;
  resultRef?: string | null;
  error?: string | null;
  userId?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
}

// ─── Event bus (contrato; impl Python H2) ───────────────────────────────────

export type PlatformEventType =
  | 'signal.emitted'
  | 'scan.completed'
  | 'backtest.completed'
  | 'execution.order_requested'
  | 'execution.order_filled';

export interface PlatformEventV1<T extends Record<string, unknown> = Record<string, unknown>> {
  id: string;
  type: PlatformEventType;
  timestamp: string;
  payload: T;
  correlationId?: string;
}

/** Límites de escala kernel — EU+US, miles de símbolos vía listas + jobs particionados. */
export const KERNEL_SCALE_LIMITS = {
  maxInstrumentsPerScanRequest: 5000,
  maxInstrumentsPerScanChunk: 250,
  maxConcurrentScanJobs: 32,
  maxTrackersPerUser: 200,
  featureCacheTtlSeconds: 3600,
} as const;
