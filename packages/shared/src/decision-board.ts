/**
 * F0.6 — Decision Board (web read-only). Contrato compartido API ↔ web para el
 * tablero de acciones del "Decision Spine".
 *
 * @see apps/api-python/src/bolsa_api/schemas/accounts.py (DecisionBoardDto)
 */

import type { TradePlanV1 } from "./cognitive/trade-plan.js";
import type { ThesisHealthV1 } from "./cognitive/thesis-health.js";
import type { ProtectPlanV1 } from "./cognitive/protect-plan.js";
import type { ExitRadarV1 } from "./cognitive/exit-radar.js";

export type DecisionGate = "PASS" | "VETO" | "DEFERRED" | "unknown";

export type DecisionBoardBucketCountsV1 = {
  pendingConfirm: number;
  vetoed: number;
  deferred: number;
  autoWaiting: number;
  total: number;
};

export type DecisionSessionViewV1 = {
  sessionId: string;
  kind: string;
  status: string;
  instrumentId: string;
  symbol?: string | null;
  decisionId?: string | null;
  createdAt: string;
  /** TODO(f0.6) normalizar a union DecisionGate cuando el backend lo garantice. */
  gate: string;
  /** Plan condicional vivo (ADR-031); ausente → Hoy usa heurística de gate. */
  tradePlan?: TradePlanV1;
  /** Ciclo 4.9 — echo runtime Setup (phase/effort); no tipado canónico. */
  wyckoffSpringAnchor?: Record<string, unknown>;
  /** Ciclo 5.0 — Thesis Health advisory (Golden F); ≠ TradePlan.status. */
  thesisHealth?: ThesisHealthV1 | Record<string, unknown>;
  /** Ciclo 5.1 — Protect/T1 advisory (Golden E); no muta structuralStop. */
  protectPlan?: ProtectPlanV1 | Record<string, unknown>;
  /** Ciclo 5.2 — Exit Radar advisory; no auto-exit. */
  exitRadar?: ExitRadarV1 | Record<string, unknown>;
};

export type SemiF3ViewV1 = {
  instrumentId?: string | null;
  symbol?: string | null;
  status: string;
  extra?: Record<string, unknown>;
};

export type DecisionBoardV1 = {
  accountId: string;
  generatedAt: string;
  buckets: DecisionBoardBucketCountsV1;
  semiF3Queue: SemiF3ViewV1[];
  decisionSessions: DecisionSessionViewV1[];
  equity?: number | null;
  freeMargin?: number | null;
};

export type DecisionBoardResponseV1 = {
  data: DecisionBoardV1;
};
