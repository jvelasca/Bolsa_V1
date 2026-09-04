/**
 * V2.30 / V2.34 — Toggle Simple / Completo en chrome del gráfico (sin panel nuevo).
 * V2.34 — touch target ~40px · texto 12px (no text-[9px]).
 */

import { cn } from "@/lib/utils";
import type { ChartFocusModeV1 } from "@/features/charts/chart-focus-prefs";
import {
  useChartFocusPrefs,
  useSetChartFocusMode,
} from "@/features/charts/use-chart-focus-prefs";
import { CABIN_TOUCH_TARGET } from "@/features/trading/cabin-visual";

const MODES: { id: ChartFocusModeV1; label: string }[] = [
  { id: "simple", label: "Simple" },
  { id: "completo", label: "Completo" },
];

type ChartFocusToggleProps = {
  className?: string;
};

export function ChartFocusToggle({ className }: ChartFocusToggleProps) {
  const { mode } = useChartFocusPrefs();
  const setMode = useSetChartFocusMode();

  return (
    <div
      className={cn(
        "pointer-events-auto inline-flex items-center gap-0.5 rounded-md border border-border/70 bg-background/90 p-0.5 shadow-sm backdrop-blur-sm",
        className,
      )}
      data-testid="chart-focus-toggle"
      data-chart-focus={mode}
      role="group"
      aria-label="Foco del plan en gráfico"
    >
      {MODES.map((m) => {
        const active = mode === m.id;
        return (
          <button
            key={m.id}
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "rounded px-3 text-xs font-semibold uppercase tracking-wide transition-colors",
              active
                ? "bg-foreground/10 text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            aria-pressed={active}
            data-testid={`chart-focus-mode-${m.id}`}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
