/**
 * Preferencias de notificación del operador (pre-multiusuario).
 * localStorage; más adelante → perfil de usuario / cuenta.
 *
 * @see docs/engineering/asesor-ui-2026-08-04.md
 * @see docs/engineering/audit-pack-estudio-asesor-canales-2026-08-04.md
 */

export const NOTIFICATION_PREFS_KEY = 'bolsa-notification-prefs-v1';

export type NotificationPrefs = {
  /** Toast in-app al detectar Alarmas Estudio nuevas. */
  alarmaToastEnabled: boolean;
  /** Intentar email tras eod-batch / cron (requiere SMTP servidor). */
  alarmaEmailEnabled: boolean;
  /** Destinatario (un solo operador hasta multiusuario). */
  alarmaEmail: string;
};

export function defaultNotificationPrefs(): NotificationPrefs {
  return {
    alarmaToastEnabled: true,
    alarmaEmailEnabled: false,
    alarmaEmail: '',
  };
}

function isValidEmailLoose(value: string): boolean {
  const v = value.trim();
  if (!v || v.length > 254) return false;
  // Suficiente para UI; el servidor / SMTP valida de verdad.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

export function normalizeNotificationPrefs(raw: unknown): NotificationPrefs {
  const d = defaultNotificationPrefs();
  if (!raw || typeof raw !== 'object') return d;
  const o = raw as Partial<NotificationPrefs>;
  const email = typeof o.alarmaEmail === 'string' ? o.alarmaEmail.trim() : d.alarmaEmail;
  return {
    alarmaToastEnabled:
      typeof o.alarmaToastEnabled === 'boolean' ? o.alarmaToastEnabled : d.alarmaToastEnabled,
    alarmaEmailEnabled:
      typeof o.alarmaEmailEnabled === 'boolean' ? o.alarmaEmailEnabled : d.alarmaEmailEnabled,
    alarmaEmail: email,
  };
}

export function loadNotificationPrefs(): NotificationPrefs {
  try {
    const raw = localStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (!raw) return defaultNotificationPrefs();
    return normalizeNotificationPrefs(JSON.parse(raw) as unknown);
  } catch {
    return defaultNotificationPrefs();
  }
}

export function saveNotificationPrefs(prefs: NotificationPrefs): NotificationPrefs {
  const next = normalizeNotificationPrefs(prefs);
  try {
    localStorage.setItem(NOTIFICATION_PREFS_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota */
  }
  return next;
}

export function notificationEmailReady(prefs: NotificationPrefs = loadNotificationPrefs()): boolean {
  return prefs.alarmaEmailEnabled && isValidEmailLoose(prefs.alarmaEmail);
}

export { isValidEmailLoose };
