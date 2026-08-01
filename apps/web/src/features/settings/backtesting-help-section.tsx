/**
 * Ayuda → Backtesting — resumen básico + pantallas + seguimiento de plataforma.
 */

import { useEffect } from 'react';
import { Link } from 'react-router-dom';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { HelpSourcesFooter } from '@/features/help/help-sources-footer';
import { StrategyMonitorPanel } from '@/features/backtests/strategy-monitor-panel';
import { DiaDEvidenceArchiveHelpCard } from '@/features/settings/dia-d-evidence-archive-help-card';
import {
  BACKTESTING_CORE_R_GUIDE,
  BACKTESTING_DIA_D_GUIDE,
  BACKTESTING_IDEAS,
  BACKTESTING_NEXT,
  BACKTESTING_SCREENS,
  BACKTESTING_SUMMARY,
  BACKTESTING_SYNC,
  BACKTESTING_TRACKING,
  BACKTESTING_YOU_ARE_HERE,
  backtestingStatusLabel,
} from '@/features/settings/backtesting-tracker';
import { cn } from '@/lib/utils';

function statusClass(status: (typeof BACKTESTING_TRACKING)[number]['status']): string {
  if (status === 'listo') return 'text-emerald-600 dark:text-emerald-400';
  if (status === 'cerrado') return 'text-amber-700 dark:text-amber-400';
  return 'text-muted-foreground';
}

export type BacktestingHelpSectionProps = {
  /** CORE-R v1.5: scroll al Monitor al abrir desde el chip de barra. */
  focusMonitor?: boolean;
};

export function BacktestingHelpSection({ focusMonitor = false }: BacktestingHelpSectionProps) {
  useEffect(() => {
    if (!focusMonitor) return;
    const id = window.setTimeout(() => {
      document
        .getElementById('strategy-monitor-panel')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(id);
  }, [focusMonitor]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{BACKTESTING_SUMMARY.title}</CardTitle>
          <CardDescription>
            Backtesting · sync {BACKTESTING_SYNC.asOf} ·{' '}
            <Link to={BACKTESTING_SYNC.route} className="text-primary hover:underline">
              Abrir pantalla
            </Link>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{BACKTESTING_SUMMARY.body}</p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-foreground">
            {BACKTESTING_SUMMARY.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{BACKTESTING_YOU_ARE_HERE.title}</CardTitle>
          <CardDescription>Ruta corta sin laboratorio</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{BACKTESTING_YOU_ARE_HERE.body}</p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-foreground">
            {BACKTESTING_YOU_ARE_HERE.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="text-[11px] text-muted-foreground">{BACKTESTING_YOU_ARE_HERE.pause}</p>
        </CardContent>
      </Card>

      <Card className="border-amber-500/40">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{BACKTESTING_DIA_D_GUIDE.title}</CardTitle>
          <CardDescription>
            Verificación D→hoy ·{' '}
            <Link to={BACKTESTING_SYNC.route} className="text-primary hover:underline">
              Abrir Backtesting
            </Link>
            {' · '}
            <code className="text-[10px]">{BACKTESTING_SYNC.diaDPremises}</code>
            {' · '}
            <code className="text-[10px]">{BACKTESTING_SYNC.operativaTestPlan}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{BACKTESTING_DIA_D_GUIDE.body}</p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-foreground">
            {BACKTESTING_DIA_D_GUIDE.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <ul className="list-disc space-y-1 pl-4 text-[11px] text-muted-foreground">
            {BACKTESTING_DIA_D_GUIDE.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <DiaDEvidenceArchiveHelpCard />

      <Card className="border-border/70">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{BACKTESTING_CORE_R_GUIDE.title}</CardTitle>
          <CardDescription>
            Reevaluación · no auto-paper ·{' '}
            <code className="text-[10px]">{BACKTESTING_SYNC.listAutoOps}</code>
            {' · '}
            <code className="text-[10px]">{BACKTESTING_SYNC.operativaTestPlan}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{BACKTESTING_CORE_R_GUIDE.body}</p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-foreground">
            {BACKTESTING_CORE_R_GUIDE.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <ul className="list-disc space-y-1 pl-4 text-[11px] text-muted-foreground">
            {BACKTESTING_CORE_R_GUIDE.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <StrategyMonitorPanel />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Pantallas del hub</CardTitle>
          <CardDescription>Qué hace cada pestaña — primero en claro, luego el detalle</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {BACKTESTING_SCREENS.map((screen) => (
            <div key={screen.id} className="rounded-md border border-border/70 px-3 py-2">
              <p className="text-sm font-medium text-foreground">{screen.title}</p>
              <p className="mt-1 text-xs text-foreground/90">{screen.plain}</p>
              <p className="mt-1.5 text-[11px] text-muted-foreground">{screen.detail}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Ideas clave</CardTitle>
          <CardDescription>Para no confundir simulación con dinero real</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {BACKTESTING_IDEAS.map((idea) => (
              <li key={idea.id} className="rounded-md border border-border/70 px-3 py-2">
                <p className="text-sm font-medium text-foreground">{idea.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{idea.body}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Seguimiento de plataforma</CardTitle>
          <CardDescription>
            Estado del producto (no preferencias). Detalle en{' '}
            <code className="text-[10px]">{BACKTESTING_SYNC.lifecycleDoc}</code>
            {' · '}
            <code className="text-[10px]">{BACKTESTING_SYNC.handoffDoc}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {BACKTESTING_TRACKING.map((row) => (
            <div key={row.id} className="rounded-md border border-border/70 px-3 py-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-foreground">{row.title}</p>
                <span className={cn('text-[11px] font-medium', statusClass(row.status))}>
                  {backtestingStatusLabel(row.status)}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{row.plain}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Siguiente</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {BACKTESTING_NEXT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <HelpSourcesFooter sectionId="backtesting" />
    </div>
  );
}
