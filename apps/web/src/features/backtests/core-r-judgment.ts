/**
 * CORE-R — juicio de reevaluación sobre Lista AUTO + cola Monitor.
 *
 * - v0: post-settle → verdict + acciones (deep-links) · informe `bolsa-core-r-report-v1`
 * - v1: Monitor «Encolar revisiones»
 * - v1.1: OOS degradation
 * - v1.2: PnL DEMO live (−5% / −10%)
 * - v1.3: narración Evidence
 * - v1.4: cron shell (`CoreRSchedulerHost`)
 * - v1.5: chip barra Trading → Ayuda · Monitor
 * - v1.6: toast al encolar (cron shell)
 *
 * Heurístico / determinista. No pisa Finalistas active. No auto-paper D.
 *
 * @see research/observations/ISSUES.md · CORE-R
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 * @see docs/engineering/operativa-test-plan-2026-07-31.md
 */

import type { FullCycleSettleReason } from "@/features/backtests/backtest-list-auto";
import type { ListAutoChangeKind } from "@/features/backtests/backtest-list-auto-board";
import { strategyMonitorChecklistHref } from "@/features/backtests/strategy-monitor";
import { instrumentTopBacktestsHref } from "@/features/backtests/instrument-strategy-top-panel";

export const CORE_R_ENGINE = "core-r-v0";
export const CORE_R_REPORT_KEY = "bolsa-core-r-report-v1";

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
  engine: typeof CORE_R_ENGINE;
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

export type CoreRJudgeInput = {
  settleReason: FullCycleSettleReason;
  change: ListAutoChangeKind;
  evidenceLevel?: string | null;
  dualAudit?: CoreRDualAuditSnap | null;
  oos?: CoreROosSnap | null;
  paperPnl?: CoreRPaperPnlSnap | null;
  topProfileId?: string | null;
  activeProfileId?: string | null;
  hasPaper?: boolean;
  slot1RunId?: string | null;
  instrumentId: string;
  timeframe: string;
  symbol?: string;
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
  engine: typeof CORE_R_ENGINE;
  listId: string;
  timeframe: string;
  at: string;
  rows: CoreRReportRow[];
};

export function coreRVerdictLabel(v: CoreRVerdict): string {
  switch (v) {
    case "keep":
      return "Mantener";
    case "fresh_ok":
      return "Fresco OK";
    case "review_lab":
      return "Revisar Lab";
    case "consider_replace":
      return "Valorar cambio";
    case "profile_mismatch":
      return "Perfil ≠ TOP";
    case "skipped_weak":
      return "Débil · skip";
    default:
      return v;
  }
}

/** Verdicts that need human follow-up (Lista AUTO «a revisar» · cola Monitor). */
export function coreRNeedsAction(
  verdict: CoreRVerdict | null | undefined,
): boolean {
  if (!verdict) return false;
  return verdict !== "keep" && verdict !== "fresh_ok";
}

/** Rows from a saved report that need review. */
export function listCoreRActionRows(
  report: CoreRReport | null | undefined,
): CoreRReportRow[] {
  if (!report) return [];
  return report.rows.filter((r) => coreRNeedsAction(r.verdict));
}

/** Heurística: OOS/PBO/credibilidad debilitan el TOP → revisar / valorar cambio. */
export function coreROosDegradation(
  oos: CoreROosSnap | null | undefined,
): { level: "review_lab" | "consider_replace"; reason: string } | null {
  if (!oos || !oos.kind || oos.kind === "none") return null;
  if (typeof oos.pbo === "number" && oos.pbo >= 0.5) {
    return {
      level: "consider_replace",
      reason: `PBO OOS elevado (${oos.pbo.toFixed(2)}) · riesgo sobreajuste`,
    };
  }
  const band = (oos.edgeBand ?? "").toLowerCase();
  if (band === "weak" || band === "poor" || band === "none") {
    return {
      level: "review_lab",
      reason: `Edge OOS «${oos.edgeBand}» · revisar Lab`,
    };
  }
  if (typeof oos.credibility === "number" && oos.credibility < 0.35) {
    return {
      level: "review_lab",
      reason: `Credibilidad OOS baja (${oos.credibility.toFixed(2)})`,
    };
  }
  if (typeof oos.oosReturnPct === "number" && oos.oosReturnPct < 0) {
    return {
      level: "consider_replace",
      reason: `Retorno OOS negativo (${oos.oosReturnPct.toFixed(1)}%)`,
    };
  }
  return null;
}

/** Return % vs depósito inicial (DEMO/paper vinculada). */
export function coreRAccountReturnPct(
  initialDeposit: number,
  totalEquity: number,
): number | null {
  if (!Number.isFinite(initialDeposit) || initialDeposit <= 0) return null;
  if (!Number.isFinite(totalEquity)) return null;
  return ((totalEquity - initialDeposit) / initialDeposit) * 100;
}

/**
 * Heurística: PnL live de la demo/paper del TOP.
 * No pisa Finalistas; solo sugiere revisar / cambiar.
 */
export function coreRPaperPnlDegradation(
  pnl: CoreRPaperPnlSnap | null | undefined,
): { level: "review_lab" | "consider_replace"; reason: string } | null {
  if (!pnl || !Number.isFinite(pnl.returnPct)) return null;
  if (pnl.returnPct <= -10) {
    return {
      level: "consider_replace",
      reason: `Demo/paper PnL ${pnl.returnPct.toFixed(1)}% vs depósito · valorar cambio`,
    };
  }
  if (pnl.returnPct <= -5) {
    return {
      level: "review_lab",
      reason: `Demo/paper PnL ${pnl.returnPct.toFixed(1)}% · revisar Lab / checklist`,
    };
  }
  return null;
}

function checkFailed(
  audit: CoreRDualAuditSnap | null | undefined,
  code: string,
): boolean {
  const checks = audit?.challenge?.checks;
  if (!checks) return false;
  return checks.some((c) => c.code === code && c.passed === false);
}

function buildActions(opts: {
  verdict: CoreRVerdict;
  instrumentId: string;
  timeframe: string;
  symbol?: string;
  slot1RunId?: string | null;
  hasPaper?: boolean;
}): CoreRAction[] {
  const { verdict, instrumentId, timeframe, symbol, slot1RunId, hasPaper } =
    opts;
  const actions: CoreRAction[] = [];
  const finalistsHref = instrumentTopBacktestsHref(instrumentId, timeframe);
  const labHref = `/backtests?tab=jobs&instrumentId=${encodeURIComponent(instrumentId)}&timeframe=${encodeURIComponent(timeframe)}`;
  const proposeHref = `/help?section=ai-platform&focus=supervised-f3${
    symbol ? `&symbol=${encodeURIComponent(symbol)}` : ""
  }`;

  if (verdict === "fresh_ok" || verdict === "keep") {
    actions.push({ id: "finalists", label: "Finalistas", href: finalistsHref });
    if (hasPaper && slot1RunId) {
      actions.push({
        id: "checklist",
        label: "Checklist",
        href: strategyMonitorChecklistHref(instrumentId, slot1RunId, timeframe),
      });
    }
    return actions.length ? actions : [{ id: "none", label: "—" }];
  }

  if (verdict === "profile_mismatch" || verdict === "skipped_weak") {
    actions.push({ id: "finalists", label: "Ver TOP", href: finalistsHref });
    actions.push({ id: "lab", label: "Lab", href: labHref });
    return actions;
  }

  if (verdict === "review_lab") {
    actions.push({ id: "lab", label: "Lab", href: labHref });
    actions.push({ id: "finalists", label: "Finalistas", href: finalistsHref });
    return actions;
  }

  // consider_replace
  actions.push({ id: "lab", label: "Lab", href: labHref });
  actions.push({ id: "finalists", label: "Finalistas", href: finalistsHref });
  actions.push({ id: "propose_f3", label: "Proponer F3", href: proposeHref });
  if (slot1RunId) {
    actions.push({
      id: "checklist",
      label: "Checklist",
      href: strategyMonitorChecklistHref(instrumentId, slot1RunId, timeframe),
    });
  }
  return actions;
}

/**
 * Juicio CORE-R tras settle Lista AUTO / ciclo 1 valor.
 * No muta TOP; solo sugiere.
 */
export function judgeCoreR(input: CoreRJudgeInput): CoreRJudgment {
  const {
    settleReason,
    change,
    evidenceLevel,
    dualAudit,
    topProfileId,
    activeProfileId,
    hasPaper,
    slot1RunId,
    instrumentId,
    timeframe,
  } = input;

  const mk = (verdict: CoreRVerdict, reason: string): CoreRJudgment => ({
    engine: CORE_R_ENGINE,
    verdict,
    reason,
    actions: buildActions({
      verdict,
      instrumentId,
      timeframe,
      symbol: input.symbol,
      slot1RunId,
      hasPaper,
    }),
  });

  if (settleReason === "skip_fresh") {
    return mk("fresh_ok", "Finalistas frescos · sin re-scan (Omitido)");
  }

  if (topProfileId && activeProfileId && topProfileId !== activeProfileId) {
    return mk(
      "profile_mismatch",
      "TOP stamp de otro perfil · re-Play recomendado (CORE-P)",
    );
  }

  if (settleReason === "skip_lab") {
    return mk(
      "skipped_weak",
      "Coach¹ débil · Lab omitido · Finalistas intactos",
    );
  }

  const oosHit = coreROosDegradation(input.oos);
  if (oosHit) {
    return mk(oosHit.level, oosHit.reason);
  }

  const pnlHit = coreRPaperPnlDegradation(input.paperPnl);
  if (pnlHit) {
    return mk(pnlHit.level, pnlHit.reason);
  }

  const confidence = dualAudit?.confidence ?? null;
  const softWeak = Boolean(dualAudit?.softWeak);
  const beatsBhFailed = checkFailed(dualAudit, "top_beats_bh");
  const lateFailed = checkFailed(dualAudit, "top_late_nonneg");

  if (settleReason === "skip_finalists") {
    if (beatsBhFailed || lateFailed || confidence === "weak" || softWeak) {
      return mk(
        "consider_replace",
        "Sin mejora Lab · señales débiles vs B&H/reciente",
      );
    }
    return mk("review_lab", "Lab sin Mejor adoptável · revisar espacio / OOS");
  }

  // saved
  if (evidenceLevel && evidenceLevel !== "lab_validated") {
    return mk(
      "review_lab",
      "TOP sin lab_validated · pasa por Lab antes de paper",
    );
  }

  if (confidence === "weak" || softWeak) {
    return mk("review_lab", "Dual-audit débil tras ciclo · Lab / ack");
  }

  if (beatsBhFailed || lateFailed) {
    return mk(
      "consider_replace",
      beatsBhFailed
        ? "#1 no bate B&H · valorar sustituir"
        : "#1 tramo reciente negativo · valorar sustituir",
    );
  }

  if (confidence === "discrepancy") {
    return mk(
      "consider_replace",
      "Discrepancia A/A2/C · revisar antes de paper",
    );
  }

  if (change === "changed" || change === "new") {
    return mk(
      "keep",
      change === "new"
        ? "Nuevo TOP lab · mantener y vigilar"
        : "Finalistas actualizados · mantener",
    );
  }

  return mk("keep", "TOP estable · lab_validated · mantener");
}

type ReportStore = Record<string, CoreRReport>;

function readStore(): ReportStore {
  try {
    const raw = localStorage.getItem(CORE_R_REPORT_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      return {};
    return parsed as ReportStore;
  } catch {
    return {};
  }
}

function writeStore(store: ReportStore): void {
  try {
    localStorage.setItem(CORE_R_REPORT_KEY, JSON.stringify(store));
  } catch {
    // quota
  }
}

export function readAllCoreRReports(): ReportStore {
  return { ...readStore() };
}

export function replaceAllCoreRReports(store: ReportStore): void {
  writeStore(store);
}

export function saveCoreRReport(
  report: Omit<CoreRReport, "engine"> & { engine?: string },
): CoreRReport {
  const full: CoreRReport = {
    ...report,
    engine: CORE_R_ENGINE,
  };
  const store = readStore();
  store[full.listId] = full;
  writeStore(store);
  // Q3.4 — push BD (lazy import evita ciclo con core-r-sync).
  void import("@/features/backtests/core-r-sync").then((m) =>
    m.scheduleCoreRPush(),
  );
  return full;
}

export function readCoreRReport(
  listId: string | null | undefined,
): CoreRReport | null {
  if (!listId) return null;
  const rec = readStore()[listId];
  if (!rec || rec.engine !== CORE_R_ENGINE) return null;
  return rec;
}

export function readCoreRVerdictForInstrument(
  listId: string | null | undefined,
  instrumentId: string,
): CoreRReportRow | null {
  const report = readCoreRReport(listId);
  if (!report) return null;
  return report.rows.find((r) => r.instrumentId === instrumentId) ?? null;
}

/** Fila de cola desde PnL live DEMO/paper (sin informe Lista AUTO). */
export function buildCoreRPaperPnlReviewRow(opts: {
  instrumentId: string;
  symbol: string;
  timeframe: string;
  pnl: CoreRPaperPnlSnap;
  slot1RunId?: string | null;
}): CoreRReportRow | null {
  const hit = coreRPaperPnlDegradation(opts.pnl);
  if (!hit) return null;
  const judgment = judgeCoreR({
    settleReason: "saved",
    change: "same",
    evidenceLevel: "lab_validated",
    paperPnl: opts.pnl,
    hasPaper: true,
    slot1RunId: opts.slot1RunId,
    instrumentId: opts.instrumentId,
    timeframe: opts.timeframe,
    symbol: opts.symbol,
  });
  return {
    instrumentId: opts.instrumentId,
    symbol: opts.symbol,
    verdict: judgment.verdict,
    reason: judgment.reason,
    actions: judgment.actions,
  };
}

/** Construye informe desde filas del tablero (tras campaña). */
export function buildCoreRReportFromBoard(opts: {
  listId: string;
  timeframe: string;
  rows: ReadonlyArray<{
    instrumentId: string;
    symbol: string;
    reeval?: CoreRJudgment | null;
    settleReason?: FullCycleSettleReason;
    change?: ListAutoChangeKind;
  }>;
}): CoreRReport {
  return {
    engine: CORE_R_ENGINE,
    listId: opts.listId,
    timeframe: opts.timeframe,
    at: new Date().toISOString(),
    rows: opts.rows
      .filter((r) => r.reeval)
      .map((r) => ({
        instrumentId: r.instrumentId,
        symbol: r.symbol,
        verdict: r.reeval!.verdict,
        reason: r.reeval!.reason,
        actions: r.reeval!.actions,
        settleReason: r.settleReason,
        change: r.change,
      })),
  };
}
