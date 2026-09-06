/**
 * Narrativa «Para ti (por qué)» desde datos Confirm existentes.
 * No inventa motor de decisión ni PASS; huecos honestos.
 */

import {
  THESIS_DIRECTION_LABELS,
  TRADE_PLAN_WHY_NOT_LABELS,
  type DecisionAction,
  type TradePlanV1,
  type TradePlanWhyNotV1,
  type WeightContextV1,
} from "@bolsa/shared";
import type { F3TicketPreviewView } from "@/features/trading/f3-ticket-preview";

export type LiveVirtualWhyBlock = {
  id: "valor" | "tamano" | "orden" | "anti";
  title: string;
  bullets: string[];
};

function directionLabel(action: unknown): string | null {
  const a = String(action ?? "").trim() as DecisionAction;
  if (a in THESIS_DIRECTION_LABELS) {
    return THESIS_DIRECTION_LABELS[a as DecisionAction];
  }
  return null;
}

function whyNotLabels(whyNot: TradePlanWhyNotV1[] | undefined): string[] {
  if (!whyNot?.length) return [];
  return whyNot.map((code) => TRADE_PLAN_WHY_NOT_LABELS[code] ?? String(code));
}

/**
 * Construye bloques Por qué reutilizando TradePlan / weights / ticket / fase.
 */
export function buildLiveVirtualWhyBlocks(input: {
  action?: unknown;
  weightContext?: WeightContextV1 | null;
  tradePlan?: TradePlanV1 | null;
  ticket?: F3TicketPreviewView | null;
  stop?: number | null;
  riskPct?: number | null;
  policyGateStatus?: string | null;
  bookMode?: string | null;
  originLabel?: string | null;
}): LiveVirtualWhyBlock[] {
  const valor: string[] = [];
  const dir = directionLabel(input.action);
  if (dir) {
    valor.push(`Dictamen de propuesta: ${dir} (≠ autorización de compra).`);
  }
  if (input.weightContext?.rationale?.trim()) {
    valor.push(input.weightContext.rationale.trim());
  }
  if (input.weightContext?.horizon && input.weightContext?.regime) {
    valor.push(
      `Fusión ${input.weightContext.horizon} · régimen ${input.weightContext.regime}.`,
    );
  }
  if (input.tradePlan?.status) {
    valor.push(`TradePlan ${input.tradePlan.status}.`);
  }
  const blocked = whyNotLabels(input.tradePlan?.whyNot);
  if (blocked.length) {
    valor.push(`Bloqueos plan: ${blocked.join(" · ")}.`);
  }
  if (input.originLabel) {
    valor.push(`Origen cola: ${input.originLabel}.`);
  }
  if (valor.length === 0) {
    valor.push("Sin explicación disponible.");
  }

  const tamano: string[] = [];
  if (input.ticket) {
    tamano.push(
      `${input.ticket.quantity} × ${input.ticket.price.toFixed(2)} · notional ~ ${input.ticket.notional.toFixed(2)} ${input.ticket.currency}.`,
    );
    if (input.ticket.fees.total > 0) {
      tamano.push(
        `Fees est. ${input.ticket.fees.total.toFixed(2)} ${input.ticket.currency} (${input.ticket.commissionProfileLabel}).`,
      );
    }
  }
  if (input.stop != null && Number.isFinite(input.stop)) {
    tamano.push(`Stop plan / firmado: ${input.stop.toFixed(2)}.`);
  }
  if (input.riskPct != null && Number.isFinite(input.riskPct)) {
    tamano.push(`Riesgo plan ~ ${input.riskPct.toFixed(2)}% equity.`);
  }
  if (input.tradePlan?.expectedRR != null) {
    tamano.push(`R/R esperado ~ ${input.tradePlan.expectedRR.toFixed(2)}.`);
  }
  if (tamano.length === 0) {
    tamano.push("Sin explicación disponible.");
  }

  const orden: string[] = [];
  if (input.bookMode) {
    orden.push(
      `Libro ${input.bookMode.toUpperCase()} · Confirm = firma humana (nunca sola).`,
    );
  } else {
    orden.push("Confirm = firma humana · nunca se envía sola.");
  }
  if (input.tradePlan?.entryCondition) {
    orden.push(`Condición entrada: ${input.tradePlan.entryCondition}.`);
  }
  if (input.tradePlan?.executionAllowed === false) {
    orden.push("Plan: executionAllowed=false (inspecciona antes de firmar).");
  }
  if (input.policyGateStatus) {
    orden.push(`Policy gate: ${input.policyGateStatus}.`);
  }
  if (orden.length === 0) {
    orden.push("Sin explicación disponible.");
  }

  const anti = [
    "Ranking ≠ BUY.",
    "Arm ≠ Execute.",
    "LIVE VIRTUAL ≠ capital real · respuesta broker simulada.",
  ];

  return [
    { id: "valor", title: "Por qué este valor", bullets: valor },
    { id: "tamano", title: "Por qué este tamaño / precio", bullets: tamano },
    { id: "orden", title: "Por qué se realiza esta orden", bullets: orden },
    { id: "anti", title: "Qué NO implica", bullets: anti },
  ];
}
