import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  BACKTEST_STRATEGIES,
  serializeChartTabToStrategyDraft,
  type BacktestStrategyType,
  type ChartStrategySetupDraft,
} from '@bolsa/shared';
import { cn } from '@/lib/utils';
import { buttonVariants } from '@/components/ui/button';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useActiveChartTab } from '@/stores/workspace-store';

export interface ChartSetupImportActions {
  onApply: (draft: ChartStrategySetupDraft) => void;
  onSaveStrategy: (draft: ChartStrategySetupDraft, name: string) => void;
  isSaving?: boolean;
}

export function BacktestChartImportPanel({
  onApply,
  onSaveStrategy,
  isSaving = false,
}: ChartSetupImportActions) {
  const activeTab = useActiveChartTab();

  const draft = useMemo(
    () => (activeTab ? serializeChartTabToStrategyDraft(activeTab) : null),
    [activeTab],
  );

  if (!activeTab) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Gráfico activo</CardTitle>
          <CardDescription>Abre un instrumento en Trading para importar su setup.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            to="/trading"
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            Ir a Trading
          </Link>
        </CardContent>
      </Card>
    );
  }

  const saveName = `${activeTab.label} · ${draft?.inferredPresetKey ?? 'setup'}`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Gráfico activo</CardTitle>
        <CardDescription>
          {activeTab.label} · TF {activeTab.timeframe}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {draft && (
          <>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Indicadores</p>
              {draft.indicatorLabels.length === 0 ? (
                <p className="text-muted-foreground">Ninguno visible</p>
              ) : (
                <ul className="mt-1 list-inside list-disc text-foreground">
                  {draft.indicatorLabels.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              )}
            </div>

            {draft.inferredPresetKey && (
              <p className="text-xs text-primary">
                Preset detectado:{' '}
                {BACKTEST_STRATEGIES[draft.inferredPresetKey as BacktestStrategyType].label}
              </p>
            )}

            {draft.warnings.map((warning) => (
              <p key={warning} className="text-xs text-muted-foreground">
                {warning}
              </p>
            ))}

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="default"
                disabled={!draft.canRunPresetBacktest}
                onClick={() => onApply(draft)}
              >
                Aplicar al formulario
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isSaving || draft.indicatorSpecs.length === 0}
                onClick={() => onSaveStrategy(draft, saveName)}
              >
                {isSaving ? 'Guardando…' : 'Guardar estrategia'}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
