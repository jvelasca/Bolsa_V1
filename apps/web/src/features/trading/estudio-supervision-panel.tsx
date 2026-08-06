/**
 * Interruptor Supervisión ON (Operativa → Configuración / banner lista Estudio). ADR-024.
 *
 * Supervisión es global sobre toda la lista Estudio (no hay interruptor por valor).
 * Por instrumento: estar en Estudio = elegible; «Dejar de supervisar» = quitar de la lista.
 */

import { useEffect, useState } from 'react';
import { ESTUDIO_LIST_NAME } from '@bolsa/shared';
import {
  CORE_R_SCHEDULER_INTERVAL_PRESETS,
  clampCoreRSchedulerInterval,
} from '@/features/backtests/core-r-scheduler';
import {
  ESTUDIO_SUPERVISION_EVENT,
  loadEstudioSupervisionPrefs,
  setEstudioSupervisionEnabled,
  type EstudioSupervisionPrefs,
} from '@/features/trading/estudio-supervision';

function useEstudioSupervisionPrefsState() {
  const [prefs, setPrefs] = useState<EstudioSupervisionPrefs>(() =>
    loadEstudioSupervisionPrefs(),
  );

  useEffect(() => {
    setPrefs(loadEstudioSupervisionPrefs());
    const onChange = () => setPrefs(loadEstudioSupervisionPrefs());
    window.addEventListener(ESTUDIO_SUPERVISION_EVENT, onChange);
    return () => window.removeEventListener(ESTUDIO_SUPERVISION_EVENT, onChange);
  }, []);

  const onToggle = (enabled: boolean) => {
    setPrefs(
      setEstudioSupervisionEnabled(enabled, {
        intervalMinutes: prefs.intervalMinutes,
      }),
    );
  };

  const onInterval = (minutes: number) => {
    setPrefs(
      setEstudioSupervisionEnabled(prefs.enabled, {
        intervalMinutes: clampCoreRSchedulerInterval(minutes),
      }),
    );
  };

  return { prefs, onToggle, onInterval };
}

/** Banner compacto encima de la lista Estudio (watchlist). */
export function EstudioListSupervisionBanner() {
  const { prefs, onToggle, onInterval } = useEstudioSupervisionPrefsState();

  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-2 py-1.5 text-[10px]"
      data-testid="estudio-list-supervision-banner"
    >
      <label className="flex cursor-pointer items-center gap-1.5 font-semibold text-foreground">
        <input
          type="checkbox"
          className="rounded border-border"
          checked={prefs.enabled}
          onChange={(e) => onToggle(e.target.checked)}
        />
        Supervisión {prefs.enabled ? 'ON' : 'OFF'}
      </label>
      <select
        className="rounded border border-border bg-background px-1 py-0.5"
        value={prefs.intervalMinutes}
        disabled={!prefs.enabled}
        onChange={(e) => onInterval(Number(e.target.value))}
        title="Cadencia Lab / CORE-R"
      >
        {CORE_R_SCHEDULER_INTERVAL_PRESETS.map((m) => (
          <option key={m} value={m}>
            {m >= 1440 ? '24 h' : `${m} min`}
          </option>
        ))}
      </select>
      <span className="min-w-0 flex-1 text-muted-foreground">
        Global sobre «{ESTUDIO_LIST_NAME}». Por valor: selección → «Dejar de supervisar».
      </span>
    </div>
  );
}

export function EstudioSupervisionPanel({ compact = false }: { compact?: boolean }) {
  const { prefs, onToggle, onInterval } = useEstudioSupervisionPrefsState();

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
        Global sobre «{ESTUDIO_LIST_NAME}»: Lab (Lista AUTO) + CORE-R. No hay interruptor por
        valor — quita el instrumento de Estudio para dejar de supervisarlo. SEMI confirma
        operar y cambiar mandato.
      </p>
    </div>
  );
}
