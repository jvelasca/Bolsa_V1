/** PBO lab helpers (P3.N). Lower is better. */

export const PBO_WARN = 0.5;
export const PBO_BAD = 0.7;

export type PboBand = 'low' | 'elevated' | 'high' | 'n/d';

export function classifyPbo(pbo: number | null | undefined): PboBand {
  if (pbo == null || !Number.isFinite(pbo)) return 'n/d';
  if (pbo < PBO_WARN) return 'low';
  if (pbo < PBO_BAD) return 'elevated';
  return 'high';
}

export function pboBandLabel(band: PboBand): string {
  switch (band) {
    case 'low':
      return 'bajo (mejor)';
    case 'elevated':
      return 'elevado';
    case 'high':
      return 'alto (sobreajuste)';
    default:
      return 'n/d';
  }
}

export function formatPbo(pbo: number | null | undefined): string {
  if (pbo == null || !Number.isFinite(pbo)) return 'n/d';
  return pbo.toFixed(2);
}
