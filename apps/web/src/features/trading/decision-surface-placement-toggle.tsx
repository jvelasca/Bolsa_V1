/**
 * V1.63 — Toggle Panel | Gráfico para ubicación de Decision Surface.
 */

import { cn } from "@/lib/utils";
import {
  useMercadoDecisionSurfacePrefs,
  useSetDecisionSurfacePlacement,
} from "@/features/trading/use-mercado-decision-surface-prefs";
import type { DecisionSurfacePlacementV1 } from "@/features/trading/mercado-decision-surface-prefs";

const OPTIONS: { id: DecisionSurfacePlacementV1; label: string }[] = [
  { id: "panel", label: "Panel" },
  { id: "chart", label: "Gráfico" },
];

export function DecisionSurfacePlacementToggle({
  className,
  size = "sm",
}: {
  className?: string;
  size?: "sm" | "md";
}) {
  const { placement } = useMercadoDecisionSurfacePrefs();
  const setPlacement = useSetDecisionSurfacePlacement();

  return (
    <div
      className={cn(
        "inline-flex rounded-md border border-border/70 p-0.5",
        className,
      )}
      data-testid="decision-surface-placement-toggle"
      role="group"
      aria-label="Ubicación de la superficie de decisión"
    >
      {OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={cn(
            "rounded px-1.5 font-medium transition-colors",
            size === "sm" ? "text-[9px]" : "text-[11px]",
            placement === opt.id
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
          aria-pressed={placement === opt.id}
          data-placement={opt.id}
          onClick={() => setPlacement(opt.id)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
