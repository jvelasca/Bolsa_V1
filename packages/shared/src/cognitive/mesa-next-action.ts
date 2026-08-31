/**
 * Mesa · Hoy — proyección única de CTA (V1.16).
 * La UI no inventa acciones; mapea autoridad del dominio.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { ExitSuggestedActionV1 } from "./exit-plan.js";
import type { ProtectPlanV1 } from "./protect-plan.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import type { HoyActionKindV1 } from "./hoy-queue.js";
import {
  buildEntryOperatingTruth,
  mesaNextActionFromEntryOperatingTruth,
} from "./entry-operating-truth.js";
import {
  buildDataFreshness,
  mesaDataFreshnessFromContract,
  type DataFreshnessV1,
} from "./data-freshness.js";
import {
  buildPortfolioRiskSnapshot,
  sumPortfolioUnrealizedR,
  type PortfolioPositionRiskInput,
} from "./portfolio-risk-metrics.js";
import { buildMesaOperationalStatusDetail } from "./mesa-operational-health.js";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";

export { sumPortfolioUnrealizedR };
export type { DataFreshnessV1, PortfolioPositionRiskInput };

export type MesaNextActionKindV1 =
  | "none"
  | "maintain"
  | "protect"
  | "reduce"
  | "exit"
  | "review"
  | "review_filter"
  | "review_proposal"
  | "view_thesis"
  | "watch";

export type MesaNextActionV1 = {
  kind: MesaNextActionKindV1;
  label: string;
  /** Nunca COMPRAR — invariante ADR-037. */
  allowsEntry: boolean;
};

export const MESA_NEXT_ACTION_LABELS: Record<MesaNextActionKindV1, string> = {
  none: "—",
  maintain: "Mantener",
  protect: "Proteger",
  reduce: "Reducir",
  exit: "Salir",
  review: "Revisar",
  review_filter: "Revisar filtro",
  review_proposal: "Revisar propuesta",
  view_thesis: "Ver tesis",
  watch: "Vigilar",
};

export type MapMesaNextActionInput = {
  entriesBlocked?: boolean;
  tradePlanStatus?: TradePlanStatusV1 | null;
  exitSuggestedAction?: ExitSuggestedActionV1 | null;
  protectPlan?: Pick<ProtectPlanV1, "status"> | null;
  attentionKind?: HoyActionKindV1 | null;
  hasOpenPosition?: boolean;
  hasOperationalPlan?: boolean;
  /** PH-1 — persist skipped / error. */
  protectionDiscrepancy?: boolean;
};

function blockedEntry(input: MapMesaNextActionInput): boolean {
  if (input.entriesBlocked) return true;
  if (input.tradePlanStatus === "BLOCKED") return true;
  if (input.tradePlanStatus === "EXPIRED") return true;
  return false;
}

export function mapMesaNextAction(
  input: MapMesaNextActionInput,
): MesaNextActionV1 {
  // V1.42 §A.8 — full_exit / reduce win over protectionDiscrepancy.
  // Discrepancy alone (no exit/reduce) still maps to protect.
  const exit = input.exitSuggestedAction;
  if (exit === "full_exit") {
    return {
      kind: "exit",
      label: MESA_NEXT_ACTION_LABELS.exit,
      allowsEntry: false,
    };
  }
  if (exit === "reduce") {
    return {
      kind: "reduce",
      label: MESA_NEXT_ACTION_LABELS.reduce,
      allowsEntry: false,
    };
  }

  if (input.protectionDiscrepancy) {
    return {
      kind: "protect",
      label: MESA_NEXT_ACTION_LABELS.protect,
      allowsEntry: false,
    };
  }

  if (exit === "protect" || input.protectPlan?.status === "protect_hint") {
    return {
      kind: "protect",
      label: MESA_NEXT_ACTION_LABELS.protect,
      allowsEntry: false,
    };
  }

  if (input.attentionKind === "REVIEW") {
    return {
      kind: "review",
      label: MESA_NEXT_ACTION_LABELS.review,
      allowsEntry: false,
    };
  }
  if (input.attentionKind === "BLOCKED") {
    return {
      kind: "review_filter",
      label: MESA_NEXT_ACTION_LABELS.review_filter,
      allowsEntry: false,
    };
  }

  if (blockedEntry(input)) {
    return {
      kind: "none",
      label: MESA_NEXT_ACTION_LABELS.none,
      allowsEntry: false,
    };
  }

  const status = input.tradePlanStatus;
  if (status === "TRIGGERED") {
    return {
      kind: "review_proposal",
      label: MESA_NEXT_ACTION_LABELS.review_proposal,
      allowsEntry: false,
    };
  }
  if (status === "ARMED") {
    return {
      kind: "view_thesis",
      label: MESA_NEXT_ACTION_LABELS.view_thesis,
      allowsEntry: false,
    };
  }
  if (status === "WATCH" || input.hasOperationalPlan === false) {
    return {
      kind: "watch",
      label: MESA_NEXT_ACTION_LABELS.watch,
      allowsEntry: false,
    };
  }

  if (input.hasOpenPosition && (exit === "hold" || exit == null)) {
    return {
      kind: "maintain",
      label: MESA_NEXT_ACTION_LABELS.maintain,
      allowsEntry: false,
    };
  }

  return {
    kind: "watch",
    label: MESA_NEXT_ACTION_LABELS.watch,
    allowsEntry: false,
  };
}

/** @deprecated Usar sumPortfolioUnrealizedR — P&L no realizado en R. */
export function sumPortfolioPnLR(
  positions: ReadonlyArray<{
    operational?: { unrealizedR?: number | null } | null;
  }>,
): number | null {
  return sumPortfolioUnrealizedR(positions);
}

export type MesaOperationalStatusV1 = "normal" | "attention" | "blocked";

export function deriveMesaOperationalStatus(input: {
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  queryFailed?: boolean;
  dataFreshnessStatus?: import("./data-freshness.js").DataFreshnessStatusV1;
  readinessState?: string | null;
}): MesaOperationalStatusV1 {
  return buildMesaOperationalStatusDetail(input).status;
}

export type MesaDataFreshnessV1 =
  | { state: "unknown"; label: string }
  | { state: "fresh"; label: string; ageMinutes: number }
  | { state: "stale"; label: string; ageMinutes: number }
  | { state: "error"; label: string };

export function deriveMesaDataFreshness(input: {
  lastBarDate?: string | null;
  queryFailed?: boolean;
  now?: Date;
  maxAgeMinutes?: number;
}): MesaDataFreshnessV1 {
  return mesaDataFreshnessFromContract(
    buildDataFreshness({
      lastBarDate: input.lastBarDate,
      queryFailed: input.queryFailed,
      now: input.now,
      thresholdMinutes: input.maxAgeMinutes,
    }),
  );
}

export type MesaOperationalHeaderV1 = {
  regimeHint: string | null;
  /** P&L no realizado agregado en R. */
  portfolioPnLR: number | null;
  /** R en riesgo si stops actuales se ejecutan. */
  portfolioOpenRiskR: number | null;
  /** Cota concurrente stops (`concurrent_stops_v0`); null si cobertura incompleta. ≠ VaR/correlación. */
  portfolioStressRiskR: number | null;
  /** @deprecated Usar portfolioPnLR */
  totalRiskR: number | null;
  portfolioRiskLimitR: number;
  cash: number | null;
  equity: number | null;
  investedPct: number | null;
  operationalStatus: MesaOperationalStatusV1;
  operationalStatusLabel: string;
  operationalPrimaryReason: string | null;
  dataFreshness: MesaDataFreshnessV1;
  dataFreshnessContract: DataFreshnessV1;
  modeLabel: string;
  modeDetail: string;
  brokerVenue: "paper" | "live" | null;
  paperDExecuteEnv: boolean;
  readinessState: string | null;
};

export function buildMesaOperationalHeader(input: {
  regimeHint?: string | null;
  positions?: ReadonlyArray<
    PortfolioPositionRiskInput & {
      marketValue?: number | null;
    }
  >;
  cash?: number | null;
  equity?: number | null;
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  lastBarDate?: string | null;
  /** Sin instrumento de referencia (p. ej. cartera vacía) — no fingir frescura. */
  noFreshnessProbe?: boolean;
  /**
   * Probe parcial (solo 1 de N posiciones) — chip Datos no verde por omisión.
   */
  freshnessPartialSample?: { probed: number; total: number } | null;
  boardQueryFailed?: boolean;
  incidentsQueryFailed?: boolean;
  portfolioQueryFailed?: boolean;
  summaryQueryFailed?: boolean;
  studiesQueryFailed?: boolean;
  killQueryFailed?: boolean;
  selfEvalQueryFailed?: boolean;
  brokerVenue?: "paper" | "live" | null;
  paperDExecuteEnv?: boolean;
  readinessState?: string | null;
  riskTolerance?: string | null;
  maxAcceptableLossPct?: number | null;
  /** F8: cuenta operativa MANUAL/SEMI/AUTO (default SEMI). */
  bookMode?: "manual" | "semi" | "auto" | null;
  /** F8: armado local A3 (`ACTIVAR AUTO`). */
  autoArmed?: boolean | null;
}): MesaOperationalHeaderV1 {
  const equity = input.equity ?? null;
  const cash = input.cash ?? null;
  let investedPct: number | null = null;
  if (equity != null && equity > 0 && cash != null) {
    investedPct = Math.round(((equity - cash) / equity) * 1000) / 10;
  }

  const queryFailed = Boolean(
    input.boardQueryFailed ||
    input.incidentsQueryFailed ||
    input.portfolioQueryFailed ||
    input.summaryQueryFailed ||
    input.studiesQueryFailed ||
    input.killQueryFailed ||
    input.selfEvalQueryFailed,
  );
  const dataFreshnessContract = buildDataFreshness({
    lastBarDate: input.lastBarDate,
    queryFailed,
    noFreshnessProbe: input.noFreshnessProbe === true && !queryFailed,
    partialSample: input.freshnessPartialSample,
  });
  const statusDetail = buildMesaOperationalStatusDetail({
    killSwitchEffective: input.killSwitchEffective,
    incidentCount: input.incidentCount,
    entriesBlocked: input.entriesBlocked,
    vetoed: input.vetoed,
    queryFailed,
    dataFreshnessStatus: dataFreshnessContract.status,
    readinessState: input.readinessState,
    brokerVenue: input.brokerVenue,
  });

  const riskSnapshot = buildPortfolioRiskSnapshot({
    positions: input.positions ?? [],
    riskTolerance: input.riskTolerance,
    maxAcceptableLossPct: input.maxAcceptableLossPct,
  });

  const posture = buildPaperAutoPosture({
    bookMode: input.bookMode,
    autoArmed: input.autoArmed,
    paperDExecuteEnv: input.paperDExecuteEnv,
  });

  return {
    regimeHint: input.regimeHint ?? null,
    portfolioPnLR: riskSnapshot.portfolioPnLR,
    portfolioOpenRiskR: riskSnapshot.portfolioOpenRiskR,
    portfolioStressRiskR: riskSnapshot.portfolioStressRiskR,
    totalRiskR: riskSnapshot.portfolioPnLR,
    portfolioRiskLimitR: riskSnapshot.portfolioRiskLimitR,
    cash,
    equity,
    investedPct,
    operationalStatus: statusDetail.status,
    operationalStatusLabel: statusDetail.statusLabel,
    operationalPrimaryReason: statusDetail.primaryReason,
    dataFreshness: mesaDataFreshnessFromContract(dataFreshnessContract),
    dataFreshnessContract,
    modeLabel: posture.modeLabel,
    modeDetail: posture.modeDetail,
    brokerVenue: input.brokerVenue ?? null,
    paperDExecuteEnv: input.paperDExecuteEnv ?? false,
    readinessState: input.readinessState ?? null,
  };
}

export function mapCandidateNextAction(
  row: {
    status: TradePlanStatusV1;
    study?: DecisionJournalStudyViewV1 | null;
    gate?: string | null;
    inConfirmQueue?: boolean;
    orderPendingFill?: boolean;
  },
  entriesBlocked: boolean,
): MesaNextActionV1 {
  if (row.study) {
    const truth = buildEntryOperatingTruth({
      study: { ...row.study, tradePlanStatus: row.status },
      entriesBlocked,
      gateStatus: row.gate ?? null,
      inConfirmQueue: row.inConfirmQueue,
      orderPendingFill: row.orderPendingFill,
    });
    if (truth) return mesaNextActionFromEntryOperatingTruth(truth);
  }

  if (entriesBlocked) {
    return {
      kind: "none",
      label: "Entradas bloqueadas",
      allowsEntry: false,
    };
  }

  return mapMesaNextAction({
    entriesBlocked,
    tradePlanStatus: row.status,
    hasOperationalPlan: row.study?.hasOperationalPlan ?? false,
  });
}

export function mapPositionNextAction(input: {
  position: {
    operational?: {
      exitPlan?: {
        suggestedAction?: ExitSuggestedActionV1 | string | null;
      } | null;
    } | null;
  };
  protectPlan?: Pick<ProtectPlanV1, "status"> | null;
  study?: Pick<
    DecisionJournalStudyViewV1,
    "tradePlanStatus" | "hasOperationalPlan"
  > | null;
  protectionDiscrepancy?: boolean;
}): MesaNextActionV1 {
  const exit = input.position.operational?.exitPlan?.suggestedAction;
  return mapMesaNextAction({
    exitSuggestedAction:
      exit === "hold" ||
      exit === "protect" ||
      exit === "reduce" ||
      exit === "full_exit"
        ? exit
        : null,
    protectPlan: input.protectPlan,
    tradePlanStatus: input.study?.tradePlanStatus ?? null,
    hasOpenPosition: true,
    hasOperationalPlan: input.study?.hasOperationalPlan ?? false,
    protectionDiscrepancy: input.protectionDiscrepancy,
  });
}
