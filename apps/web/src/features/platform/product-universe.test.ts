import { describe, expect, it } from 'vitest';
import {
  diaDVerifyHref,
  productUniverseFromPath,
  VERIFY_DIA_D_CTA,
} from '@/features/platform/product-universe';

describe('product-universe', () => {
  it('maps routes', () => {
    expect(productUniverseFromPath('/backtests')).toBe('lab');
    expect(productUniverseFromPath('/backtests?tab=run')).toBe('lab');
    expect(productUniverseFromPath('/trading')).toBe('trading');
    expect(productUniverseFromPath('/overview')).toBe(null);
  });

  it('builds verify href', () => {
    expect(diaDVerifyHref('abc')).toContain('verify=1');
    expect(diaDVerifyHref('abc')).toContain('focus=detail');
    expect(VERIFY_DIA_D_CTA).toBe('Verificar D→hoy');
  });
});
