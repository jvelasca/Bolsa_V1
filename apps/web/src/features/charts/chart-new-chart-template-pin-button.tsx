import { LayoutTemplate } from 'lucide-react';
import { NEW_CHART_TEMPLATE_PIN_TOOLTIP } from '@bolsa/shared';

import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace-store';

const BTN_CLASS =
  'inline-flex h-[1.375rem] w-[1.375rem] shrink-0 items-center justify-center rounded border border-transparent transition-colors hover:bg-accent disabled:opacity-40';

export function ChartNewChartTemplatePinButton({ className }: { className?: string }) {
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const templateChartId = useWorkspaceStore(
    (s) => s.workspace.preferences.newChartTemplateChartId ?? null,
  );
  const toggle = useWorkspaceStore((s) => s.toggleNewChartTemplatePin);

  const pinned = Boolean(activeChartId && templateChartId === activeChartId);

  return (
    <button
      type="button"
      disabled={!activeChartId}
      title={NEW_CHART_TEMPLATE_PIN_TOOLTIP}
      aria-pressed={pinned}
      aria-label="Plantilla para gráficos nuevos"
      onClick={() => toggle()}
      className={cn(
        BTN_CLASS,
        pinned && 'border-primary/40 bg-primary/15',
        className,
      )}
    >
      <LayoutTemplate
        className={cn('h-3.5 w-3.5', pinned ? 'text-primary' : 'text-muted-foreground')}
      />
    </button>
  );
}
