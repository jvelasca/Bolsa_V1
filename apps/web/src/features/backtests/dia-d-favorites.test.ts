import { beforeEach, describe, expect, it } from 'vitest';
import {
  addCustomDiaD,
  DIA_D_CAROUSEL_KEY,
  DIA_D_FAVORITES_KEY,
  DIA_D_PRESETS,
  defaultDiaDCarouselPrefs,
  formatDiaDDisplay,
  isPresetVisible,
  loadDiaDCarouselPrefs,
  monthsAgoIso,
  removeCustomDiaD,
  resolveDiaDCarouselChips,
  saveDiaDCarouselPrefs,
  togglePresetVisible,
  updateCustomDiaD,
  yearsAgoIso,
} from '@/features/backtests/dia-d-favorites';

describe('dia-d carousel prefs', () => {
  beforeEach(() => {
    localStorage.removeItem(DIA_D_CAROUSEL_KEY);
    localStorage.removeItem(DIA_D_FAVORITES_KEY);
  });

  it('formats ISO as dd/mm/yyyy', () => {
    expect(formatDiaDDisplay('2026-01-01')).toBe('01/01/2026');
  });

  it('has fixed presets 3m/6m/9m/1y/2y', () => {
    expect(DIA_D_PRESETS.map((p) => p.id)).toEqual([
      '3m',
      '6m',
      '9m',
      '1y',
      '2y',
    ]);
    const ref = new Date(2026, 7, 2);
    expect(monthsAgoIso(9, ref)).toBe('2025-11-02');
    expect(yearsAgoIso(1, ref)).toBe('2025-08-02');
  });

  it('toggles preset visibility without deleting presets', () => {
    let prefs = defaultDiaDCarouselPrefs();
    expect(isPresetVisible(prefs, '3m')).toBe(true);
    prefs = togglePresetVisible(prefs, '3m');
    expect(isPresetVisible(prefs, '3m')).toBe(false);
    const chips = resolveDiaDCarouselChips(prefs, new Date(2026, 7, 2));
    expect(chips.some((c) => c.id === '3m')).toBe(false);
    expect(chips.some((c) => c.id === '6m')).toBe(true);
  });

  it('customs are addable editable removable', () => {
    let prefs = defaultDiaDCarouselPrefs();
    prefs = addCustomDiaD(prefs, '2020-03-15', 'Crisis');
    expect(prefs.customs).toEqual([{ iso: '2020-03-15', label: 'Crisis' }]);
    prefs = updateCustomDiaD(prefs, '2020-03-15', {
      iso: '2020-03-20',
      label: 'COVID',
    });
    expect(prefs.customs[0]).toEqual({ iso: '2020-03-20', label: 'COVID' });
    prefs = removeCustomDiaD(prefs, '2020-03-20');
    expect(prefs.customs).toEqual([]);
  });

  it('persists carousel prefs and migrates legacy favorites', () => {
    localStorage.setItem(
      DIA_D_FAVORITES_KEY,
      JSON.stringify(['2024-01-01', '2023-06-01']),
    );
    const prefs = loadDiaDCarouselPrefs();
    expect(prefs.customs.map((c) => c.iso)).toEqual([
      '2024-01-01',
      '2023-06-01',
    ]);
    saveDiaDCarouselPrefs(prefs);
    expect(loadDiaDCarouselPrefs().customs).toHaveLength(2);
  });
});
