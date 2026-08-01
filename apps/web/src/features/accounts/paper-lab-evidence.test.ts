import { describe, expect, it } from 'vitest';
import { formatPaperLabEvidence } from '@/features/accounts/paper-lab-evidence';

describe('formatPaperLabEvidence (P7)', () => {
  it('shows empty state', () => {
    expect(formatPaperLabEvidence(null)).toBe('—');
    expect(formatPaperLabEvidence({ kind: 'none' })).toBe('Sin validación lab');
  });

  it('formats CPCV + WFE + PBO + Edge', () => {
    const text = formatPaperLabEvidence({
      kind: 'cpcv',
      walkForwardEfficiency: 0.65,
      pbo: 0.55,
      edgeBand: 'uncertain',
    });
    expect(text).toMatch(/CPCV/);
    expect(text).toMatch(/WFE 0\.65/);
    expect(text).toMatch(/PBO 0\.55/);
    expect(text).toMatch(/Edge uncertain/);
  });

  it('formats hold-out OOS', () => {
    expect(
      formatPaperLabEvidence({ kind: 'holdout', oosScore: 4.2 }),
    ).toMatch(/Hold-out · OOS 4\.2/);
  });
});
