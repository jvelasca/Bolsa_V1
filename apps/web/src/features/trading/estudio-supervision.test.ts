import { beforeEach, describe, expect, it } from 'vitest';
import {
  ESTUDIO_SUPERVISION_KEY,
  estudioFreshnessDue,
  estudioRediscoverDue,
  formatEstudioCadenceMinutes,
  loadEstudioSupervisionPrefs,
  normalizeEstudioSupervisionPrefs,
  sliceRediscoverBudget,
} from '@/features/trading/estudio-supervision';

describe('estudio-supervision cadencias', () => {
  beforeEach(() => {
    localStorage.removeItem(ESTUDIO_SUPERVISION_KEY);
  });

  it('migra intervalMinutes legacy a vigilanceMinutes (schema ≥2)', () => {
    const n = normalizeEstudioSupervisionPrefs({
      schemaVersion: 2,
      enabled: true,
      intervalMinutes: 240,
      vigilanceMinutes: 240,
      freshnessMinutes: 3 * 1440,
    });
    expect(n.vigilanceMinutes).toBe(240);
    expect(n.intervalMinutes).toBe(240);
    expect(n.freshnessMinutes).toBe(3 * 1440);
    expect(n.rediscoverMinutes).toBe(30 * 1440);
  });

  it('migra defaults v1 (60 min / 7d) a vela diaria', () => {
    const n = normalizeEstudioSupervisionPrefs({
      enabled: true,
      intervalMinutes: 60,
      freshnessMinutes: 7 * 1440,
    });
    expect(n.schemaVersion).toBe(2);
    expect(n.vigilanceMinutes).toBe(1440);
    expect(n.freshnessMinutes).toBe(1440);
  });

  it('freshness due si nunca corrió', () => {
    const p = normalizeEstudioSupervisionPrefs({ enabled: true });
    expect(estudioFreshnessDue(p, Date.now())).toBe(true);
  });

  it('freshness no due dentro del intervalo', () => {
    const now = Date.now();
    const p = normalizeEstudioSupervisionPrefs({
      enabled: true,
      freshnessMinutes: 60,
      lastFreshnessTickAt: new Date(now - 10 * 60_000).toISOString(),
    });
    expect(estudioFreshnessDue(p, now)).toBe(false);
  });

  it('rediscover off cuando minutes=0', () => {
    const p = normalizeEstudioSupervisionPrefs({
      enabled: true,
      rediscoverMinutes: 0,
      lastRediscoverTickAt: null,
    });
    expect(estudioRediscoverDue(p)).toBe(false);
  });

  it('sliceRediscoverBudget rota el cursor', () => {
    const ids = ['a', 'b', 'c', 'd', 'e'];
    const first = sliceRediscoverBudget(ids, 0, 2);
    expect(first.ids).toEqual(['a', 'b']);
    expect(first.nextCursor).toBe(2);
    const second = sliceRediscoverBudget(ids, first.nextCursor, 2);
    expect(second.ids).toEqual(['c', 'd']);
    const wrap = sliceRediscoverBudget(ids, 4, 3);
    expect(wrap.ids).toEqual(['e', 'a', 'b']);
    expect(wrap.nextCursor).toBe(2);
  });

  it('formatEstudioCadenceMinutes', () => {
    expect(formatEstudioCadenceMinutes(0)).toBe('off');
    expect(formatEstudioCadenceMinutes(60)).toBe('1 h');
    expect(formatEstudioCadenceMinutes(7 * 1440)).toBe('7 días');
  });

  it('load defaults vela diaria', () => {
    const p = loadEstudioSupervisionPrefs();
    expect(p.enabled).toBe(false);
    expect(p.vigilanceMinutes).toBe(1440);
    expect(p.freshnessMinutes).toBe(1440);
  });
});
