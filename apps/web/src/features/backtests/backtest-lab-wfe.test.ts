import { describe, expect, it } from 'vitest';
import {
  applyLabWfeToSuite,
  credibilityHintFromLabWfe,
  pickLabWalkForwardEfficiency,
} from '@bolsa/shared';

describe('lab WFE → evidence suite (P3.L)', () => {
  it('picks explicit WFE or recomputes from means', () => {
    expect(pickLabWalkForwardEfficiency({ walkForwardEfficiency: 0.7 })).toBe(0.7);
    expect(
      pickLabWalkForwardEfficiency({ meanOosScore: 6, meanIsScore: 10 }),
    ).toBe(0.6);
    expect(pickLabWalkForwardEfficiency({ meanOosScore: 6, meanIsScore: 0 })).toBeNull();
  });

  it('applies lab_score provenance to suite', () => {
    const suite = applyLabWfeToSuite({ trialsN: 12 }, 0.65);
    expect(suite.walkForwardEfficiency).toBe(0.65);
    expect(suite.wfeSource).toBe('lab_score');
  });

  it('builds credibility hint from lab WFE alone', () => {
    const hint = credibilityHintFromLabWfe(0.8, 10);
    expect(hint.credibility).toBeGreaterThan(0);
    expect(hint.note).toMatch(/WFE lab/i);
  });
});
