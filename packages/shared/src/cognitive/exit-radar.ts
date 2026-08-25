/**
 * Exit Radar advisory (ADR-031 Ciclo 5.2).
 * Read-only: no auto-exit, no muta structuralStop, no check_opening.
 * Priority: exit_hint > time_stop_hint > trail_hint > none.
 */

import type { ConfidenceHint } from "./confidence-state.js";
import type { TradePlanDirectionV1 } from "./trade-plan.js";

export type ExitRadarStatusV1 =
  | "none"
  | "trail_hint"
  | "time_stop_hint"
  | "exit_hint";

export type ExitRadarWhyV1 =
  | "thesis_exit"
  | "beyond_target1"
  | "expired"
  | "mfe_ge_1_5r"
  | "missing_inputs";

export type ExitRadarV1 = {
  status: ExitRadarStatusV1;
  suggestedTrailStop: number | null;
  target1: number | null;
  rMultiple: number | null;
  why: ExitRadarWhyV1[];
};

export type MapExitRadarInput = {
  direction?: TradePlanDirectionV1 | null;
  entry?: number | null;
  structuralStop?: number | null;
  lastClose?: number | null;
  expiresAt?: string | null;
  /** ISO now override for tests; default Date.now() */
  nowIso?: string | null;
  thesisHint?: ConfidenceHint | null;
  /** Precomputed from protectPlan if available */
  target1?: number | null;
  rMultiple?: number | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function isExpired(
  expiresAt: string | null | undefined,
  nowIso?: string | null,
): boolean {
  if (typeof expiresAt !== "string" || expiresAt.length === 0) return false;
  const exp = Date.parse(expiresAt);
  if (!Number.isFinite(exp)) return false;
  const now =
    typeof nowIso === "string" && nowIso.length > 0
      ? Date.parse(nowIso)
      : Date.now();
  if (!Number.isFinite(now)) return false;
  return now >= exp;
}

/**
 * Composes exit/trail/time-stop advisory. Does not execute or mutate stops.
 */
export function mapExitRadar(input: MapExitRadarInput): ExitRadarV1 {
  const direction = input.direction;
  const entry = input.entry;
  const stop = input.structuralStop;
  const lastClose = input.lastClose;
  const why: ExitRadarWhyV1[] = [];

  let rMultiple = finite(input.rMultiple) ? input.rMultiple : null;
  const explicitTarget1 = finite(input.target1) ? input.target1 : null;
  let target1 = explicitTarget1;
  let suggestedTrailStop: number | null = null;

  const hasGeometry =
    (direction === "long" || direction === "short") &&
    finite(entry) &&
    finite(stop);

  if (hasGeometry) {
    const R = Math.abs(entry - stop);
    if (R > 0) {
      const sign = direction === "long" ? 1 : -1;
      if (target1 == null) {
        target1 = entry + sign * R;
      }
      if (rMultiple == null && finite(lastClose)) {
        rMultiple =
          Math.round(((lastClose - entry) / R) * sign * 10000) / 10000;
      }
      if (rMultiple != null && rMultiple >= 1.5) {
        why.push("mfe_ge_1_5r");
        suggestedTrailStop = entry + sign * 0.5 * R;
      }
    }
  }

  const thesisExit =
    input.thesisHint === "exit" || input.thesisHint === "reduce";
  if (thesisExit) why.push("thesis_exit");

  // Beyond T1 only when target1 came from protectPlan (explicit), not default 1R.
  let beyondTarget = false;
  if (
    explicitTarget1 != null &&
    (direction === "long" || direction === "short") &&
    finite(lastClose)
  ) {
    beyondTarget =
      direction === "long"
        ? lastClose >= explicitTarget1
        : lastClose <= explicitTarget1;
    if (beyondTarget) why.push("beyond_target1");
  }

  const expired = isExpired(input.expiresAt, input.nowIso);
  if (expired) why.push("expired");

  if (thesisExit || beyondTarget) {
    return {
      status: "exit_hint",
      suggestedTrailStop,
      target1,
      rMultiple,
      why,
    };
  }
  if (expired) {
    return {
      status: "time_stop_hint",
      suggestedTrailStop,
      target1,
      rMultiple,
      why,
    };
  }
  if (suggestedTrailStop != null) {
    return {
      status: "trail_hint",
      suggestedTrailStop,
      target1,
      rMultiple,
      why,
    };
  }

  if (!hasGeometry && !thesisExit && !expired) {
    why.push("missing_inputs");
  }

  return {
    status: "none",
    suggestedTrailStop: null,
    target1,
    rMultiple,
    why,
  };
}
