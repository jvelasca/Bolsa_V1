import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';

interface ScreenerPipelinePanelProps {
  embedded?: boolean;
  executionPolicyCount: number;
  jobMeta: {
    cacheHits?: number | null;
    cacheMisses?: number | null;
  } | null;
}

export function ScreenerPipelinePanel({
  embedded,
  executionPolicyCount,
  jobMeta,
}: ScreenerPipelinePanelProps) {
  const queryClient = useQueryClient();
  const evaluateSchedulesMutation = useMutation({
    mutationFn: () => api.evaluateTrackerSchedules(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['scan-jobs'] }),
  });

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Canal interno"
      description="Cache · cola · programación automática P9"
      icon={Settings2}
    >
      <div className="space-y-2 text-xs text-muted-foreground">
        <p>
          <strong className="text-foreground">Cache</strong> — features por IndicatorSpec
        </p>
        <p>
          <strong className="text-foreground">Cola</strong> —{' '}
          <code className="text-xs">scan_jobs</code>
        </p>
        <p>
          <strong className="text-foreground">Programación</strong> — worker en API (cierre 1d/1wk)
        </p>
        {jobMeta?.cacheHits != null && (
          <p className="border-t border-border pt-2">
            Última tarea: caché {jobMeta.cacheHits} aciertos / {jobMeta.cacheMisses} fallos
          </p>
        )}
        {executionPolicyCount > 0 && (
          <p className="border-t border-border pt-2">
            {executionPolicyCount} políticas de ejecución activas
          </p>
        )}
        <div className="border-t border-border pt-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-full text-xs"
            disabled={evaluateSchedulesMutation.isPending}
            onClick={() => evaluateSchedulesMutation.mutate()}
          >
            {evaluateSchedulesMutation.isPending ? 'Evaluando…' : 'Evaluar programaciones P9'}
          </Button>
          {evaluateSchedulesMutation.data && (
            <p className="mt-1 text-xs text-muted-foreground">
              {evaluateSchedulesMutation.data.data.enqueuedCount} tareas encoladas de{' '}
              {evaluateSchedulesMutation.data.data.checkedCount} rastreadores
            </p>
          )}
        </div>
      </div>
    </ScreenerPanelShell>
  );
}
