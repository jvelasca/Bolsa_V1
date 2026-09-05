/**
 * V2.34 — contextual line on chart chrome (no new panel).
 * «Próximo · T2 · 205» or «Estado · T1 alcanzado» from plan geometry.
 */

import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { CABIN_TYPE } from "@/features/trading/cabin-visual";
import { cn } from "@/lib/utils";

function formatLevel(n: number | null | undefined): string | null {
  if (n == null || !Number.isFinite(n)) return null;
  return n.toFixed(2);
}

export function ChartPlanContextStrip({
  instrumentId,
  className,
}: {
  instrumentId: string | null;
  className?: string;
}) {
  const context = useInstrumentOperationalContext(instrumentId);
  const plan = context.plan;
  if (!plan || !context.showsPlanLevels) return null;

  const t1Reached = Boolean(plan.target1Reached || plan.target1Touched);
  const t2Reached = Boolean(plan.target2Reached || plan.target2Touched);
  let line: string | null = null;
  if (t1Reached && !t2Reached && plan.target2 != null) {
    line = `Próximo · T2 · ${formatLevel(plan.target2)}`;
  } else if (!t1Reached && plan.target1 != null) {
    line = `Próximo · T1 · ${formatLevel(plan.target1)}`;
  } else if (t1Reached && t2Reached) {
    line = plan.trailingActive
      ? "Estado · Trailing activo"
      : "Estado · T2 alcanzado";
  } else if (t1Reached) {
    line = "Estado · T1 alcanzado";
  } else if (plan.stopVigente != null) {
    line = `Protección · ${formatLevel(plan.stopVigente)}`;
  }

  if (!line) return null;

  return (
    <p
      className={cn(
        "pointer-events-none absolute bottom-2 left-[7.5rem] z-20 max-w-[14rem] truncate rounded-md border border-border/60 bg-background/90 px-2 py-1 shadow-sm backdrop-blur-sm",
        CABIN_TYPE.meta,
        "font-medium text-foreground",
        className,
      )}
      data-testid="chart-plan-context-strip"
      aria-live="polite"
    >
      {line}
    </p>
  );
}
