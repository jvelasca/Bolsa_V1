/**
 * DÍA-D AUTO — selector de vista del monitor (`Ventana actual` / `DÍA-D AUTO`).
 *
 * El modo por defecto es la ventana actual: la vista DÍA-D solo consulta artefactos cuando
 * el usuario la abre (no añade trabajo al monitor de producción).
 */

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type AutoMonitorMode = "current" | "dia-d";

export function AutoMonitorModeToolbar({
  mode,
  onChange,
}: {
  mode: AutoMonitorMode;
  onChange: (mode: AutoMonitorMode) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Vista del monitor AUTO"
      data-testid="auto-monitor-mode-toolbar"
      className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5"
    >
      {(
        [
          { id: "current", label: "Ventana actual" },
          { id: "dia-d", label: "DÍA-D AUTO" },
        ] as const
      ).map((option) => (
        <Button
          key={option.id}
          type="button"
          size="sm"
          variant="ghost"
          role="tab"
          aria-selected={mode === option.id}
          data-testid={`auto-monitor-mode-${option.id}`}
          onClick={() => onChange(option.id)}
          className={cn(
            "h-7 rounded-md px-3 text-xs",
            mode === option.id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}
