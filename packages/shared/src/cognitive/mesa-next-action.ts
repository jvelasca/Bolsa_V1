/**
 * Mesa · Hoy — proyección única de CTA (V1.16).
 * La UI no inventa acciones; mapea autoridad del dominio.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import type { ExitSuggestedActionV1 } from "./exit-plan.js";
import type { ProtectPlanV1 } from "./protect-plan.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import type { HoyActionKindV1 } from "./hoy-queue.js";

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
  if (input.protectionDiscrepancy) {
    return {
      kind: "protect",
      label: MESA_NEXT_ACTION_LABELS.protect,
      allowsEntry: false,
    };
  }

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

/** Suma R de posiciones abiertas cuando el dato existe. */
export function sumPortfolioUnrealizedR(
  positions: ReadonlyArray<{
    operational?: { unrealizedR?: number | null } | null;
  }>,
): number | null {
  let sum = 0;
  let any = false;
  for (const p of positions) {
    const r = p.operational?.unrealizedR;
    if (r != null && Number.isFinite(r)) {
      sum += r;
      any = true;
    }
  }
  return any ? Math.round(sum * 100) / 100 : null;
}

export type MesaOperationalStatusV1 = "normal" | "attention" | "blocked";

export function deriveMesaOperationalStatus(input: {
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  queryFailed?: boolean;
}): MesaOperationalStatusV1 {
  if (input.queryFailed) return "attention";
  if (input.killSwitchEffective) return "blocked";
  if ((input.incidentCount ?? 0) > 0) return "blocked";
  if (input.entriesBlocked || (input.vetoed ?? 0) > 0) return "attention";
  return "normal";
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
  if (input.queryFailed) {
    return { state: "error", label: "No consultado" };
  }
  const raw = input.lastBarDate?.trim();
  if (!raw) {
    return { state: "unknown", label: "—" };
  }
  const ts = new Date(raw);
  if (Number.isNaN(ts.getTime())) {
    return { state: "unknown", label: "—" };
  }
  const now = input.now ?? new Date();
  const ageMinutes = Math.max(
    0,
    Math.floor((now.getTime() - ts.getTime()) / 60_000),
  );
  const max = input.maxAgeMinutes ?? 5 * 24 * 60;
  if (ageMinutes > max) {
    return {
      state: "stale",
      label: `Retrasados · ${formatAge(ageMinutes)}`,
      ageMinutes,
    };
  }
  return {
    state: "fresh",
    label: `Actualizados · ${formatAge(ageMinutes)}`,
    ageMinutes,
  };
}

function formatAge(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 48) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

export type MesaOperationalHeaderV1 = {
  regimeHint: string | null;
  totalRiskR: number | null;
  cash: number | null;
  equity: number | null;
  investedPct: number | null;
  operationalStatus: MesaOperationalStatusV1;
  operationalStatusLabel: string;
  dataFreshness: MesaDataFreshnessV1;
  modeLabel: string;
  modeDetail: string;
  brokerVenue: "paper" | "live" | null;
  paperDExecuteEnv: boolean;
  readinessState: string | null;
};

const OPERATIONAL_STATUS_LABEL: Record<MesaOperationalStatusV1, string> = {
  normal: "Normal",
  attention: "Atención",
  blocked: "Bloqueado",
};

export function buildMesaOperationalHeader(input: {
  regimeHint?: string | null;
  positions?: ReadonlyArray<{
    marketValue?: number | null;
    operational?: { unrealizedR?: number | null } | null;
  }>;
  cash?: number | null;
  equity?: number | null;
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  lastBarDate?: string | null;
  boardQueryFailed?: boolean;
  incidentsQueryFailed?: boolean;
  brokerVenue?: "paper" | "live" | null;
  paperDExecuteEnv?: boolean;
  readinessState?: string | null;
}): MesaOperationalHeaderV1 {
  const equity = input.equity ?? null;
  const cash = input.cash ?? null;
  let investedPct: number | null = null;
  if (equity != null && equity > 0 && cash != null) {
    investedPct = Math.round(((equity - cash) / equity) * 1000) / 10;
  }

  const queryFailed = Boolean(
    input.boardQueryFailed || input.incidentsQueryFailed,
  );
  const operationalStatus = deriveMesaOperationalStatus({
    killSwitchEffective: input.killSwitchEffective,
    incidentCount: input.incidentCount,
    entriesBlocked: input.entriesBlocked,
    vetoed: input.vetoed,
    queryFailed,
  });

  return {
    regimeHint: input.regimeHint ?? null,
    totalRiskR: sumPortfolioUnrealizedR(input.positions ?? []),
    cash,
    equity,
    investedPct,
    operationalStatus,
    operationalStatusLabel: OPERATIONAL_STATUS_LABEL[operationalStatus],
    dataFreshness: deriveMesaDataFreshness({
      lastBarDate: input.lastBarDate,
      queryFailed,
    }),
    modeLabel: "SEMI",
    modeDetail: "IA propone · humano firma · AUTO off",
    brokerVenue: input.brokerVenue ?? null,
    paperDExecuteEnv: input.paperDExecuteEnv ?? false,
    readinessState: input.readinessState ?? null,
  };
}

export function mapCandidateNextAction(
  row: {
    status: TradePlanStatusV1;
    study?: Pick<DecisionJournalStudyViewV1, "hasOperationalPlan"> | null;
  },
  entriesBlocked: boolean,
): MesaNextActionV1 {
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
