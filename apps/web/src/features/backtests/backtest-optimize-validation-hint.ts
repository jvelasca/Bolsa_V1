/** Heuristic validation prefill when seeding Optimizar from explore/result (P6). */

export type OptimizeValidationMode = "none" | "holdout" | "walkforward";

export type OptimizeValidationHint = {
  mode: OptimizeValidationMode;
  /** Hold-out fraction when mode=holdout (0–0.5). */
  oosPct?: number;
  /** Expanding WF folds when mode=walkforward (2–5). */
  walkForwardFolds?: number;
  /** Short UI reason (coach + seed banner). */
  reason: string;
};

/** Same floor as panel short-window policy. */
export const VALIDATION_MIN_BARS_HOLDOUT = 250;
/** Prefer WF over a single hold-out cut. */
export const VALIDATION_MIN_BARS_WALKFORWARD = 800;

/**
 * Suggest lab validation from bar count.
 * Explore/result are in-sample only — longer history → stronger default check.
 */
export function suggestOptimizeValidation(
  barLimit?: number | null,
): OptimizeValidationHint {
  const bars =
    barLimit != null && Number.isFinite(barLimit) && barLimit > 0
      ? Math.round(barLimit)
      : 0;

  if (bars < VALIDATION_MIN_BARS_HOLDOUT) {
    return {
      mode: "none",
      reason:
        "Historial corto (<250 barras): acumula datos antes de hold-out/WF; la exploración fue solo in-sample.",
    };
  }

  if (bars < VALIDATION_MIN_BARS_WALKFORWARD) {
    return {
      mode: "holdout",
      oosPct: 0.2,
      reason:
        "Hold-out ~20% al final preactivado: la exploración/prueba origen fue solo in-sample.",
    };
  }

  return {
    mode: "walkforward",
    walkForwardFolds: 3,
    reason:
      "Walk-forward (3 pliegues) preactivado: historial largo; un solo corte OOS no basta.",
  };
}

/** One coach next-step line describing the prefill. */
export function coachValidationNextStep(hint: OptimizeValidationHint): string {
  if (hint.mode === "holdout") {
    return "Optimizar con hold-out ~20% preactivado (validar fuera de la ventana de búsqueda)";
  }
  if (hint.mode === "walkforward") {
    return "Optimizar con walk-forward (3 pliegues) preactivado — más fiable que un solo OOS";
  }
  return "Si optimizas con historial corto, interpreta el grid con cautela (sin OOS/WF aún)";
}
