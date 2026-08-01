/**
 * Alarmas B1 — toasts entrada/salida desde hits o alarmRoute de rastreador.
 * @see docs/engineering/research-radar-unification-2026-07-31.md
 */

import {
  SIGNAL_KIND_LABELS,
  type ExecutionMode,
  type ScanHitDto,
  type ScanRunResultDto,
  type SignalEventV1,
} from '@bolsa/shared';

export const ALARM_SAFE_MODES: readonly ExecutionMode[] = ['inform_only', 'alert'];

export function isAlarmSafeMode(mode: string | null | undefined): boolean {
  return mode === 'inform_only' || mode === 'alert';
}

export function formatScanHitAlarmToast(hit: ScanHitDto): string {
  const kind = (SIGNAL_KIND_LABELS as Record<string, string>)[hit.signal.kind] ?? hit.signal.kind;
  const price =
    typeof hit.signal.price === 'number' && Number.isFinite(hit.signal.price)
      ? hit.signal.price.toFixed(2)
      : '—';
  return `Radar · ${hit.symbol}: ${kind} @ ${price}`;
}

export function formatAlarmRouteSummary(route: NonNullable<ScanRunResultDto['alarmRoute']>): string {
  const n = route.actions?.length ?? 0;
  const mode =
    route.mode === 'inform_only'
      ? 'informar'
      : route.mode === 'alert'
        ? 'alerta'
        : route.mode;
  if (n === 0) return `Radar · política ${mode}: sin acciones`;
  return `Radar · ${n} alarma${n === 1 ? '' : 's'} (${mode})`;
}

/** Preferencia: alert > inform_only entre políticas habilitadas. */
export function pickAlarmPolicyId(
  policies: Array<{ id: string; mode: ExecutionMode; enabled: boolean }>,
): string | null {
  const enabled = policies.filter((p) => p.enabled && isAlarmSafeMode(p.mode));
  const alert = enabled.find((p) => p.mode === 'alert');
  if (alert) return alert.id;
  return enabled[0]?.id ?? null;
}

export function signalKindLabel(kind: SignalEventV1['kind'] | string): string {
  return (SIGNAL_KIND_LABELS as Record<string, string>)[kind] ?? String(kind);
}
