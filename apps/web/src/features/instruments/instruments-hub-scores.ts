/**
 * Scores hub Instrumentos I2 — FA batch + Composite/TA batch.
 *
 * @see docs/engineering/instruments-hub-2026-07-31.md
 */

import type { CompositeChipDto, FundamentalChipDto } from "@bolsa/shared";

export const HUB_FA_QUERY_CHUNK = 80;
export const HUB_COMPOSITE_QUERY_CHUNK = 40;

export type HubFaScore = {
  scoreDisplay100: number | null;
  isStale: boolean;
  distress: boolean;
};

export type HubTaScore = {
  /** Pierna técnica 0–100. */
  technicalDisplay100: number | null;
  /** Combined Composite 0–100 (tooltip / sort opcional). */
  compositeDisplay100: number | null;
};

export function chunkIds(ids: string[], size: number): string[][] {
  if (size <= 0) return [ids];
  const out: string[][] = [];
  for (let i = 0; i < ids.length; i += size) {
    out.push(ids.slice(i, i + size));
  }
  return out;
}

export function indexFaScores(
  chips: FundamentalChipDto[],
): Map<string, HubFaScore> {
  const map = new Map<string, HubFaScore>();
  for (const chip of chips) {
    map.set(chip.instrumentId, {
      scoreDisplay100: chip.scoreDisplay100 ?? null,
      isStale: Boolean(chip.isStale),
      distress: Boolean(chip.distress),
    });
  }
  return map;
}

export function indexTaScores(
  chips: CompositeChipDto[],
): Map<string, HubTaScore> {
  const map = new Map<string, HubTaScore>();
  for (const chip of chips) {
    map.set(chip.instrumentId, {
      technicalDisplay100: chip.technicalDisplay100 ?? null,
      compositeDisplay100: chip.scoreDisplay100 ?? null,
    });
  }
  return map;
}
