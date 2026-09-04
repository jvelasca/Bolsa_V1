/**
 * V2.10 — Protect stop source: technical (hint / trail / plan) vs emergency bootstrap.
 * Projection only — not a second FSM. Confirm still signs.
 *
 * Bootstrap −5% is an emergency floor when OPEN_UNPROTECTED has no structural stop.
 * It must NEVER be presented as the strategy / technical stop.
 */

export const BOOTSTRAP_PROTECT_STOP_PCT = 0.05;

/** Where the suggested protect stop came from. */
export type ProtectStopKindV1 = "bootstrap" | "hint" | "trail" | "plan";

export type ResolveBootstrapProtectStopInputV1 = {
  direction?: string | null;
  /** Prefer actual → planned → avgCost → lastPrice. */
  entry: number | null | undefined;
  /** If the plan already carried an initialStop, use it (still bootstrap context). */
  initialStop?: number | null;
};

function finitePositive(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n) && n > 0;
}

/**
 * Raw emergency floor −5 % from entry. Never uses a planned initialStop.
 * Use this to classify an executed stop as emergency vs technical.
 */
export function resolveEmergencyBootstrapStopPrice(input: {
  direction?: string | null;
  entry: number | null | undefined;
}): number | null {
  const entry = finitePositive(input.entry) ? input.entry : null;
  if (entry == null) return null;
  const direction = (input.direction ?? "long").toLowerCase();
  const raw =
    direction === "short"
      ? entry * (1 + BOOTSTRAP_PROTECT_STOP_PCT)
      : entry * (1 - BOOTSTRAP_PROTECT_STOP_PCT);
  return Math.round(raw * 1e4) / 1e4;
}

/**
 * True when the executed/suggested stop is the emergency −5 % floor,
 * not a technical strategy stop.
 */
export function isEmergencyBootstrapStop(input: {
  direction?: string | null;
  entry: number | null | undefined;
  stop: number | null | undefined;
  protectKind?: ProtectStopKindV1 | null;
}): boolean {
  if (input.protectKind === "bootstrap") {
    return finitePositive(input.stop);
  }
  if (
    input.protectKind === "hint" ||
    input.protectKind === "trail" ||
    input.protectKind === "plan"
  ) {
    return false;
  }
  const expected = resolveEmergencyBootstrapStopPrice(input);
  const stop = finitePositive(input.stop) ? input.stop : null;
  if (expected == null || stop == null) return false;
  return Math.abs(stop - expected) <= Math.max(0.01, expected * 0.001);
}

/**
 * Emergency stop for unprotected open positions without ExitPlan/protect_hint stop.
 * LONG → entry × (1 − 5%); SHORT → entry × (1 + 5%).
 */
export function resolveBootstrapProtectStop(
  input: ResolveBootstrapProtectStopInputV1,
): number | null {
  if (finitePositive(input.initialStop)) return input.initialStop;
  return resolveEmergencyBootstrapStopPrice(input);
}

/** Operator-facing copy for Confirm / tooltips. */
export function bootstrapProtectStopLabel(pct = BOOTSTRAP_PROTECT_STOP_PCT): {
  title: string;
  suggestedLine: string;
  disclaimer: string;
} {
  const pctLabel = `−${Math.round(pct * 100)} %`;
  return {
    title: "Posición sin protección",
    suggestedLine: `Stop de emergencia sugerido: ${pctLabel}`,
    disclaimer: "No sustituye al stop técnico. Confirm sigue firmando.",
  };
}
