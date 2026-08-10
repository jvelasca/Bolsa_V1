/**
 * Orquestación pura del ciclo Play (ACK¹ → Lab → Revalidar → Finalistas).
 * Evita bugs de UI (fingerprint que impide reentrar tras ACK, doble Play).
 */

import { coachNeedsHumanAck } from "@/features/backtests/backtest-assistant-full-cycle";
import type { CoachLabAdvanceDecision } from "@/features/backtests/coach-profile-policy";

export type Coach1AdvanceAction =
  | { type: "skip_lab"; reason: string }
  | { type: "wait_ack1"; reason: string }
  | { type: "save_semifinal"; reason: string }
  | { type: "go_lab"; reason: string };

export type Coach1AdvanceInput = {
  gate: CoachLabAdvanceDecision;
  confidence: string | null | undefined;
  requireAckBeforeLab: boolean;
  /** Estado ACK del panel (checkbox / soft-ACK). */
  ackReady: boolean;
  autoAckOnCycle: boolean;
  pauseIfAckNeeded: boolean;
  saveSemifinalSkipLab: boolean;
};

/**
 * ¿El ACK¹/ACK final está satisfecho para seguir?
 * Con Auto-ACK y sin «Pausar», no esperamos al checkbox del panel (evita carrera).
 */
export function isCoach1AckSatisfied(input: {
  needsAck: boolean;
  ackReady: boolean;
  autoAckOnCycle: boolean;
  pauseIfAckNeeded: boolean;
}): boolean {
  if (!input.needsAck) return true;
  if (input.ackReady) return true;
  if (input.autoAckOnCycle && !input.pauseIfAckNeeded) return true;
  return false;
}

/**
 * Política única de ACK (⋯ Asistente ↔ panel Coach).
 * Un solo criterio: no hay checkbox «confirma» distinto del de la config.
 */
export type AssistantAckPolicy = {
  /** Soft-ACK + grabar sin checkbox humano */
  mode: "auto" | "human";
  /** Mostrar checkbox interactivo en Coach (solo modo human) */
  showHumanCheckbox: boolean;
};

export function resolveAssistantAckPolicy(input: {
  autoAckOnCycle: boolean;
  pauseIfAckNeeded: boolean;
}): AssistantAckPolicy {
  const mode: "auto" | "human" =
    input.autoAckOnCycle && !input.pauseIfAckNeeded ? "auto" : "human";
  return {
    mode,
    showHumanCheckbox: mode === "human",
  };
}

/** Decisión Coach¹ → Lab / wait / skip / atajo semifinal. */
export function resolveCoach1AdvanceAction(
  input: Coach1AdvanceInput,
): Coach1AdvanceAction {
  if (!input.gate.advance) {
    return { type: "skip_lab", reason: input.gate.reason };
  }

  const needsAck = coachNeedsHumanAck(input.confidence);
  if (input.requireAckBeforeLab && needsAck) {
    const ok = isCoach1AckSatisfied({
      needsAck: true,
      ackReady: input.ackReady,
      autoAckOnCycle: input.autoAckOnCycle,
      pauseIfAckNeeded: input.pauseIfAckNeeded,
    });
    if (!ok) {
      return {
        type: "wait_ack1",
        reason: input.gate.reason,
      };
    }
  }

  if (input.saveSemifinalSkipLab) {
    return {
      type: "save_semifinal",
      reason: "ACK¹ OK · atajo semifinal (sin Lab)",
    };
  }

  return { type: "go_lab", reason: input.gate.reason };
}

/**
 * ¿Reentrar al efecto Universo→Lab aunque el fingerprint ya se consumió?
 * (ACK¹ pendiente → usuario/soft-ACK marca ack).
 */
export function shouldReenterUniverseToLabChain(opts: {
  fingerprintMatches: boolean;
  pendingAck1: boolean;
  ackSatisfied: boolean;
}): boolean {
  if (!opts.fingerprintMatches) return true;
  return opts.pendingAck1 && opts.ackSatisfied;
}

/** ¿El mensaje de auto-save implica Finalistas escritos? */
export function isFinalistsSavedStatusMessage(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("lab_validated") ||
    m.includes("→ finalistas") ||
    m.includes("mejores lab + coach") ||
    (m.includes("finalistas") && m.includes("ok")) ||
    // ADR-021: TOP experimento F-D (no pisa F-hoy)
    m.includes("f-d guardado") ||
    (m.includes("experimento") && m.includes("día d"))
  );
}

/** ¿Es el atajo semifinal (no Finalistas active)? */
export function isSemifinalShortcutStatusMessage(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("semifinal") || m.includes("lab omitido") || m.includes("atajo")
  );
}

/**
 * Tras Coach²: con ACK satisfecho y mejoras Lab → siempre save_active.
 * (misma regla que resolveFullCycleSaveDecision; helper para tests de secuencia).
 */
export function sequenceExpectsFinalistsSave(opts: {
  postLab: boolean;
  labImprovedCount: number;
  needsAck: boolean;
  ackReady: boolean;
  autoAckOnCycle: boolean;
  pauseIfAckNeeded: boolean;
  recommendationCount: number;
}): { shouldSave: boolean; blockedBy: string | null } {
  if (!opts.postLab) {
    return { shouldSave: false, blockedBy: "not_post_lab" };
  }
  if (opts.labImprovedCount <= 0) {
    return { shouldSave: false, blockedBy: "no_lab_improve" };
  }
  if (opts.recommendationCount <= 0) {
    return { shouldSave: false, blockedBy: "no_candidates" };
  }
  const ackOk = isCoach1AckSatisfied({
    needsAck: opts.needsAck,
    ackReady: opts.ackReady,
    autoAckOnCycle: opts.autoAckOnCycle,
    pauseIfAckNeeded: opts.pauseIfAckNeeded,
  });
  if (!ackOk) {
    return { shouldSave: false, blockedBy: "ack_final" };
  }
  return { shouldSave: true, blockedBy: null };
}
