/**
 * Contrato operativa SEMI DEMO — gates + sizing + geo + Camino C.
 * Battery: `pnpm test:semi`
 */

import { describe, expect, it } from 'vitest';
import {
  demoBookAllowsEnqueueConfirm,
  demoBookAllowsExecute,
  defaultDemoBookPrefs,
  normalizeDemoBookPrefs,
  suggestQuantityFromCash,
} from '@/features/trading/demo-book-prefs';
import {
  inferHomeCountry,
  optimalScoreFromPayload,
  rankByOptimalThenGeo,
} from '@/features/trading/demo-book-geo-rank';
import { PAPER_PATH_SUPERVISED } from '@/features/settings/paper-paths-copy';
import { FINALIST_SUPERVISED_SOURCE } from '@/features/backtests/finalist-propose-supervised';

describe('SEMI DEMO operativa contract', () => {
  it('defaults match product brief (SEMI · N=10 · 10% cash · home_first)', () => {
    const d = defaultDemoBookPrefs();
    expect(d.mode).toBe('semi');
    expect(d.maxOpenPositions).toBe(10);
    expect(d.defaultSizePctOfCash).toBe(10);
    expect(d.countryPrefer).toBe('home_first');
  });

  it('MANUAL blocks enqueue+execute; SEMI allows both; AUTO execute blocked', () => {
    expect(demoBookAllowsEnqueueConfirm('manual')).toBe(false);
    expect(demoBookAllowsExecute('manual')).toBe(false);
    expect(demoBookAllowsEnqueueConfirm('semi')).toBe(true);
    expect(demoBookAllowsExecute('semi')).toBe(true);
    expect(demoBookAllowsEnqueueConfirm('auto')).toBe(true);
    expect(demoBookAllowsExecute('auto')).toBe(false);
  });

  it('sizing ≈ 10% cash / price (floor)', () => {
    expect(
      suggestQuantityFromCash({ cash: 20_000, price: 100, sizePctOfCash: 10 }),
    ).toBe(20);
    expect(
      suggestQuantityFromCash({ cash: 500, price: 100, sizePctOfCash: 10 }),
    ).toBe(0);
  });

  it('geo: óptimo gana; empate favorece home', () => {
    const home = inferHomeCountry({ accountCurrency: 'EUR' });
    expect(home).toBe('ES');
    const ranked = rankByOptimalThenGeo(
      [
        {
          instrumentId: 'us',
          optimalScore: 0.5,
          country: 'US',
          tieBreak: '1',
        },
        {
          instrumentId: 'es',
          optimalScore: 0.5,
          country: 'ES',
          tieBreak: '2',
        },
        {
          instrumentId: 'best-us',
          optimalScore: 0.9,
          country: 'US',
          tieBreak: '3',
        },
      ],
      { prefer: 'home_first', homeCountry: home },
    );
    expect(ranked.map((x) => x.instrumentId)).toEqual(['best-us', 'es', 'us']);
  });

  it('Camino C copy is SEMI Confirm (not Desplegar / not AUTO)', () => {
    expect(PAPER_PATH_SUPERVISED.shortTitle).toMatch(/SEMI/i);
    expect(PAPER_PATH_SUPERVISED.blurb.toLowerCase()).toMatch(/no es auto/);
    expect(FINALIST_SUPERVISED_SOURCE).toBe('finalists');
  });

  it('normalizes illegal prefs without crashing', () => {
    const n = normalizeDemoBookPrefs({
      mode: 'nope',
      maxOpenPositions: 999,
      defaultSizePctOfCash: -5,
      countryPrefer: 'mars',
    });
    expect(n.mode).toBe('semi');
    expect(n.maxOpenPositions).toBeLessThanOrEqual(40);
    expect(n.defaultSizePctOfCash).toBeGreaterThanOrEqual(1);
    expect(n.countryPrefer).toBe('home_first');
  });

  it('optimal score prefers combinedScore over TA', () => {
    expect(
      optimalScoreFromPayload({ combinedScore: 0.8, scoreTa: 0.1 }),
    ).toBe(0.8);
  });
});
