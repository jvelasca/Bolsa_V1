/**
 * Progreso del embudo Asistente (sesión).
 * Los ✓ NO dependen del TOP antiguo en BD: solo de lo hecho en esta pasada.
 */

import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import {
  ASSISTANT_STEPS,
  assistantStepIndex,
} from "@/features/backtests/backtest-assistant-steps";

export type AssistantSessionProgress = {
  /** 1 Universo: batería/coach terminó OK. */
  universeDone: boolean;
  /** 2 Semifinal: lab de las 3 encolado (o OK sin optimizar). */
  semifinalDone: boolean;
  /** 3 Lab: TOP promovido a active en esta pasada (o OK lab sin auto-avance). */
  labDone: boolean;
  /** 4/5 Finalistas: fase visitada / ciclo cerrado. */
  finalistsDone: boolean;
  /** TOP escrito en BD en esta pasada (verde en mapa). */
  finalistsSaved: boolean;
  /** Ciclo cerró Finalistas sin escribir (ámbar / omitido). */
  finalistsSkipped: boolean;
};

export function emptyAssistantProgress(): AssistantSessionProgress {
  return {
    universeDone: false,
    semifinalDone: false,
    labDone: false,
    finalistsDone: false,
    finalistsSaved: false,
    finalistsSkipped: false,
  };
}

export function isAssistantStepComplete(
  step: AssistantStepId,
  progress: AssistantSessionProgress,
): boolean {
  switch (step) {
    case "universe":
      return progress.universeDone;
    case "semifinal":
      return progress.semifinalDone;
    case "lab":
      return progress.labDone;
    case "finalists":
      return progress.finalistsDone;
    default:
      return false;
  }
}

/** Puede pedir OK / ejecutar este paso (el anterior debe estar ✓). */
export function canAutoRunStep(
  step: AssistantStepId,
  progress: AssistantSessionProgress,
  hasInstrument: boolean,
): boolean {
  if (step === "universe") return hasInstrument;
  const idx = assistantStepIndex(step);
  for (let i = 0; i < idx; i++) {
    const prev = ASSISTANT_STEPS[i]?.id;
    if (!prev || !isAssistantStepComplete(prev, progress)) return false;
  }
  return true;
}

/**
 * Snapshot para encadenar Universo → Coach/Lab en el mismo tick.
 * `setAssistantProgress({ universeDone: true })` es async: si `canAutoRunStep`
 * lee el state React todavía en false, semifinal aborta y el fingerprint del
 * chain impide reintento → el usuario necesita un 2º Play.
 */
export function withUniverseDone(
  progress: AssistantSessionProgress,
): AssistantSessionProgress {
  return { ...progress, universeDone: true };
}

/**
 * Paso activo del rail: el primero incompleto, salvo override (p. ej. confirm abierto).
 */
export function resolveAssistantActiveStep(
  progress: AssistantSessionProgress,
  focusOverride: AssistantStepId | null,
): AssistantStepId {
  if (focusOverride) return focusOverride;
  if (!progress.universeDone) return "universe";
  if (!progress.semifinalDone) return "semifinal";
  if (!progress.labDone) return "lab";
  return "finalists";
}

export function assistantStepLabel(step: AssistantStepId): string {
  return ASSISTANT_STEPS.find((s) => s.id === step)?.label ?? step;
}

export function assistantStepOrdinal(step: AssistantStepId): string {
  const def = ASSISTANT_STEPS.find((s) => s.id === step);
  return def ? `${def.n}/4` : "";
}
