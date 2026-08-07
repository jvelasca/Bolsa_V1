import { describe, expect, it, beforeEach } from 'vitest';
import {
  AUTO_ARM_CONFIRM_PHRASE,
  defaultAutoArm,
  disarmAutoArm,
  loadAutoArm,
  tryArmAuto,
} from '@/features/trading/demo-book-auto-arm';

describe('demo-book-auto-arm (A3)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('rejects wrong phrase', () => {
    const r = tryArmAuto('activar auto');
    expect(r.ok).toBe(false);
    expect(loadAutoArm().armed).toBe(false);
  });

  it('arms with exact phrase and can disarm', () => {
    const r = tryArmAuto(AUTO_ARM_CONFIRM_PHRASE);
    expect(r.ok).toBe(true);
    expect(loadAutoArm().armed).toBe(true);
    expect(disarmAutoArm()).toEqual(defaultAutoArm());
  });
});
