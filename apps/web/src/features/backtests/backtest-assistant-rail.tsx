/**
 * Rail del Asistente — mapa 5 etapas + Play / ↻ / config (⋯).
 *
 * 1 Probar → 2 Coach → 3 Lab → 4 Revalidar → 5 Finalistas
 * (mismo embudo en 1 valor y Lista AUTO).
 *
 * @see docs/engineering/research-lifecycle.md § Embudo D
 * @see assistant-funnel-map.ts
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { MoreHorizontal, Play, Pause, RotateCcw, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AssistantStepId } from '@/features/backtests/backtest-assistant-steps';
import type { AssistantPrefs } from '@/features/backtests/backtest-assistant-prefs';
import type { AssistantSessionProgress } from '@/features/backtests/backtest-assistant-completion';
import {
  FUNNEL_STAGES,
  funnelPrefsLegend,
  funnelStageStatusLabel,
  resolveActiveFunnelStage,
  resolveFunnelStageStatus,
  type FunnelStageStatus,
} from '@/features/backtests/assistant-funnel-map';
import { AssistantFunnelFlowConfig } from '@/features/backtests/assistant-funnel-flow-config';
import { IconButton } from '@/components/ui/icon-button';
import {
  OpaqueMenuLabel,
  OpaqueMenuPanel,
} from '@/components/ui/opaque-menu-panel';

type ListAutoRailControls = {
  visible: boolean;
  canPause: boolean;
  canResume: boolean;
  canStop: boolean;
  paused: boolean;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
};

type Props = {
  activeStep: AssistantStepId;
  prefs: AssistantPrefs;
  onPrefsChange: (next: AssistantPrefs) => void;
  progress: AssistantSessionProgress;
  coachPass: 'initial' | 'post_lab';
  fullCycleActive: boolean;
  awaitingAck?: boolean;
  /** 'coach1' | 'revalidate' — copy del aviso de pausa */
  awaitingAckStage?: 'coach1' | 'revalidate' | null;
  flashMessage?: string | null;
  onStepClick?: (step: AssistantStepId) => void;
  onReset?: () => void;
  onPlay?: () => void;
  playDisabled?: boolean;
  playTitle?: string;
  listAutoControls?: ListAutoRailControls | null;
  profileLabel?: string | null;
  profileMissing?: boolean;
};

function stageChipClass(status: FunnelStageStatus, active: boolean): string {
  if (status === 'done') {
    return 'border-emerald-500/45 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200';
  }
  if (status === 'skipped') {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200';
  }
  if (status === 'blocked') {
    return 'border-amber-500/60 bg-amber-500/20 text-amber-950 dark:text-amber-100 ring-1 ring-amber-500/40';
  }
  if (active || status === 'active') {
    return 'border-primary/50 bg-primary/10 text-foreground';
  }
  return 'border-border/70 bg-background/60 text-muted-foreground hover:bg-muted/60 hover:text-foreground';
}

export function BacktestAssistantRail({
  activeStep: _activeStep,
  prefs,
  onPrefsChange,
  progress,
  coachPass,
  fullCycleActive,
  awaitingAck = false,
  awaitingAckStage = null,
  flashMessage,
  onStepClick,
  onReset,
  onPlay,
  playDisabled,
  playTitle,
  listAutoControls,
  profileLabel = null,
  profileMissing = false,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const funnelInput = useMemo(
    () => ({
      progress,
      coachPass,
      fullCycleActive,
      awaitingAck,
      finalistsSaved: progress.finalistsSaved,
      finalistsSkipped: progress.finalistsSkipped,
    }),
    [progress, coachPass, fullCycleActive, awaitingAck],
  );
  const activeFunnel = resolveActiveFunnelStage(funnelInput);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  return (
    <div className="shrink-0 rounded-lg border border-border bg-muted/15 px-2.5 py-1.5">
      <div className="flex min-h-8 flex-wrap items-center gap-x-2 gap-y-1.5">
        <p
          className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
          title={`Embudo: ${funnelPrefsLegend()}. Play lanza el ciclo. ⋯ configura.`}
        >
          Asistente
        </p>
        {profileLabel ? (
          <span
            className={cn(
              'max-w-[10rem] truncate rounded border px-1.5 py-0.5 text-[10px]',
              profileMissing
                ? 'border-amber-500/40 text-amber-800 dark:text-amber-200'
                : 'border-border/70 text-muted-foreground',
            )}
            title={profileLabel}
          >
            {profileLabel}
          </span>
        ) : null}

        <div className="flex items-center gap-0.5">
          {onPlay ? (
            <button
              type="button"
              className="rounded p-1 text-primary hover:bg-primary/10 disabled:opacity-40"
              title={playTitle ?? 'Play'}
              aria-label="Ejecutar asistente"
              disabled={playDisabled}
              onClick={onPlay}
            >
              <Play className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : null}
          {listAutoControls?.visible && listAutoControls.canPause ? (
            <button
              type="button"
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Pausa Lista AUTO"
              aria-label="Pausa Lista AUTO"
              onClick={listAutoControls.onPause}
            >
              <Pause className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {listAutoControls?.visible && listAutoControls.canResume ? (
            <button
              type="button"
              className="rounded p-1 text-primary hover:bg-primary/10"
              title="Reanudar Lista AUTO"
              aria-label="Reanudar Lista AUTO"
              onClick={listAutoControls.onResume}
            >
              <Play className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : null}
          {listAutoControls?.visible && listAutoControls.canStop ? (
            <button
              type="button"
              className="rounded p-1 text-destructive hover:bg-destructive/10"
              title="Stop: corta ya la campaña Lista AUTO"
              aria-label="Stop Lista AUTO"
              onClick={listAutoControls.onStop}
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : null}
          {onReset && (
            <button
              type="button"
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Reiniciar asistente"
              aria-label="Reiniciar asistente"
              onClick={onReset}
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          )}

          <div className="relative" ref={menuRef}>
            <IconButton
              icon={MoreHorizontal}
              title="Configuración del asistente"
              active={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
              className={menuOpen ? 'bg-muted text-foreground' : undefined}
            />
            {menuOpen && (
              <OpaqueMenuPanel align="left" className="w-[22.5rem] py-1.5">
                <OpaqueMenuLabel>Diagrama del ciclo</OpaqueMenuLabel>
                <AssistantFunnelFlowConfig
                  prefs={prefs}
                  onPrefsChange={onPrefsChange}
                />
              </OpaqueMenuPanel>
            )}
          </div>
        </div>

        <span className="hidden h-4 w-px shrink-0 bg-border sm:block" aria-hidden />

        <div
          className="flex min-w-0 flex-1 flex-wrap items-center gap-1"
          role="list"
          aria-label="Embudo del asistente"
        >
          {FUNNEL_STAGES.map((stage, i) => {
            const status = resolveFunnelStageStatus(stage.id, funnelInput);
            const active = stage.id === activeFunnel;
            const prefix =
              status === 'done'
                ? '✓ '
                : status === 'skipped'
                  ? '– '
                  : status === 'blocked'
                    ? '! '
                    : '';
            return (
              <div key={stage.id} className="flex items-center gap-1" role="listitem">
                {i > 0 && (
                  <span className="text-[10px] text-muted-foreground/50" aria-hidden>
                    →
                  </span>
                )}
                <button
                  type="button"
                  title={`${stage.n}. ${stage.label}: ${stage.blurb} (${funnelStageStatusLabel(status)})`}
                  disabled={!onStepClick}
                  onClick={() => onStepClick?.(stage.navStep)}
                  className={cn(
                    'rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors',
                    stageChipClass(status, active),
                  )}
                >
                  <span className="tabular-nums text-[10px] opacity-70">{stage.n}</span>{' '}
                  {prefix}
                  {stage.label}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {flashMessage ? (
        <p
          className="mt-1 w-full text-[11px] leading-snug text-muted-foreground"
          aria-live="polite"
        >
          {flashMessage}
        </p>
      ) : null}
      {awaitingAck ? (
        <p className="mt-1 text-[11px] font-medium text-amber-800 dark:text-amber-200" aria-live="polite">
          {awaitingAckStage === 'coach1'
            ? 'Ciclo en pausa en Coach: marca «ACK¹» para pasar al Lab (o atajo semifinal).'
            : 'Ciclo en pausa en Revalidar: marca «ACK final» para grabar o descartar Finalistas.'}
        </p>
      ) : null}
    </div>
  );
}
