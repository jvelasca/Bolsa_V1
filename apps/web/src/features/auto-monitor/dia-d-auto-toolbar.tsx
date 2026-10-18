/**
 * AUTO — selector de vista del monitor (`Ventana actual` / `Operación` / `DÍA-D AUTO` /
 * `Operativa diaria`).
 *
 * El modo por defecto es `Operación` (la historia única es la vista de trabajo); `current` queda
 * como crudo/experto, `DÍA-D AUTO` como sandbox y `daily` como operativa diaria por valor. Las
 * vistas que solo leen artefactos/jobs no añaden trabajo al monitor de producción.
 */

import { type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type AutoMonitorMode = "current" | "operation" | "dia-d" | "daily";

/** Fuente ÚNICA del orden de las pestañas (la página la importa, no la duplica). */
export const AUTO_MONITOR_MODES: readonly AutoMonitorMode[] = [
  "current",
  "operation",
  "dia-d",
  "daily",
];

/** Modos que no deben sondear `/auto/operational-monitor` cada 20 s. */
export const AUTO_MONITOR_MODES_WITHOUT_MONITOR_POLL: readonly AutoMonitorMode[] =
  ["dia-d", "daily"];

export function AutoMonitorModeToolbar({
  mode,
  onChange,
}: {
  mode: AutoMonitorMode;
  /** `focus` pide mover el foco a la pestaña activa tras el commit (patrón WAI-ARIA). */
  onChange: (mode: AutoMonitorMode, focus?: boolean) => void;
}) {
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = AUTO_MONITOR_MODES.indexOf(mode);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % AUTO_MONITOR_MODES.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex =
        (index - 1 + AUTO_MONITOR_MODES.length) % AUTO_MONITOR_MODES.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = AUTO_MONITOR_MODES.length - 1;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    onChange(AUTO_MONITOR_MODES[nextIndex]!, true);
  };

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
          { id: "operation", label: "Operación" },
          { id: "dia-d", label: "DÍA-D AUTO" },
          { id: "daily", label: "Operativa diaria" },
        ] as const
      ).map((option) => (
        <Button
          key={option.id}
          type="button"
          size="sm"
          variant="ghost"
          id={`auto-monitor-mode-tab-${option.id}`}
          role="tab"
          aria-selected={mode === option.id}
          aria-controls={`auto-monitor-mode-panel-${option.id}`}
          tabIndex={mode === option.id ? 0 : -1}
          data-testid={`auto-monitor-mode-${option.id}`}
          onClick={() => onChange(option.id)}
          onKeyDown={onTabKeyDown}
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
