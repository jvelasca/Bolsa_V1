/**
 * Interruptor Supervisión ON (Operativa → Configuración). ADR-024.
 */

import { useEffect, useState } from 'react';
import { ESTUDIO_LIST_NAME } from '@bolsa/shared';
import {
  CORE_R_SCHEDULER_INTERVAL_PRESETS,
  clampCoreRSchedulerInterval,
} from '@/features/backtests/core-r-scheduler';
import {
  loadEstudioSupervisionPrefs,
  setEstudioSupervisionEnabled,
  type EstudioSupervisionPrefs,
} from '@/features/trading/estudio-supervision';

export function EstudioSupervisionPanel({ compact = false }: { compact?: boolean }) {
  const [prefs, setPrefs] = useState<EstudioSupervisionPrefs>(() =>
    loadEstudioSupervisionPrefs(),
  );

  useEffect(() => {
    setPrefs(loadEstudioSupervisionPrefs());
  }, []);

  const onToggle = (enabled: boolean) => {
    const next = setEstudioSupervisionEnabled(enabled, {
      intervalMinutes: prefs.intervalMinutes,
    });
    setPrefs(next);
  };

  const onInterval = (minutes: number) => {
    const intervalMinutes = clampCoreRSchedulerInterval(minutes);
    const next = setEstudioSupervisionEnabled(prefs.enabled, { intervalMinutes });
    setPrefs(next);
  };

  return (
    <div
      className={
        compact
          ? 'space-y-1.5 rounded border border-border/60 bg-background/40 px-2 py-1.5'
          : 'space-y-2 rounded border border-border p-2'
      }
      data-testid="estudio-supervision-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <label className="flex cursor-pointer items-center gap-1.5 text-[11px] font-medium">
          <input
            type="checkbox"
            className="rounded border-border"
            checked={prefs.enabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          Supervisión ON
        </label>
        <select
          className="rounded border border-border bg-background px-1 py-0.5 text-[10px]"
          value={prefs.intervalMinutes}
          disabled={!prefs.enabled}
          onChange={(e) => onInterval(Number(e.target.value))}
          title="Cadencia CORE-R / reevaluación"
        >
          {CORE_R_SCHEDULER_INTERVAL_PRESETS.map((m) => (
            <option key={m} value={m}>
              {m >= 1440 ? '24 h' : `${m} min`}
            </option>
          ))}
          {!CORE_R_SCHEDULER_INTERVAL_PRESETS.includes(
            prefs.intervalMinutes as (typeof CORE_R_SCHEDULER_INTERVAL_PRESETS)[number],
          ) ? (
            <option value={prefs.intervalMinutes}>{prefs.intervalMinutes} min</option>
          ) : null}
        </select>
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        Sobre lista «{ESTUDIO_LIST_NAME}»: Lab (Lista AUTO) + reevaluación CORE-R.
        SEMI confirma operar y cambiar mandato. Quitar de Estudio para la supervisión
        de ese valor.
      </p>
    </div>
  );
}
