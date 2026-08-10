/** Plan legible de lo que hará un paso del asistente (antes del OK). */

import type { AssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";
import type { AssistantStepId } from "@/features/backtests/backtest-assistant-steps";
import { ASSISTANT_STEPS } from "@/features/backtests/backtest-assistant-steps";
import {
  assistantStepOrdinal,
  canAutoRunStep,
  type AssistantSessionProgress,
} from "@/features/backtests/backtest-assistant-completion";

export type AssistantConfirmPlan = {
  step: AssistantStepId;
  title: string;
  bullets: string[];
  canExecute: boolean;
  blockedReason?: string;
  source: "click" | "advance";
};

export function buildAssistantStepPlan(
  step: AssistantStepId,
  prefs: AssistantPrefs,
  progress: AssistantSessionProgress,
  hasInstrument: boolean,
  source: "click" | "advance" = "click",
): AssistantConfirmPlan {
  const def = ASSISTANT_STEPS.find((s) => s.id === step);
  const label = def?.label ?? step;
  const ordinal = assistantStepOrdinal(step);
  const canExecute = canAutoRunStep(step, progress, hasInstrument);
  const bullets: string[] = [];

  if (step === "universe") {
    bullets.push("Paso 1/4 — Universo: elegir valor y lanzar exploración AT");
    if (prefs.universe.selectAllGenerics)
      bullets.push("Marcar todas las genéricas en la matriz");
    if (prefs.universe.includeOptimizedStrategies) {
      bullets.push("Incluir Optimizadas en el lote (tope matriz)");
    }
    if (prefs.universe.includeMineStrategies) {
      bullets.push("Incluir Mis estrategias en el lote (tope matriz)");
    }
    if (prefs.universe.runCoachOnEnter) {
      bullets.push(
        prefs.universe.reuseLoteIfUnchanged
          ? "Ejecutar «Probar + coach» (reutiliza lote si no cambió)"
          : "Ejecutar «Probar + coach» (siempre re-simula)",
      );
    } else {
      bullets.push("Sin ejecución automática (activa Probar + coach en …)");
    }
    if (prefs.universe.autoAdvanceWhenDone) {
      bullets.push("Al terminar → te pedirá OK para Semifinal (paso 2)");
    }
  } else if (step === "semifinal") {
    bullets.push("Paso 2/4 — Semifinal: TOP-3 del coach → laboratorio");
    if (prefs.semifinal.optimizeTop3OnEnter) {
      bullets.push(
        "Encolar optimización de las 3 candidatas (hold-out/WF según barras)",
      );
    } else {
      bullets.push(
        "Solo revisar coach (sin encolar lab; marca el paso al confirmar)",
      );
    }
    if (prefs.semifinal.autoAdvanceWhenDone) {
      bullets.push("Al terminar → te pedirá OK para Laboratorio (paso 3)");
    }
  } else if (step === "lab") {
    bullets.push(
      "Paso 3/4 — Laboratorio: adoptar Mejor solo si ≥ ancla (OOS/WF)",
    );
    bullets.push("Abrir pestaña Optimizar con la semilla / jobs");
    if (prefs.lab.autoAdvanceWhenActiveTop) {
      bullets.push(
        "Cuando el TOP pase a active → te pedirá OK para Finalistas (paso 4)",
      );
    } else {
      bullets.push("Luego pulsa Finalistas manualmente");
    }
  } else {
    bullets.push(
      "Paso 4/4 — Finalistas: Mis estrategias filtradas por TOP del valor",
    );
    if (prefs.finalists.revalidateCoachOnEnter) {
      bullets.push("Revalidar con «Probar + coach»");
    } else {
      bullets.push("Revisar finalistas guardados (sin re-lanzar coach)");
    }
  }

  return {
    step,
    title:
      source === "advance"
        ? `Siguiente · ${ordinal} ${label}`
        : `${ordinal} ${label}`,
    bullets,
    canExecute,
    blockedReason: canExecute
      ? undefined
      : step === "universe"
        ? "Elige un valor antes del paso 1."
        : `Completa el paso anterior (✓) antes del ${ordinal}.`,
    source,
  };
}
