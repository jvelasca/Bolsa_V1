import { describe, expect, it } from 'vitest';
import { FINALIST_SUPERVISED_SOURCE } from '@/features/backtests/finalist-propose-supervised';
import { PAPER_PATH_SUPERVISED } from '@/features/settings/paper-paths-copy';

describe('finalist supervised path', () => {
  it('labels Camino C distinct from paper A and auto D', () => {
    expect(FINALIST_SUPERVISED_SOURCE).toBe('finalists');
    expect(PAPER_PATH_SUPERVISED.cta).toMatch(/Proponer/i);
    expect(PAPER_PATH_SUPERVISED.finalistsHint).toMatch(/Camino C|Supervisado|F3|SEMI/i);
    expect(PAPER_PATH_SUPERVISED.finalistsHint.toLowerCase()).not.toContain('desplegar en paper');
    expect(PAPER_PATH_SUPERVISED.blurb.toLowerCase()).toMatch(/no es auto/);
  });
});
