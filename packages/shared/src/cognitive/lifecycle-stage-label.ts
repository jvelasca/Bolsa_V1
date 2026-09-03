/**
 * V1.90 — Lifecycle stage → mesa operational vocabulary.
 * Machine stage stays in data attributes; UI shows human labels.
 */

export type LifecycleStageMachineV1 =
  | "clean"
  | "candidate"
  | "open"
  | "t1_ready"
  | "t1_executed"
  | "trailing"
  | "exit_required"
  | "t2_ready"
  | "t2_executed"
  | "closed"
  | string;

export const LIFECYCLE_STAGE_LABELS: Record<string, string> = {
  clean: "Limpia",
  candidate: "Candidata",
  open: "Abierta",
  t1_ready: "T1 preparado",
  t1_executed: "T1 ejecutado",
  trailing: "Protegiendo",
  exit_required: "Salida requerida",
  t2_ready: "T2 preparado",
  t2_executed: "T2 ejecutado",
  closed: "Cerrada",
};

export function lifecycleStageLabel(
  stage: string | null | undefined,
): string | null {
  if (!stage || stage === "candidate") return null;
  return LIFECYCLE_STAGE_LABELS[stage] ?? stage;
}
