import { describe, expect, it } from 'vitest';
import { formatCompositeLegMethod } from '@/features/instruments/composite-leg-labels';

describe('formatCompositeLegMethod', () => {
  it('maps ADV v1.1 buckets', () => {
    expect(formatCompositeLegMethod('adv_mega')).toBe('ADV mega');
    expect(formatCompositeLegMethod('adv_high')).toBe('ADV alta');
    expect(formatCompositeLegMethod('adv_very_high')).toBe('ADV muy alta');
  });

  it('maps mcap fallback buckets', () => {
    expect(formatCompositeLegMethod('mcap_mid_large')).toBe('mcap mid-large');
    expect(formatCompositeLegMethod('mcap_mega')).toBe('mcap mega');
  });

  it('passes through unknown / empty', () => {
    expect(formatCompositeLegMethod(null)).toBeNull();
    expect(formatCompositeLegMethod('')).toBeNull();
    expect(formatCompositeLegMethod('custom_x')).toBe('custom_x');
  });
});
