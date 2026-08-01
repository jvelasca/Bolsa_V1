/**
 * Chip FA compacto para filas de Universo Lista (F1 PR3).
 * Solo formatea FundamentalChipDto — no recalcula Score_FUND.
 */

import type { FundamentalChipDto, FundamentalDataConfidence } from '@bolsa/shared';

export type ListMemberFaChipView = {
  primary: string;
  secondary: string;
  confidence: FundamentalDataConfidence;
  toneClass: string;
};

export function faConfidenceToneClass(c: FundamentalDataConfidence): string {
  if (c === 'HIGH') return 'text-emerald-700 dark:text-emerald-300';
  if (c === 'MEDIUM') return 'text-amber-800 dark:text-amber-300';
  return 'text-destructive';
}

export function summarizeListMemberFa(
  chip: FundamentalChipDto | null | undefined,
): ListMemberFaChipView | null {
  if (!chip) return null;
  const score =
    chip.scoreDisplay100 != null && Number.isFinite(chip.scoreDisplay100)
      ? `FUND ${chip.scoreDisplay100}`
      : 'FUND —';
  const parts: string[] = [chip.confidence];
  if (chip.isStale) parts.push('stale');
  if (chip.distress) parts.push('distress');
  return {
    primary: score,
    secondary: parts.join(' · '),
    confidence: chip.confidence,
    toneClass: faConfidenceToneClass(chip.confidence),
  };
}
