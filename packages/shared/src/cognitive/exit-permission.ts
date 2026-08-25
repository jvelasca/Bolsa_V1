/**
 * ExitPermission — veto de salida / mutación de stop (ADR-032).
 * Simétrico a check_opening (apertura), distinto de él.
 * ≠ ExitPlan ≠ ExecutionPlan ≠ auto-exit ≠ ExecuteTrade.
 */

import type { ExecutionPlanV1 } from "./execution-plan.js";
import type { ExitPlanV1, ExitSuggestedActionV1 } from "./exit-plan.js";

export type ExitPermissionVerdictV1 = "ALLOW" | "DENY";

export type ExitPermissionReasonV1 =
  | "not_actionable"
  | "position_closed"
  | "kill_switch"
  | "broker_not_allowed"
  | "paper_auto_env_blocked"
  | "execution_blocked"
  | "missing_exit_plan";

export type ExitPermissionActionV1 =
  | "full_exit"
  | "reduce"
  | "protect"
  | "none";

export type ExitPermissionV1 = {
  verdict: ExitPermissionVerdictV1;
  allowed: boolean;
  reasons: ExitPermissionReasonV1[];
  exitPlanId: string | null;
  positionId: string | null;
  action: ExitPermissionActionV1;
  createdAt: string;
};

export type ExitPermissionSignalsV1 = {
  killSwitch?: boolean | null;
  brokerRequested?: boolean | null;
  autoExecute?: boolean | null;
  /** Eco env PAPER_D_EXECUTE; default false. */
  paperDExecute?: boolean | null;
  positionClosed?: boolean | null;
  executionPlan?: ExecutionPlanV1 | null;
  at?: string | null;
};

export const EXIT_PERMISSION_KEY = "exitPermission";

function nowIso(at?: string | null): string {
  if (typeof at === "string" && at.trim()) return at;
  return new Date().toISOString();
}

function resolveAction(exitPlan: ExitPlanV1 | null): ExitPermissionActionV1 {
  if (!exitPlan) return "none";
  if (
    exitPlan.status === "TRIGGERED" &&
    exitPlan.suggestedAction === "full_exit"
  ) {
    return "full_exit";
  }
  if (
    exitPlan.status === "TRIGGERED" &&
    exitPlan.suggestedAction === "reduce"
  ) {
    return "reduce";
  }
  if (exitPlan.status === "ARMED" && exitPlan.suggestedAction === "protect") {
    return "protect";
  }
  return "none";
}

function isActionable(exitPlan: ExitPlanV1): boolean {
  return resolveAction(exitPlan) !== "none";
}

function deny(
  reasons: ExitPermissionReasonV1[],
  exitPlan: ExitPlanV1 | null,
  at?: string | null,
): ExitPermissionV1 {
  return {
    verdict: "DENY",
    allowed: false,
    reasons,
    exitPlanId: exitPlan?.exitPlanId ?? null,
    positionId: exitPlan?.positionId ?? null,
    action: resolveAction(exitPlan),
    createdAt: nowIso(at),
  };
}

/**
 * Gate F5: ¿podemos salir / mutar stop ahora?
 * No ejecuta. No muta planes. Sin ExitPlan → DENY.
 */
export function checkExitPermission(
  exitPlan: ExitPlanV1 | null | undefined,
  signals?: ExitPermissionSignalsV1 | null,
): ExitPermissionV1 {
  const sig = signals ?? {};
  const at = sig.at;

  if (!exitPlan) {
    return deny(["missing_exit_plan"], null, at);
  }

  if (sig.positionClosed === true) {
    return deny(["position_closed"], exitPlan, at);
  }

  if (sig.killSwitch === true) {
    return deny(["kill_switch"], exitPlan, at);
  }

  const exec = sig.executionPlan;
  if (sig.brokerRequested === true) {
    return deny(["broker_not_allowed"], exitPlan, at);
  }
  if (
    exec &&
    (exec.venue === "BROKER" || exec.blockedReason === "broker_not_allowed")
  ) {
    return deny(["broker_not_allowed"], exitPlan, at);
  }

  if (sig.autoExecute === true && sig.paperDExecute !== true) {
    return deny(["paper_auto_env_blocked"], exitPlan, at);
  }

  if (exec && exec.status === "BLOCKED") {
    return deny(["execution_blocked"], exitPlan, at);
  }

  if (!isActionable(exitPlan)) {
    return deny(["not_actionable"], exitPlan, at);
  }

  return {
    verdict: "ALLOW",
    allowed: true,
    reasons: [],
    exitPlanId: exitPlan.exitPlanId,
    positionId: exitPlan.positionId,
    action: resolveAction(exitPlan),
    createdAt: nowIso(at),
  };
}
