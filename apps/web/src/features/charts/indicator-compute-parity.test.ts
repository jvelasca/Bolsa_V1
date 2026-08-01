import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { ChartIndicatorInstance, OhlcvBarDto } from '@bolsa/shared';
import {
  resolveOverlayRenderSeries,
  resolveSubRenderSeries,
} from '@/features/charts/indicator-compute';

const fixtureDir = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../packages/py/analytics/tests/fixtures',
);
const golden = JSON.parse(readFileSync(join(fixtureDir, 'indicator_golden.json'), 'utf8')) as {
  bars: OhlcvBarDto[];
  barsExtended?: OhlcvBarDto[];
  cases: Array<{
    definitionId: string;
    parameters: Record<string, number>;
    lineKey: string;
    barsRef?: string;
    points: Array<{ timestamp: string; value: number }>;
  }>;
};

function instanceFor(definitionId: string, parameters: Record<string, number>): ChartIndicatorInstance {
  return {
    instanceId: `test-${definitionId}`,
    definitionId,
    parameters,
    visible: true,
  };
}

function resolveSeries(instance: ChartIndicatorInstance, bars: OhlcvBarDto[]) {
  const overlay = resolveOverlayRenderSeries(instance, bars, []);
  if (overlay.length > 0) return overlay;
  return resolveSubRenderSeries(instance, bars, []);
}

function barsForCase(testCase: (typeof golden.cases)[number]): OhlcvBarDto[] {
  if (testCase.barsRef === 'extended') {
    if (!golden.barsExtended?.length) {
      throw new Error('barsExtended missing in indicator_golden.json');
    }
    return golden.barsExtended;
  }
  return golden.bars;
}

describe('indicator compute golden parity (TS chart vs fixture)', () => {
  for (const testCase of golden.cases) {
    it(`${testCase.definitionId}/${testCase.lineKey} ${JSON.stringify(testCase.parameters)}`, () => {
      const instance = instanceFor(testCase.definitionId, testCase.parameters);
      const series = resolveSeries(instance, barsForCase(testCase));
      const line = series.find((item) => item.key === testCase.lineKey);
      expect(line).toBeDefined();
      expect(line!.points).toHaveLength(testCase.points.length);
      for (let i = 0; i < testCase.points.length; i += 1) {
        expect(String(line!.points[i]!.time)).toBe(testCase.points[i]!.timestamp);
        expect(line!.points[i]!.value).toBeCloseTo(testCase.points[i]!.value!, 9);
      }
    });
  }
});
