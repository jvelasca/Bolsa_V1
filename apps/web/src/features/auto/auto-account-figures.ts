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
};

export type AutoAccountFigureId = "position" | "pnl" | "cash" | "risk";

export type AutoAccountFigure = {
  id: AutoAccountFigureId;
  label: string;
  value: string;
};

function positionLabel(count: number): string {
  const noun = count === 1 ? "posición" : "posiciones";
  return `${count} ${noun} en la cuenta simulada`;
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
      : `Resultado de la cuenta ${formatPrice(summary.totalUnrealizedPnl, "EUR")}`;
  const cash =
    summary == null
      ? AUTO_HOME_NO_DATA_LABEL
      : formatPrice(summary.cash, "EUR");

  return [
    { id: "position", label: "Posición", value: position },
    { id: "pnl", label: "Resultado", value: pnl },
    { id: "cash", label: "Efectivo simulado", value: cash },
    { id: "risk", label: "Riesgo", value: input.riskLabel },
  ];
}
