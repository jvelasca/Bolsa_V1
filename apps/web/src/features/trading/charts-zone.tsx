import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { requestChartReflow } from "@/features/charts/chart-utils";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function ChartsZone({ children }: { children: ReactNode }) {
  const charts = useWorkspaceStore((s) => s.workspace.charts);
  const activeChartId = useWorkspaceStore((s) => s.workspace.activeChartId);
  const selectChartTab = useWorkspaceStore((s) => s.selectChartTab);
  const closeChartTab = useWorkspaceStore((s) => s.closeChartTab);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-1 sm:p-2">
        {children}
      </div>
      {charts.length > 0 && (
        <div className="scroll-area flex shrink-0 items-center gap-0.5 overflow-x-auto border-t border-border bg-muted/20 px-1 py-0.5">
          {charts.map((tab) => (
            <div
              key={tab.id}
              role="button"
              tabIndex={0}
              data-testid={
                tab.id === activeChartId ? "chart-active-tab" : undefined
              }
              data-instrument-id={tab.instrumentId}
              data-symbol={tab.label}
              data-active={tab.id === activeChartId ? "true" : undefined}
              onClick={() => {
                selectChartTab(tab.id);
                requestChartReflow();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") selectChartTab(tab.id);
              }}
              className={cn(
                "group flex max-w-[140px] cursor-pointer items-center gap-0.5 rounded px-2 py-0.5 text-[11px]",
                tab.id === activeChartId
                  ? "bg-accent text-primary"
                  : "hover:bg-accent/60",
              )}
            >
              <span className="truncate">{tab.label}</span>
              <button
                type="button"
                title="Cerrar gráfico"
                aria-label="Cerrar gráfico"
                onClick={(e) => {
                  e.stopPropagation();
                  closeChartTab(tab.id);
                }}
                className="rounded p-0.5 opacity-60 hover:bg-background hover:opacity-100"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
