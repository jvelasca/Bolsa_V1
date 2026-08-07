/**
 * notification-prefs — normalización y email listo.
 */

import { describe, expect, it } from 'vitest';
import {
  defaultNotificationPrefs,
  isValidEmailLoose,
  normalizeNotificationPrefs,
  notificationEmailReady,
} from '@/features/config/notification-prefs';

describe('notification-prefs', () => {
  it('defaults toast on and email off', () => {
    const d = defaultNotificationPrefs();
    expect(d.alarmaToastEnabled).toBe(true);
    expect(d.alarmaEmailEnabled).toBe(false);
    expect(d.alarmaEmail).toBe('');
    expect(d.dailyDigestEnabled).toBe(false);
    expect(d.dailyDigestPdfEnabled).toBe(false);
  });

  it('normalizes partial raw', () => {
    const n = normalizeNotificationPrefs({
      alarmaEmailEnabled: true,
      alarmaEmail: '  a@b.com ',
      dailyDigestEnabled: true,
      dailyDigestPdfEnabled: true,
    });
    expect(n.alarmaToastEnabled).toBe(true);
    expect(n.alarmaEmailEnabled).toBe(true);
    expect(n.alarmaEmail).toBe('a@b.com');
    expect(n.dailyDigestEnabled).toBe(true);
    expect(n.dailyDigestPdfEnabled).toBe(true);
  });

  it('validates email loosely', () => {
    expect(isValidEmailLoose('a@b.com')).toBe(true);
    expect(isValidEmailLoose('bad')).toBe(false);
    expect(notificationEmailReady({
      alarmaToastEnabled: true,
      alarmaEmailEnabled: true,
      alarmaEmail: 'a@b.com',
      dailyDigestEnabled: false,
      dailyDigestPdfEnabled: false,
    })).toBe(true);
    expect(notificationEmailReady({
      alarmaToastEnabled: true,
      alarmaEmailEnabled: true,
      alarmaEmail: 'bad',
      dailyDigestEnabled: false,
      dailyDigestPdfEnabled: false,
    })).toBe(false);
  });
});
