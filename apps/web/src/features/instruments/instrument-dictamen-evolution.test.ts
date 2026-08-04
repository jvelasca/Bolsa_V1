import { describe, expect, it } from 'vitest';
import { buildDictamenSparklinePath } from '@/features/instruments/instrument-dictamen-evolution';
import type { InstrumentDailyOpinionV1 } from '@bolsa/shared';

function row(
  asOf: string,
  stars: number,
  stance: InstrumentDailyOpinionV1['stance'] = 'hold_watch',
): InstrumentDailyOpinionV1 {
  return {
    id: asOf,
    instrumentId: 'i1',
    asOfBarDate: asOf,
    stance,
    dictamenStars: stars,
    strategyStars: null,
    ioScore: null,
    faScore: null,
    taScore: null,
    distress: false,
    reasons: [],
    gateStatus: 'PASS',
    topId: null,
    topVersion: null,
    source: 'on_demand',
    engineVersion: 'opinion_v1',
    idempotencyKey: asOf,
    computedAt: `${asOf}T18:00:00Z`,
    createdAt: `${asOf}T18:00:00Z`,
    updatedAt: `${asOf}T18:00:00Z`,
  };
}

describe('buildDictamenSparklinePath', () => {
  it('returns empty for no rows', () => {
    expect(buildDictamenSparklinePath([], 100, 40).dots).toEqual([]);
  });

  it('maps ★1 low and ★5 high', () => {
    const { dots } = buildDictamenSparklinePath(
      [row('2026-08-01', 1), row('2026-08-04', 5)],
      100,
      40,
      0,
    );
    expect(dots).toHaveLength(2);
    expect(dots[0]!.y).toBeGreaterThan(dots[1]!.y);
  });
});
