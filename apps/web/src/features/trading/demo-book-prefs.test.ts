import { describe, expect, it } from 'vitest';
import {
  defaultDemoBookPrefs,
  demoBookAllowsEnqueueConfirm,
  demoBookAllowsExecute,
  demoBookRequiresEstudioMembership,
  normalizeDemoBookPrefs,
  suggestQuantityFromCash,
} from '@/features/trading/demo-book-prefs';

describe('demo-book-prefs', () => {
  it('defaults to SEMI with 10 positions and 10% size', () => {
    const d = defaultDemoBookPrefs();
    expect(d.mode).toBe('semi');
    expect(d.maxOpenPositions).toBe(10);
    expect(d.defaultSizePctOfCash).toBe(10);
  });

  it('normalizes invalid mode and clamps N / pct', () => {
    const n = normalizeDemoBookPrefs({
      mode: 'nope',
      maxOpenPositions: 99,
      defaultSizePctOfCash: 0,
    });
    expect(n.mode).toBe('semi');
    expect(n.maxOpenPositions).toBe(40);
    expect(n.defaultSizePctOfCash).toBe(1);
  });

  it('gates enqueue / execute by mode', () => {
    expect(demoBookAllowsEnqueueConfirm('manual')).toBe(false);
    expect(demoBookAllowsEnqueueConfirm('semi')).toBe(true);
    expect(demoBookAllowsExecute('manual')).toBe(false);
    expect(demoBookAllowsExecute('semi')).toBe(true);
    expect(demoBookAllowsExecute('auto')).toBe(false);
  });

  it('SEMI/AUTO require Estudio membership; MANUAL does not', () => {
    expect(demoBookRequiresEstudioMembership('manual')).toBe(false);
    expect(demoBookRequiresEstudioMembership('semi')).toBe(true);
    expect(demoBookRequiresEstudioMembership('auto')).toBe(true);
  });

  it('suggests quantity ≈ 10% cash / price', () => {
    expect(
      suggestQuantityFromCash({ cash: 20_000, price: 100, sizePctOfCash: 10 }),
    ).toBe(20);
    expect(
      suggestQuantityFromCash({ cash: 500, price: 100, sizePctOfCash: 10 }),
    ).toBe(0);
  });
});
