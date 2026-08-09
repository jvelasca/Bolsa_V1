/**
 * Columna «Procesos»: 3 iconos (vigilia / frescura / rediscubrir).
 * Sincro (velas) es otra columna — no mezclar.
 */

import { Activity, FlaskConical, RefreshCcw } from 'lucide-react';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  ESTUDIO_SUPERVISION_EVENT,
  loadEstudioSupervisionPrefs,
} from '@/features/trading/estudio-supervision';
import { ESTUDIO_LANE_STAMPS_EVENT } from '@/features/trading/estudio-lane-stamps';
import {
  resolveEstudioProcessStatus,
  type EstudioProcessLaneId,
  type EstudioProcessLaneState,
} from '@/features/trading/estudio-process-status';
import { useEstudioProcessRunningStore } from '@/stores/estudio-process-running-store';
import { useEffect, useState } from 'react';

const ICONS: Record<
  EstudioProcessLaneId,
  typeof Activity
> = {
  vigilance: Activity,
  freshness: FlaskConical,
  rediscover: RefreshCcw,
};

function toneClass(state: EstudioProcessLaneState): string {
  switch (state) {
    case 'ok':
      return 'text-emerald-500';
    case 'stale':
      return 'text-amber-500';
    case 'running':
      return 'text-sky-500';
    case 'empty':
    default:
      return 'text-muted-foreground/50';
  }
}

type Props = {
  instrumentId: string;
  className?: string;
};

export function ListProcessStatusCell({ instrumentId, className }: Props) {
  const [prefs, setPrefs] = useState(() => loadEstudioSupervisionPrefs());
  const [stampTick, setStampTick] = useState(0);
  const runningId = useEstudioProcessRunningStore((s) => s.instrumentId);
  const runningLane = useEstudioProcessRunningStore((s) => s.lane);

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

  const view = useMemo(
    () =>
      resolveEstudioProcessStatus({
        instrumentId,
        prefs,
        runningLane: runningId === instrumentId ? runningLane : null,
      }),
    // stampTick es señal de refresco (timestamps de proceso); conservar dep
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [instrumentId, prefs, runningId, runningLane, stampTick],
  );

  return (
    <span
      className={cn('inline-flex items-center justify-center gap-0.5', className)}
      data-testid="list-process-status-cell"
    >
      {view.lanes.map((lane) => {
        const Icon = ICONS[lane.id];
        return (
          <span key={lane.id} title={lane.title} className="inline-flex">
            <Icon
              className={cn(
                'h-3.5 w-3.5',
                toneClass(lane.state),
                lane.state === 'running' && 'animate-spin',
              )}
              strokeWidth={2.4}
              aria-label={`${lane.label}: ${lane.state}`}
            />
          </span>
        );
      })}
    </span>
  );
}

type StampProps = {
  instrumentId: string;
  kind: 'lab' | 'coreR';
  className?: string;
};

export function ListProcessTimestampCell({ instrumentId, kind, className }: StampProps) {
  const [prefs, setPrefs] = useState(() => loadEstudioSupervisionPrefs());
  const [stampTick, setStampTick] = useState(0);
  const runningId = useEstudioProcessRunningStore((s) => s.instrumentId);
  const runningLane = useEstudioProcessRunningStore((s) => s.lane);

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

  const view = useMemo(
    () =>
      resolveEstudioProcessStatus({
        instrumentId,
        prefs,
        runningLane: runningId === instrumentId ? runningLane : null,
      }),
    // stampTick es señal de refresco (timestamps de proceso); conservar dep
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [instrumentId, prefs, runningId, runningLane, stampTick],
  );

  const iso = kind === 'lab' ? view.lastLabAt : view.lastCoreRAt;
  const text = iso
    ? new Date(iso).toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
      })
    : '—';

  return (
    <span
      className={cn('text-[10px] tabular-nums text-foreground/80', className)}
      title={iso ? new Date(iso).toLocaleString('es-ES') : 'Sin registro'}
    >
      {text}
    </span>
  );
}
