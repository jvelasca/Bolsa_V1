/**
 * Unified Alert Inbox — Market / Decision / Position / Risk / System.
 */

import type { MesaDecisionAlertV1 } from "./decision-journal-relevant-delta.js";
import { buildMesaDecisionAlerts } from "./decision-journal-relevant-delta.js";
import type { OperationalPriorityV1 } from "./operational-priority.js";
import type { PortfolioScenarioV1 } from "./portfolio-scenario.js";
import type { InvestmentPositionAggregateV1 } from "./investment-position-aggregate.js";

export type UnifiedAlertKindV1 =
  | "MARKET"
  | "DECISION"
  | "POSITION"
  | "RISK"
  | "SYSTEM";

export type UnifiedAlertV1 = {
  kind: UnifiedAlertKindV1;
  symbol: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  checklist?: ReadonlyArray<{ label: string; status: "ok" | "warn" | "bad" }>;
  ctaLabel?: string | null;
};

function mapLegacyKind(kind: MesaDecisionAlertV1["kind"]): UnifiedAlertKindV1 {
  if (kind === "incident" || kind === "data_stale") return "SYSTEM";
  if (
    kind === "protection_discrepancy" ||
    kind === "stop_near" ||
    kind === "tp1_reached"
  ) {
    return "POSITION";
  }
  return "DECISION";
}

export function unifiedAlertsFromDecisionAlerts(
  alerts: MesaDecisionAlertV1[],
): UnifiedAlertV1[] {
  return alerts.map((a) => ({
    kind: mapLegacyKind(a.kind),
    symbol: a.symbol,
    title: a.kind.replace(/_/g, " ").toUpperCase(),
    message: a.message,
    severity: a.severity,
  }));
}

export function buildTriggerReadyAlert(input: {
  symbol: string;
  priority: OperationalPriorityV1;
  scenario?: PortfolioScenarioV1 | null;
}): UnifiedAlertV1 | null {
  if (input.priority.verdict !== "OPERABLE") return null;

  const checklist = [
    { label: "Tesis", status: "ok" as const },
    { label: "Plan", status: "ok" as const },
    {
      label: "Riesgo",
      status:
        input.scenario?.after.openRiskR != null &&
        input.scenario.after.openRiskR > (input.scenario.riskLimitR ?? 5)
          ? ("warn" as const)
          : ("ok" as const),
    },
    {
      label: "Mandato",
      status:
        input.scenario?.after.mandateFit === "VETO"
          ? ("bad" as const)
          : ("ok" as const),
    },
    {
      label: "Portfolio",
      status:
        input.priority.suitability.value < 50
          ? ("warn" as const)
          : ("ok" as const),
    },
    { label: "Datos", status: "ok" as const },
  ];

  return {
    kind: "DECISION",
    symbol: input.symbol,
    title: "TRIGGER DE ENTRADA ALCANZADO",
    message: "Lista para revisión de propuesta",
    severity: "info",
    checklist,
    ctaLabel: "VER PROPUESTA",
  };
}

export function buildPositionManagementAlert(
  aggregate: InvestmentPositionAggregateV1,
): UnifiedAlertV1 | null {
  const action = aggregate.nextAction.kind;
  if (action === "maintain" || action === "watch" || action === "none") {
    return null;
  }

  return {
    kind: "POSITION",
    symbol: aggregate.symbol,
    title: aggregate.nextAction.label.toUpperCase(),
    message: `Posición requiere: ${aggregate.nextAction.label}`,
    severity:
      action === "exit" || aggregate.currentState.protectionDiscrepancy
        ? "critical"
        : "warning",
  };
}

export type BuildUnifiedAlertInboxInput = {
  decisionAlerts?: MesaDecisionAlertV1[];
  positionAggregates?: InvestmentPositionAggregateV1[];
  triggeredPriorities?: Array<{
    symbol: string;
    priority: OperationalPriorityV1;
    scenario?: PortfolioScenarioV1 | null;
  }>;
  portfolioRiskWarnings?: string[];
};

export function buildUnifiedAlertInbox(
  input: BuildUnifiedAlertInboxInput,
): UnifiedAlertV1[] {
  const out: UnifiedAlertV1[] = [];

  out.push(...unifiedAlertsFromDecisionAlerts(input.decisionAlerts ?? []));

  for (const agg of input.positionAggregates ?? []) {
    const alert = buildPositionManagementAlert(agg);
    if (alert) out.push(alert);
  }

  for (const t of input.triggeredPriorities ?? []) {
    const alert = buildTriggerReadyAlert(t);
    if (alert) out.push(alert);
  }

  for (const msg of input.portfolioRiskWarnings ?? []) {
    out.push({
      kind: "RISK",
      symbol: "CARTERA",
      title: "RIESGO CARTERA",
      message: msg,
      severity: "warning",
    });
  }

  const severityOrder = { critical: 0, warning: 1, info: 2 };
  return out.sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity],
  );
}

export { buildMesaDecisionAlerts };
