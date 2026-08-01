/**
 * FIE F4 — Screener FA: Universo × gate → lista blanca (sin timing técnico).
 *
 * Python evalúa `fundamentalGate` sobre snapshots; no OHLCV / Score_TA.
 * Persistencia opcional → InstrumentList `kind=snapshot`.
 *
 * @see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
 */

import type { FundamentalGateV1 } from './fundamentals-gate.js';

export const FUNDAMENTAL_SCREENER_VERSION = 'fund_screener_v1' as const;

export interface FundamentalScreenerUniverseV1 {
  listId?: string;
  instrumentIds?: string[];
}

export interface FundamentalScreenerPersistV1 {
  /** Actualiza lista custom/snapshot existente. */
  listId?: string;
  /** Nombre si se crea lista nueva (default semanal). */
  name?: string;
}

export interface FundamentalScreenerRunRequestV1 {
  universe: FundamentalScreenerUniverseV1;
  fundamentalGate: FundamentalGateV1;
  /** Refrescar Yahoo si snapshot stale (default true). */
  refreshStale?: boolean;
  maxResults?: number;
  persist?: FundamentalScreenerPersistV1 | null;
}

export interface FundamentalScreenerHitV1 {
  instrumentId: string;
  symbol: string;
  name?: string | null;
  sector?: string | null;
  scoreDisplay100?: number | null;
  trailingPe?: number | null;
  roe?: number | null;
  piotroski?: number | null;
  fcfYield?: number | null;
  dcfUpside?: number | null;
  grahamUpside?: number | null;
  confidence?: string | null;
}

export interface FundamentalScreenerSkipV1 {
  instrumentId: string;
  symbol?: string | null;
  reason: string;
}

export interface FundamentalScreenerRunResultV1 {
  screenerVersion: typeof FUNDAMENTAL_SCREENER_VERSION | string;
  screenerId: string;
  scannedCount: number;
  hitCount: number;
  skippedCount: number;
  fundamentalsRefreshedCount: number;
  listId?: string | null;
  persistedListId?: string | null;
  weekKey: string;
  hits: FundamentalScreenerHitV1[];
  skipped: FundamentalScreenerSkipV1[];
}

export interface FundamentalScreenerRunResponseV1 {
  data: FundamentalScreenerRunResultV1;
}
