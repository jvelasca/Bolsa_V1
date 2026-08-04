/**
 * Panel Configuración → Notificaciones (correo Alarmas Estudio, toast).
 * Pre-multiusuario: un destinatario local; SMTP sigue en el servidor.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { checkboxClassName } from '@/components/ui/dialog';
import {
  isValidEmailLoose,
  notificationEmailReady,
} from '@/features/config/notification-prefs';
import { useNotificationPrefsStore } from '@/stores/notification-prefs-store';
import { cn } from '@/lib/utils';

export function NotificationsSettingsPanel() {
  const alarmaToastEnabled = useNotificationPrefsStore((s) => s.alarmaToastEnabled);
  const alarmaEmailEnabled = useNotificationPrefsStore((s) => s.alarmaEmailEnabled);
  const alarmaEmail = useNotificationPrefsStore((s) => s.alarmaEmail);
  const setPrefs = useNotificationPrefsStore((s) => s.setPrefs);

  const emailOk = isValidEmailLoose(alarmaEmail);
  const ready = notificationEmailReady({
    alarmaToastEnabled,
    alarmaEmailEnabled,
    alarmaEmail,
  });

  return (
    <div className="space-y-4" data-testid="notifications-settings">
      <Card>
        <CardHeader>
          <CardTitle>Notificaciones</CardTitle>
          <CardDescription>
            Correo y toasts para Alarmas del Estudio (Asesor). Un operador por navegador hasta
            multiusuario. El envío de email requiere SMTP en el servidor (
            <code className="text-[10px]">SMTP_HOST</code> /{' '}
            <code className="text-[10px]">SMTP_FROM</code>).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5 text-sm">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className={cn(checkboxClassName, 'mt-0.5')}
              checked={alarmaToastEnabled}
              onChange={(e) => setPrefs({ alarmaToastEnabled: e.target.checked })}
            />
            <span>
              <span className="font-medium">Toast in-app de Alarmas</span>
              <p className="mt-1 text-xs text-muted-foreground">
                Avisa cuando aparece una Alarma nueva en el Estudio (sin spamear al abrir la app).
              </p>
            </span>
          </label>

          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className={cn(checkboxClassName, 'mt-0.5')}
              checked={alarmaEmailEnabled}
              onChange={(e) => setPrefs({ alarmaEmailEnabled: e.target.checked })}
            />
            <span>
              <span className="font-medium">Email de Alarmas</span>
              <p className="mt-1 text-xs text-muted-foreground">
                Tras recalcular EOD (manual o cron), envía resumen de Alarmas al correo indicado.
              </p>
            </span>
          </label>

          <label className="flex max-w-md flex-col gap-1.5">
            <span className="font-medium">Correo electrónico</span>
            <input
              type="email"
              autoComplete="email"
              placeholder="tu@correo.com"
              value={alarmaEmail}
              disabled={!alarmaEmailEnabled}
              onChange={(e) => setPrefs({ alarmaEmail: e.target.value })}
              className={cn(
                'rounded-md border bg-background px-3 py-2 text-sm',
                alarmaEmailEnabled && alarmaEmail && !emailOk
                  ? 'border-destructive'
                  : 'border-border',
                !alarmaEmailEnabled && 'opacity-60',
              )}
            />
            {alarmaEmailEnabled && alarmaEmail && !emailOk ? (
              <span className="text-xs text-destructive">Revisa el formato del correo.</span>
            ) : (
              <span className="text-xs text-muted-foreground">
                {ready
                  ? 'Listo: se enviará si el servidor tiene SMTP configurado.'
                  : 'Activa el email y escribe un correo válido.'}
              </span>
            )}
          </label>

          <p className="rounded-md border border-border/70 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            Multiusuario: este buzón pasará al perfil de usuario. Hoy es preferencia local del
            navegador (no sustituye cuentas DEMO / inversión).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
