/**
 * CORE-R — juicio de reevaluación sobre Lista AUTO + cola Monitor (tipos).
 *
 * Hogar canónico (P2.6, F-DEBT-2) de la familia CORE-R re-declarada
 * anteriormente en `apps/web/src/features/backtests/core-r-judgment.ts`.
 * Solo TIPOS de forma (D5-safe): el valor en wire/localStorage no cambia.
 *
 * La const `CORE_R_ENGINE`/`CORE_R_REPORT_KEY` se quedan en el web; aquí los
 * tipos que la referenciaban usan el literal equivalente `"core-r-v0"` para no
 * depender (backward, evitando ciclos) de una const del web.
 */

/** Motivo de cierre de un ciclo 1-valor dentro de la campaña Lista AUTO. */
export type FullCycleSettleReason =
  | "saved"
  | "skip_lab"
  | "skip_finalists"
  /** Datos de entrada iguales al stamp de Finalistas → no re-analizar. */
  | "skip_fresh";

/** Δ Finalistas respecto al TOP previo al ciclo de ese ticker. */
export type ListAutoChangeKind = "unknown" | "changed" | "same" | "new";

export type CoreRVerdict =
  | "keep"
  | "fresh_ok"
  | "review_lab"
  | "consider_replace"
  | "profile_mismatch"
  | "skipped_weak";

export type CoreRActionId =
  | "lab"
  | "checklist"
  | "propose_f3"
  | "finalists"
  | "none";

export type CoreRAction = {
  id: CoreRActionId;
  label: string;
  href?: string;
};

export type CoreRJudgment = {
  engine: "core-r-v0";
  verdict: CoreRVerdict;
  reason: string;
  actions: CoreRAction[];
};

export type CoreRDualAuditSnap = {
  confidence?: string | null;
  softWeak?: boolean | null;
  challenge?: {
    passed?: boolean;
    checks?: ReadonlyArray<{ code?: string; passed?: boolean }>;
  } | null;
};

/** Señales OOS / EdgeReport para degradación temporal (CORE-R v1.1). */
export type CoreROosSnap = {
  kind?: string | null;
  pbo?: number | null;
  credibility?: number | null;
  oosReturnPct?: number | null;
  edgeBand?: string | null;
};

/** PnL live de cuenta DEMO/paper vinculada al TOP (CORE-R v1.2). */
export type CoreRPaperPnlSnap = {
  accountId: string;
  /** (equity − initialDeposit) / initialDeposit × 100 */
  returnPct: number;
  totalUnrealizedPnl: number;
  totalEquity: number;
  initialDeposit: number;
};

export type CoreRReportRow = {
  instrumentId: string;
  symbol: string;
  verdict: CoreRVerdict;
  reason: string;
  actions: CoreRAction[];
  settleReason?: FullCycleSettleReason;
  change?: ListAutoChangeKind;
};

export type CoreRReport = {
  engine: "core-r-v0";
  listId: string;
  timeframe: string;
  at: string;
  rows: CoreRReportRow[];
};
