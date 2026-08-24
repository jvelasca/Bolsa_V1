/**
 * F0.6 — Decision Board (web read-only). Contrato compartido API ↔ web para el
 * tablero de acciones del "Decision Spine".
 *
 * @see apps/api-python/src/bolsa_api/schemas/accounts.py (DecisionBoardDto)
 */

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
