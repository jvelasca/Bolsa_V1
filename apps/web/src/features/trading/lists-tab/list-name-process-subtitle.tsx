/**
 * Subtítulo bajo el nombre en lista Estudio: resumen de capas + barra al actualizar.
 *
 * Textos: `al día` · `toca V·F` · `sin sync` · `actualizando…`
 * Tooltip: detalle de cada capa (mismo contenido que iconos Procesos).
 *
 * @see summarizeEstudioProcessLanes
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 */

import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  ESTUDIO_SUPERVISION_EVENT,
  loadEstudioSupervisionPrefs,
} from '@/features/trading/estudio-supervision';
import { ESTUDIO_LANE_STAMPS_EVENT } from '@/features/trading/estudio-lane-stamps';
import {
  resolveEstudioProcessStatus,
  summarizeEstudioProcessLanes,
} from '@/features/trading/estudio-process-status';
import { useEstudioProcessRunningStore } from '@/stores/estudio-process-running-store';

type Props = {
  instrumentId: string;
  className?: string;
};

function toneClass(tone: ReturnType<typeof summarizeEstudioProcessLanes>['tone']): string {
  switch (tone) {
    case 'ok':
      return 'text-emerald-600 dark:text-emerald-400/90';
    case 'attention':
      return 'text-amber-600 dark:text-amber-400/90';
    case 'running':
      return 'text-sky-700 dark:text-sky-300';
    case 'empty':
    default:
      return 'text-muted-foreground';
  }
}

export function ListNameProcessSubtitle({ instrumentId, className }: Props) {
  const [prefs, setPrefs] = useState(() => loadEstudioSupervisionPrefs());
  const [stampTick, setStampTick] = useState(0);
  const runningId = useEstudioProcessRunningStore((s) => s.instrumentId);
  const runningLane = useEstudioProcessRunningStore((s) => s.lane);
  const isRunning = runningId === instrumentId;

  useEffect(() => {
    const sync = () => setPrefs(loadEstudioSupervisionPrefs());
    const onStamps = () => setStampTick((n) => n + 1);
    window.addEventListener(ESTUDIO_SUPERVISION_EVENT, sync);
    window.addEventListener(ESTUDIO_LANE_STAMPS_EVENT, onStamps);
    return () => {
      window.removeEventListener(ESTUDIO_SUPERVISION_EVENT, sync);
      window.removeEventListener(ESTUDIO_LANE_STAMPS_EVENT, onStamps);
    };
  }, []);

  const summary = useMemo(() => {
    const view = resolveEstudioProcessStatus({
      instrumentId,
      prefs,
      runningLane: isRunning ? runningLane : null,
    });
    return summarizeEstudioProcessLanes(view.lanes);
  }, [instrumentId, prefs, isRunning, runningLane, stampTick]);

  return (
    <span
      className={cn(
        'relative mt-0.5 block h-[12px] overflow-hidden rounded-[2px]',
        className,
      )}
      title={summary.title}
      data-testid="list-name-process-subtitle"
    >
      {isRunning || summary.tone === 'running' ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden rounded-[2px] bg-sky-500/10"
        >
          <span className="estudio-row-progress absolute inset-y-0 w-2/5 rounded-[2px] bg-sky-500/35" />
        </span>
      ) : null}
      <span
        className={cn(
          'relative z-[1] block truncate px-0.5 text-[9px] font-medium leading-[12px]',
          toneClass(summary.tone),
        )}
      >
        {summary.text}
      </span>
    </span>
  );
}
