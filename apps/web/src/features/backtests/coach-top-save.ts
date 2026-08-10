/**
 * Persistencia Guardar TOP-3 desde recomendaciones del coach.
 * Puro + async resolve — sin depender del top-50 de la lista de estrategias.
 */

import type {
  ChartTimeframe,
  InstrumentStrategyTopSlotV1,
  StrategyDefinitionSummaryDto,
} from "@bolsa/shared";
import type { TechnicalRecommendation } from "@/features/backtests/backtest-deep-coach";
import { dedupeInstrumentTopSlots } from "@/features/backtests/instrument-strategy-top-promote";

export type CoachTopCreatePreset = (input: {
  name: string;
  presetKey: string;
  timeframe: ChartTimeframe;
}) => Promise<StrategyDefinitionSummaryDto>;

export type CoachTopStrategyLookup = {
  /** Lista ya cargada (puede estar truncada). */
  existing: StrategyDefinitionSummaryDto[];
  createFromPreset: CoachTopCreatePreset;
  /** Opcional: resolver por id si no está en existing. */
  getById?: (id: string) => Promise<StrategyDefinitionSummaryDto | null>;
};

export function coachTopStrategyName(symbol: string, label: string): string {
  return `${symbol} · ${label}`;
}

/**
 * Construye slots 1..N desde recomendaciones ya rankeadas.
 * Dedup por strategyType (el ranking ya debería venir deduplicado).
 */
export async function buildCoachTopSlots(opts: {
  recommendations: TechnicalRecommendation[];
  symbol: string;
  timeframe: string;
  lookup: CoachTopStrategyLookup;
  limit?: number;
  /** Origen del slot (Finalistas post-Lab → optimized). */
  slotSource?: InstrumentStrategyTopSlotV1["source"];
  /**
   * Post-Lab / Finalistas active: exige runId (Checklist Camino A).
   * Omite candidatas sin run; si ninguna queda → error.
   */
  requireRunId?: boolean;
}): Promise<InstrumentStrategyTopSlotV1[]> {
  const limit = opts.limit ?? 3;
  const recs = opts.recommendations.slice(0, Math.max(limit * 2, limit));
  const tf = (
    opts.timeframe === "1w" ? "1wk" : opts.timeframe
  ) as ChartTimeframe;
  const existing = [...opts.lookup.existing];
  const usedTypes = new Set<string>();
  const usedDefIds = new Set<string>();
  const rawSlots: InstrumentStrategyTopSlotV1[] = [];

  for (const rec of recs) {
    if (rawSlots.length >= limit) break;
    if (opts.requireRunId && !rec.row.runId) continue;

    const presetKey = rec.row.strategyType;
    if (presetKey && !rec.row.strategyDefinitionId && usedTypes.has(presetKey))
      continue;

    let strategyDefinitionId: string | null =
      rec.row.strategyDefinitionId ?? null;
    if (!strategyDefinitionId && presetKey) {
      const wantedName = coachTopStrategyName(opts.symbol, rec.row.label);
      const found = existing.find(
        (s) => s.name === wantedName && s.presetKey === presetKey,
      );
      if (found) {
        if (usedDefIds.has(found.id)) continue;
        strategyDefinitionId = found.id;
      } else {
        const created = await opts.lookup.createFromPreset({
          name: wantedName,
          presetKey,
          timeframe: tf,
        });
        strategyDefinitionId = created.id;
        existing.push(created);
      }
    }

    if (strategyDefinitionId) {
      if (usedDefIds.has(strategyDefinitionId)) continue;
      usedDefIds.add(strategyDefinitionId);
    }
    if (presetKey && !rec.row.strategyDefinitionId) usedTypes.add(presetKey);

    let resolvedType = presetKey ?? rec.row.strategyType ?? null;
    if (strategyDefinitionId) {
      const fromExisting = existing.find((s) => s.id === strategyDefinitionId);
      if (fromExisting?.presetKey) resolvedType = fromExisting.presetKey;
      else if (opts.lookup.getById) {
        const fetched = await opts.lookup.getById(strategyDefinitionId);
        if (fetched?.presetKey) {
          resolvedType = fetched.presetKey;
          existing.push(fetched);
        }
      }
    }

    rawSlots.push({
      rank: (rawSlots.length + 1) as 1 | 2 | 3,
      label: rec.row.label,
      strategyType: resolvedType,
      strategyDefinitionId,
      stars: rec.stars,
      score: rec.score,
      starsCapped: Boolean(rec.starsCapped),
      runId: rec.row.runId ?? null,
      source:
        opts.slotSource ??
        (rec.row.labPass === "lab_improved" ? "optimized" : "coach"),
      totalReturnPct: rec.row.totalReturnPct ?? null,
      excessReturnPct: rec.row.excessReturnPct ?? null,
      maxDrawdownPct: rec.row.maxDrawdownPct ?? null,
      lateReturnPct: rec.lateReturnPct ?? null,
    });
  }

  if (opts.requireRunId && rawSlots.length === 0) {
    throw new Error(
      "Finalistas: ninguna candidata con runId. Re-simula el lote post-Lab antes de guardar.",
    );
  }

  return dedupeInstrumentTopSlots(rawSlots, limit);
}

/**
 * Une estrategias de la lista + defs referenciadas por el TOP que faltan (limit 50).
 */
export async function mergeStrategiesWithTopSlots(opts: {
  strategies: StrategyDefinitionSummaryDto[];
  slots: Array<{ strategyDefinitionId?: string | null }>;
  getById: (id: string) => Promise<StrategyDefinitionSummaryDto | null>;
}): Promise<StrategyDefinitionSummaryDto[]> {
  const byId = new Map(opts.strategies.map((s) => [s.id, s]));
  const missing = new Set<string>();
  for (const slot of opts.slots) {
    const id = slot.strategyDefinitionId;
    if (id && !byId.has(id)) missing.add(id);
  }
  await Promise.all(
    [...missing].map(async (id) => {
      const s = await opts.getById(id);
      if (s) byId.set(s.id, s);
    }),
  );
  return [...byId.values()];
}

/** Filtra biblioteca a finalistas del TOP (ids de slots). */
export function filterFinalistStrategies(
  strategies: StrategyDefinitionSummaryDto[],
  topStrategyIds: ReadonlySet<string>,
): StrategyDefinitionSummaryDto[] {
  return strategies.filter((s) => topStrategyIds.has(s.id));
}
