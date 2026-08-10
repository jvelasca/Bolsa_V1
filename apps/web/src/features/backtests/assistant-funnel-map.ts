/**
 * Mapa visual del embudo Asistente (5 etapas de producto).
 *
 * 1 Probar → 2 Coach → 3 Lab → 4 Revalidar (Coach²) → 5 Finalistas
 * Los ids de rail/navegación siguen siendo 4 (`AssistantStepId`);
 * esta capa solo clarifica Coach¹ vs Coach² y el guardado.
 *
 * @see docs/engineering/research-lifecycle.md § Embudo D
 */

import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import type { AssistantSessionProgress } from "@/features/backtests/backtest-assistant-completion";

export type FunnelStageId =
  | "probe"
  | "coach1"
  | "lab"
  | "revalidate"
  | "finalists";

export type FunnelStageDef = {
  id: FunnelStageId;
  n: 1 | 2 | 3 | 4 | 5;
  label: string;
  /** Texto corto para (⋯) / tooltips */
  blurb: string;
  /** Paso de rail al que navega el clic */
  navStep: AssistantStepId;
};

export const FUNNEL_STAGES: FunnelStageDef[] = [
  {
    id: "probe",
    n: 1,
    label: "Probar",
    blurb: "Probar genéricas (± Mis / Finalistas del valor).",
    navStep: "universe",
  },
  {
    id: "coach1",
    n: 2,
    label: "Coach",
    blurb: "Analiza ★. ACK¹ si hace falta → Lab (o atajo semifinal).",
    navStep: "semifinal",
  },
  {
    id: "lab",
    n: 3,
    label: "Lab",
    blurb: "Si mejoran → Revalidar. Si no → no grabar (Finalistas intactos).",
    navStep: "lab",
  },
  {
    id: "revalidate",
    n: 4,
    label: "Revalidar",
    blurb: "Coach² + ACK final → grabar Finalistas o descartar.",
    navStep: "semifinal",
  },
  {
    id: "finalists",
    n: 5,
    label: "Finalistas",
    blurb:
      "TOP active lab_validated si el ACK final y la política lo permiten.",
    navStep: "finalists",
  },
];

export type FunnelStageStatus =
  | "pending"
  | "active"
  | "done"
  | "skipped"
  | "blocked";

export type ResolveFunnelStageInput = {
  progress: AssistantSessionProgress;
  coachPass: "initial" | "post_lab";
  fullCycleActive: boolean;
  /** Ciclo parado esperando ACK humano en Coach² */
  awaitingAck?: boolean;
  /** TOP escrito en esta pasada */
  finalistsSaved?: boolean;
  /** Fase Finalistas cerrada sin guardar (skip) */
  finalistsSkipped?: boolean;
};

/** Etapa activa del mapa (para resaltar). */
export function resolveActiveFunnelStage(
  input: ResolveFunnelStageInput,
): FunnelStageId {
  const {
    progress,
    coachPass,
    fullCycleActive,
    awaitingAck,
    finalistsSaved,
    finalistsSkipped,
  } = input;

  if (finalistsSaved || finalistsSkipped) return "finalists";
  if (awaitingAck) {
    return coachPass === "post_lab" ? "revalidate" : "coach1";
  }
  if (fullCycleActive && coachPass === "post_lab") {
    return "revalidate";
  }
  if (!progress.universeDone) return "probe";
  if (!progress.semifinalDone && coachPass === "initial") return "coach1";
  if (!progress.labDone) {
    // Universo hecho, aún en Coach¹ o entrando a Lab
    if (progress.semifinalDone) return "lab";
    return "coach1";
  }
  if (coachPass === "post_lab") return "revalidate";
  if (progress.semifinalDone && !progress.labDone) return "lab";
  if (progress.universeDone && !progress.semifinalDone) return "coach1";
  return "finalists";
}

/** Estado visual de cada etapa. */
export function resolveFunnelStageStatus(
  stageId: FunnelStageId,
  input: ResolveFunnelStageInput,
): FunnelStageStatus {
  const active = resolveActiveFunnelStage(input);
  const { progress, coachPass, awaitingAck, finalistsSaved, finalistsSkipped } =
    input;

  if (stageId === active) {
    // Terminal: no dejar Finalistas en «En curso» tras guardar/omitir
    if (stageId === "finalists") {
      if (finalistsSaved) return "done";
      if (finalistsSkipped) return "skipped";
    }
    if (awaitingAck && (stageId === "revalidate" || stageId === "coach1")) {
      return "blocked";
    }
    return "active";
  }

  switch (stageId) {
    case "probe":
      return progress.universeDone ? "done" : "pending";
    case "coach1":
      if (!progress.universeDone) return "pending";
      if (progress.semifinalDone || coachPass === "post_lab") return "done";
      return "pending";
    case "lab":
      if (!progress.semifinalDone && coachPass !== "post_lab") return "pending";
      if (progress.labDone || coachPass === "post_lab") return "done";
      return "pending";
    case "revalidate":
      if (coachPass !== "post_lab" && !finalistsSaved && !finalistsSkipped) {
        return progress.labDone ? "pending" : "pending";
      }
      if (finalistsSaved || finalistsSkipped) return "done";
      if (coachPass === "post_lab") return "pending";
      return "pending";
    case "finalists":
      if (finalistsSaved) return "done";
      if (finalistsSkipped) return "skipped";
      return "pending";
    default:
      return "pending";
  }
}

export function funnelStageStatusLabel(status: FunnelStageStatus): string {
  switch (status) {
    case "active":
      return "En curso";
    case "done":
      return "Hecho";
    case "skipped":
      return "Omitido";
    case "blocked":
      return "Falta ACK";
    default:
      return "Pendiente";
  }
}

/** Leyenda compacta para el menú (⋯). */
export function funnelPrefsLegend(): string {
  return FUNNEL_STAGES.map((s) => `${s.n}. ${s.label}`).join(" → ");
}
