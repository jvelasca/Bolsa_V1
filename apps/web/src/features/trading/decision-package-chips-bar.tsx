/**
 * U4 — chips compactos: acción DecisionPackage + Fit PASS/VETO.
 * Presentación pura; datos vía mappers en decision-package-chips.ts.
 */

import { cn } from "@/lib/utils";
import type {
  DecisionActionChipView,
  FitChipView,
} from "@/features/trading/decision-package-chips";

function actionTone(action: DecisionActionChipView["action"]): string {
  switch (action) {
    case "recommend_long":
      return "border-emerald-600/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50";
    case "recommend_short":
    case "exit_hint":
    case "reduce":
      return "border-rose-600/40 bg-rose-500/10 text-rose-950 dark:text-rose-50";
    case "wait":
    default:
      return "border-border/70 bg-muted/40 text-muted-foreground";
  }
}

function fitTone(status: FitChipView["status"] | null): string {
  switch (status) {
    case "PASS":
      return "border-emerald-600/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50";
    case "VETO":
      return "border-rose-600/40 bg-rose-500/10 text-rose-950 dark:text-rose-50";
    case "WARNING":
      return "border-amber-600/40 bg-amber-500/10 text-amber-950 dark:text-amber-50";
    default:
      return "border-border/60 bg-muted/25 text-muted-foreground";
  }
}

const CHIP_BASE =
  "inline-flex h-[1.375rem] max-w-[9rem] shrink-0 items-center truncate rounded border px-1.5 text-[10px] font-semibold uppercase tracking-wide leading-none";

export function DecisionPackageChipsBar({
  action,
  fit,
  className,
  density = "full",
}: {
  action: DecisionActionChipView | null;
  fit: FitChipView | null;
  className?: string;
  /** `compact` oculta el slot Fit vacío (barra chart estrecha). */
  density?: "full" | "compact";
}) {
  const showEmptyFit = density === "full";
  if (!action && !fit && !showEmptyFit) return null;

  return (
    <div
      className={cn("flex flex-wrap items-center gap-1", className)}
      data-testid="decision-package-chips"
    >
      {action ? (
        <span
          className={cn(CHIP_BASE, actionTone(action.action))}
          title={action.title}
          data-testid="decision-package-action-chip"
          data-action={action.action}
        >
          {action.label}
        </span>
      ) : null}
      {fit ? (
        <span
          className={cn(CHIP_BASE, fitTone(fit.status))}
          title={fit.title}
          data-testid="decision-package-fit-chip"
          data-fit={fit.status}
        >
          {fit.label}
        </span>
      ) : showEmptyFit ? (
        <span
          className={cn(CHIP_BASE, fitTone(null))}
          title="Fit aún no evaluado para este valor (sin inventar PASS)"
          data-testid="decision-package-fit-chip"
          data-fit="empty"
        >
          Fit · —
        </span>
      ) : null}
    </div>
  );
}
