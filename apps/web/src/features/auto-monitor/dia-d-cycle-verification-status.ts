/**
 * P2 — tri-estado de la verificación DÍA-D de un ciclo (puro, testeable).
 *
 * Un ciclo SOLO se rotula «Verificación vinculada» si existe un registro durable que lo
 * enlaza; sin registro es «Sin verificación»; si el ciclo no declara `cycleId` (o no se
 * pudo comprobar) se declara «Sin dato todavía» (nunca se finge ausencia).
 */

export type DiaDCycleVerificationState = "linked" | "not-verified" | "unknown";

export const DIA_D_CYCLE_VERIFICATION_LABELS: Record<
  DiaDCycleVerificationState,
  string
> = {
  linked: "Verificación vinculada",
  "not-verified": "Sin verificación",
  unknown: "Sin dato todavía",
};

export function resolveDiaDCycleVerificationState(input: {
  cycleId?: string | null;
  verified: boolean;
}): DiaDCycleVerificationState {
  if (!input.cycleId?.trim()) return "unknown";
  return input.verified ? "linked" : "not-verified";
}
