import { LayoutGrid, Radar } from 'lucide-react';
import type { ScreenerMobileView } from '@/stores/screener-preferences-store';
import { cn } from '@/lib/utils';

interface ScreenerMobileViewTabsProps {
  view: ScreenerMobileView;
  onChange: (view: ScreenerMobileView) => void;
}

export function ScreenerMobileViewTabs({ view, onChange }: ScreenerMobileViewTabsProps) {
  return (
    <div
      className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-muted/30 p-1 lg:hidden"
      role="tablist"
      aria-label="Vista del rastreador"
    >
      {(
        [
          { id: 'workflow' as const, label: 'Rastreo y resultados', icon: Radar },
          { id: 'tools' as const, label: 'Herramientas', icon: LayoutGrid },
        ] as const
      ).map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={view === id}
          className={cn(
            'inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-xs font-medium transition-colors',
            view === id
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
          onClick={() => onChange(id)}
        >
          <Icon className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{label}</span>
        </button>
      ))}
    </div>
  );
}
