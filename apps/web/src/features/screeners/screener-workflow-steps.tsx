import { cn } from "@/lib/utils";

export type ScreenerWorkflowStep = "configure" | "scan" | "results";

interface ScreenerWorkflowStepsProps {
  activeStep: ScreenerWorkflowStep;
  hitCount?: number;
  isRunning?: boolean;
}

const STEPS: Array<{ id: ScreenerWorkflowStep; label: string; short: string }> =
  [
    { id: "configure", label: "1. Configurar", short: "Config" },
    { id: "scan", label: "2. Escanear", short: "Escaneo" },
    { id: "results", label: "3. Actuar", short: "Señales" },
  ];

function stepIndex(step: ScreenerWorkflowStep): number {
  return STEPS.findIndex((item) => item.id === step);
}

export function ScreenerWorkflowSteps({
  activeStep,
  hitCount,
  isRunning,
}: ScreenerWorkflowStepsProps) {
  const activeIdx = stepIndex(activeStep);

  return (
    <ol
      className="flex flex-wrap items-center gap-1.5 sm:gap-2"
      aria-label="Flujo del rastreador"
    >
      {STEPS.map((step, index) => {
        const isActive = step.id === activeStep;
        const isDone = index < activeIdx;
        const showHits =
          step.id === "results" && hitCount != null && hitCount > 0;

        return (
          <li key={step.id} className="flex items-center gap-1.5 sm:gap-2">
            {index > 0 && (
              <span
                className="hidden text-muted-foreground/50 sm:inline"
                aria-hidden
              >
                →
              </span>
            )}
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                isActive && "border-primary/40 bg-primary/10 text-primary",
                isDone &&
                  !isActive &&
                  "border-border bg-muted/30 text-foreground",
                !isActive &&
                  !isDone &&
                  "border-border/60 text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[10px]",
                  isActive && "bg-primary text-primary-foreground",
                  isDone && !isActive && "bg-muted text-foreground",
                  !isActive && !isDone && "bg-muted/50 text-muted-foreground",
                )}
              >
                {index + 1}
              </span>
              <span className="hidden sm:inline">
                {step.label.replace(/^\d+\.\s/, "")}
              </span>
              <span className="sm:hidden">{step.short}</span>
              {step.id === "scan" && isRunning && (
                <span className="text-[10px] text-primary animate-pulse">
                  …
                </span>
              )}
              {showHits && (
                <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:text-emerald-400">
                  {hitCount}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function resolveWorkflowStep(options: {
  isRunning: boolean;
  hasResults: boolean;
}): ScreenerWorkflowStep {
  if (options.hasResults && !options.isRunning) return "results";
  if (options.isRunning) return "scan";
  return "configure";
}
