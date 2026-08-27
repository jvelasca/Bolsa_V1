/**
 * Lenguaje de producto del ranking (V1.23 Fase 4).
 *
 * El ranking prioriza; nunca autoriza. Por eso el score se llama Prioridad y
 * el resultado se nombra PREPARADA / VIGILAR / BLOQUEADA — nunca BUY.
 */

import type { OpportunityFunnelV1, OpportunityRankRowV1 } from "@bolsa/shared";

export const PRIORITY_SCORE_PREFIX = "Prioridad" as const;
export const PRIORITY_NOT_AN_ORDER = "NO ES UNA ORDEN" as const;

export function formatPriorityScore(quality: number): string {
  return `${PRIORITY_SCORE_PREFIX} ${quality}/100`;
}

export const OPPORTUNITY_RESULT_LABELS = [
  "PREPARADA",
  "VIGILAR",
  "BLOQUEADA",
] as const;
export type OpportunityResultLabel = (typeof OPPORTUNITY_RESULT_LABELS)[number];

/**
 * Resultado de producto de una fila del ranking.
 * PREPARADA ≠ permiso de compra: sigue exigiendo firma en Confirmar.
 */
export function opportunityResultLabel(
  rankRow: Pick<OpportunityRankRowV1, "category" | "operationalPriority">,
  entriesBlocked = false,
): OpportunityResultLabel {
  if (entriesBlocked) return "BLOQUEADA";
  if (rankRow.category === "BLOCKED") return "BLOQUEADA";
  if (!rankRow.operationalPriority.operability.operable) return "BLOQUEADA";
  if (rankRow.category === "TOP") return "PREPARADA";
  return "VIGILAR";
}

export function opportunityResultTone(label: OpportunityResultLabel): string {
  if (label === "PREPARADA") return "text-emerald-700 dark:text-emerald-300";
  if (label === "BLOQUEADA") return "text-rose-700 dark:text-rose-300";
  return "text-amber-800 dark:text-amber-200";
}

/** Barras de prioridad — tres dimensiones, no tres números gemelos. */
export type OpportunityScoreBarV1 = {
  id: "quality" | "suitability" | "operability";
  label: string;
  value: number;
  hint: string;
};

export function buildOpportunityScoreBars(
  rankRow: Pick<
    OpportunityRankRowV1,
    "quality" | "suitability" | "operability"
  >,
): OpportunityScoreBarV1[] {
  return [
    {
      id: "quality",
      label: "Calidad",
      value: rankRow.quality,
      hint: "Fuerza técnica y relación beneficio/riesgo del estudio",
    },
    {
      id: "suitability",
      label: "Encaje",
      value: rankRow.suitability,
      hint: "Cómo encaja en tu cartera (riesgo abierto, sector, caja)",
    },
    {
      id: "operability",
      label: "Operabilidad",
      value: rankRow.operability,
      hint: "Si hoy se podría preparar la orden (plan, gates, datos)",
    },
  ];
}

/** Embudo en castellano básico — de Estudio a Operables. */
export const HOY_FUNNEL_STEP_LABELS = [
  "ESTUDIO",
  "FILTRADAS",
  "SEÑALES",
  "ANALIZADAS",
  "BUENAS OPORTUNIDADES",
  "ENCAJAN CARTERA",
  "OPERABLES",
] as const;

export function formatFunnelTitle(remaining: number): string {
  return `¿Por qué quedan sólo ${remaining}?`;
}

export type OpportunityFunnelStepV1 = {
  label: (typeof HOY_FUNNEL_STEP_LABELS)[number];
  count: number;
  hint: string;
};

export function buildOpportunityFunnelSteps(
  funnel: Pick<
    OpportunityFunnelV1,
    | "universeCount"
    | "screenedCount"
    | "hitCount"
    | "analyzedCount"
    | "setupCount"
    | "portfolioFitCount"
    | "operableCount"
  >,
): OpportunityFunnelStepV1[] {
  return [
    {
      label: "ESTUDIO",
      count: funnel.universeCount,
      hint: "Valores que vigilas",
    },
    {
      label: "FILTRADAS",
      count: funnel.screenedCount,
      hint: "Revisadas en el último barrido",
    },
    {
      label: "SEÑALES",
      count: funnel.hitCount,
      hint: "Han dado señal en el barrido",
    },
    {
      label: "ANALIZADAS",
      count: funnel.analyzedCount,
      hint: "Con análisis reciente (≤7 días)",
    },
    {
      label: "BUENAS OPORTUNIDADES",
      count: funnel.setupCount,
      hint: "Con fuerza y beneficio/riesgo suficientes",
    },
    {
      label: "ENCAJAN CARTERA",
      count: funnel.portfolioFitCount,
      hint: "Compatibles con tu riesgo y tus sectores",
    },
    {
      label: "OPERABLES",
      count: funnel.operableCount,
      hint: "Se podrían preparar hoy — sigue exigiendo firma",
    },
  ];
}

export const HOY_FUNNEL_CLOCK_LABELS = {
  marketDataAsOf: "Datos de mercado",
  analysisAsOf: "Análisis",
  rankingAsOf: "Ranking",
} as const;

export type OpportunityFunnelClockV1 = {
  id: keyof typeof HOY_FUNNEL_CLOCK_LABELS;
  label: string;
  /** Ya formateado; «—» cuando no hay dato (nunca inventar «ahora»). */
  value: string;
  asOf: string | null;
};

/** Hora corta, o «—» si el dato no existe o no es parseable. */
export function formatFunnelClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function buildOpportunityFunnelClocks(
  funnel: Pick<
    OpportunityFunnelV1,
    "marketDataAsOf" | "analysisAsOf" | "rankingAsOf"
  > | null,
): OpportunityFunnelClockV1[] {
  const ids = [
    "marketDataAsOf",
    "analysisAsOf",
    "rankingAsOf",
  ] as const satisfies ReadonlyArray<keyof typeof HOY_FUNNEL_CLOCK_LABELS>;
  return ids.map((id) => {
    const asOf = funnel?.[id] ?? null;
    return {
      id,
      label: HOY_FUNNEL_CLOCK_LABELS[id],
      value: formatFunnelClock(asOf),
      asOf,
    };
  });
}
