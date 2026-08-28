/**
 * ExitPolicy — fracciones de gestión T1/T2 por plantilla de TradingPolicy.
 * V1.27: no es un motor de salida nuevo; parametriza ExitPlan.suggested*.
 * Perfiles: conservative / moderate / aggressive_swing (sin triada paralela).
 */

export type ExitTrailWidthV1 = "tight" | "medium" | "wide";

export type ExitPolicyV1 = {
  t1ReduceFraction: number;
  t2ReduceFraction: number;
  trailWidth: ExitTrailWidthV1;
};

export const CONSERVATIVE_EXIT_POLICY: ExitPolicyV1 = {
  t1ReduceFraction: 0.5,
  t2ReduceFraction: 1,
  trailWidth: "tight",
};

export const MODERATE_EXIT_POLICY: ExitPolicyV1 = {
  t1ReduceFraction: 0.3,
  t2ReduceFraction: 0.3,
  trailWidth: "medium",
};

export const AGGRESSIVE_SWING_EXIT_POLICY: ExitPolicyV1 = {
  t1ReduceFraction: 0,
  t2ReduceFraction: 0.3,
  trailWidth: "wide",
};

export const EXIT_POLICY_BY_TEMPLATE: Record<
  "conservative" | "moderate" | "aggressive_swing",
  ExitPolicyV1
> = {
  conservative: CONSERVATIVE_EXIT_POLICY,
  moderate: MODERATE_EXIT_POLICY,
  aggressive_swing: AGGRESSIVE_SWING_EXIT_POLICY,
};

export function resolveExitPolicy(
  templateId: string | null | undefined,
): ExitPolicyV1 {
  if (templateId === "conservative") return CONSERVATIVE_EXIT_POLICY;
  if (templateId === "aggressive_swing") return AGGRESSIVE_SWING_EXIT_POLICY;
  return MODERATE_EXIT_POLICY;
}

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

export function clampExitFraction(n: number): number {
  if (!finite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

export function qtyFromExitFraction(
  remaining: number,
  fraction: number,
): number {
  if (!finite(remaining) || remaining <= 0) return 0;
  const f = clampExitFraction(fraction);
  if (f <= 1e-12) return 0;
  if (f >= 1 - 1e-12) return round4(remaining);
  return round4(remaining * f);
}

export type ExitPolicySuggestionV1 = {
  suggestedAction: "hold" | "protect" | "reduce" | "full_exit";
  suggestedQty: number | null;
  suggestedStop: number | null;
};

/**
 * Aplica política a un evento ya elegido (primary). Sin política: T1 = mitad (legado F3).
 */
export function suggestionFromExitPolicy(
  primary: string | null,
  remaining: number,
  policy: ExitPolicyV1 | null | undefined,
  trailStop?: number | null,
): ExitPolicySuggestionV1 {
  if (!primary) {
    return { suggestedAction: "hold", suggestedQty: null, suggestedStop: null };
  }
  if (primary === "TRAIL") {
    const stop = finite(trailStop) && trailStop > 0 ? round4(trailStop) : null;
    return {
      suggestedAction: "protect",
      suggestedQty: null,
      suggestedStop: stop,
    };
  }
  if (primary === "TARGET_1") {
    const fraction = policy ? clampExitFraction(policy.t1ReduceFraction) : 0.5;
    const qty = qtyFromExitFraction(remaining, fraction);
    if (qty <= 0) {
      return {
        suggestedAction: "hold",
        suggestedQty: null,
        suggestedStop: null,
      };
    }
    if (qty >= remaining - 1e-9) {
      return {
        suggestedAction: "full_exit",
        suggestedQty: round4(remaining),
        suggestedStop: null,
      };
    }
    return {
      suggestedAction: "reduce",
      suggestedQty: qty,
      suggestedStop: null,
    };
  }
  if (primary === "TARGET_2") {
    const fraction = policy ? clampExitFraction(policy.t2ReduceFraction) : 1;
    const qty = qtyFromExitFraction(remaining, fraction);
    if (qty <= 0) {
      return {
        suggestedAction: "hold",
        suggestedQty: null,
        suggestedStop: null,
      };
    }
    if (qty >= remaining - 1e-9) {
      return {
        suggestedAction: "full_exit",
        suggestedQty: round4(remaining),
        suggestedStop: null,
      };
    }
    return {
      suggestedAction: "reduce",
      suggestedQty: qty,
      suggestedStop: null,
    };
  }
  return {
    suggestedAction: "full_exit",
    suggestedQty: round4(remaining),
    suggestedStop: null,
  };
}
