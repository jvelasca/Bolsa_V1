/**
 * Embudo Asistente backtesting: 4 pasos (Universo → Coach → Lab → Finalistas).
 * Copy rail 2026-07-28: «Coach: pasar TOP-3 al Lab», «Abrir Lab · #1».
 * @see docs/engineering/research-lifecycle.md § Embudo D
 */

export type AssistantStepId = "universe" | "semifinal" | "lab" | "finalists";

export type AssistantStepDef = {
  id: AssistantStepId;
  n: 1 | 2 | 3 | 4;
  label: string;
  short: string;
};

export const ASSISTANT_STEPS: AssistantStepDef[] = [
  {
    id: "universe",
    n: 1,
    label: "Universo",
    short: "Valor + Probar + coach",
  },
  {
    id: "semifinal",
    n: 2,
    label: "Coach",
    short: "TOP ★ → Lab o Finalistas",
  },
  {
    id: "lab",
    n: 3,
    label: "Lab",
    short: "Pasar / abrir Lab",
  },
  {
    id: "finalists",
    n: 4,
    label: "Finalistas",
    short: "TOP del valor",
  },
];

export type AssistantProgressInput = {
  progress: import("./backtest-assistant-completion.js").AssistantSessionProgress;
  focusOverride: AssistantStepId | null;
};

export function assistantStepIndex(id: AssistantStepId): number {
  return ASSISTANT_STEPS.findIndex((s) => s.id === id);
}
