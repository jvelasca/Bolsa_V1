/**
 * DTOs de hechos Coach (CORE-A) — forma concreta serializada al
 * `analyzeBacktestCoach` (campo `facts`) y persistida en `coachFacts`.
 *
 * El wire no cambia; este DTO refleja la shape de `CoachFactsV1` (web) para
 * que `backtest-explore-panel.tsx` y el proveedor LLM no necesiten
 * `as unknown as`. `ProfileHorizon`/`RiskTolerance` viven aquí (compartido).
 */

import type {
  ProfileHorizon,
  RiskTolerance,
} from "./cognitive/investor-profile.js";

export type CoachFactsV1Dto = {
  schemaVersion: "1.0.0";
  symbol: string;
  timeframe: string;
  periodLabel?: string;
  horizon: ProfileHorizon;
  riskTolerance?: RiskTolerance | null;
  evidenceLevel: "in_sample_only" | "lab_validated";
  starCeiling: 3 | 5;
  buyHoldReturnPct: number | null;
  okCount: number;
  windows: {
    earlyBestLabel?: string;
    midBestLabel?: string;
    lateBestLabel?: string;
    shifted: boolean;
    narrative: string;
  };
  recommendations: Array<{
    rank: number;
    strategyType: string;
    label: string;
    category: string;
    score: number;
    stars: number;
    starsCapped: boolean;
    totalReturnPct?: number;
    excessReturnPct?: number | null;
    maxDrawdownPct?: number;
    earlyReturnPct?: number | null;
    midReturnPct?: number | null;
    lateReturnPct?: number | null;
    usedSoftFallback?: boolean;
    qualityFlagged?: boolean;
    runId?: string;
  }>;
};
