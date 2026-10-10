/**
 * Cuatro cifras de cuenta bajo las seis preguntas.
 *
 * Copia el resumen de cuenta ya producido. No recalcula posición, caja ni P&L.
 * Un resumen ausente es «Sin dato todavía», nunca `0`.
 *
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §3 §4
 */

import { formatPrice } from "@/features/charts/chart-utils";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";

export type AutoAccountSummaryFacts = {
  positionsCount: number;
  cash: number;
  totalUnrealizedPnl: number;
  /**
   * F4 — P&L realizado AGREGADO de todo el historial (base canónica tax report).
   * `null`/ausente = no medido → «Sin dato todavía», NUNCA 0 fabricado.
   */
  totalRealizedPnl?: number | null;
};

export type AutoAccountFigureId =
  | "position"
  | "pnl"
  | "realized"
  | "cash"
  | "risk";

export type AutoAccountFigure = {
  id: AutoAccountFigureId;
  label: string;
  value: string;
};

// H4 (v2.88.106): el RÓTULO dice QUÉ es el resultado (abierto vs cerrado) y el VALOR
// lleva la cifra con el calificador de cuenta simulada, para no mezclar SIM/dinero real.
export const AUTO_ACCOUNT_OPEN_PNL_LABEL = "Resultado de posiciones abiertas";
export const AUTO_ACCOUNT_CLOSED_PNL_LABEL =
  "Resultado de operaciones cerradas";
export const AUTO_ACCOUNT_CASH_LABEL = "Efectivo simulado";

function positionLabel(count: number): string {
  const noun = count === 1 ? "posición" : "posiciones";
  return `${count} ${noun} en la cuenta simulada`;
}

function accountScopeAmount(amount: number): string {
  return `${formatPrice(amount, "EUR")} en la cuenta simulada`;
}

export function buildAutoAccountFigures(input: {
  summary: AutoAccountSummaryFacts | null;
  riskLabel: string;
}): AutoAccountFigure[] {
  const summary = input.summary;
  const position =
    summary == null
      ? AUTO_HOME_NO_DATA_LABEL
      : positionLabel(summary.positionsCount);
  const pnl =
    summary == null
      ? AUTO_HOME_NO_DATA_LABEL
      : accountScopeAmount(summary.totalUnrealizedPnl);
  // F4: realizado agregado. `null`/ausente es un hueco declarado, nunca 0.
  const realized =
    summary == null || summary.totalRealizedPnl == null
      ? AUTO_HOME_NO_DATA_LABEL
      : accountScopeAmount(summary.totalRealizedPnl);
  const cash =
    summary == null
      ? AUTO_HOME_NO_DATA_LABEL
      : formatPrice(summary.cash, "EUR");

  return [
    { id: "position", label: "Posición", value: position },
    { id: "pnl", label: AUTO_ACCOUNT_OPEN_PNL_LABEL, value: pnl },
    { id: "realized", label: AUTO_ACCOUNT_CLOSED_PNL_LABEL, value: realized },
    { id: "cash", label: AUTO_ACCOUNT_CASH_LABEL, value: cash },
    { id: "risk", label: "Riesgo", value: input.riskLabel },
  ];
}
