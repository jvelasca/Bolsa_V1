/**
 * Banner de actividad del tablero Lab (zonas en cola / analizando).
 */

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { OptimizeProgressPhase } from "@/features/backtests/backtest-optimize-progress";

export type LabZoneActivitySnapshot = {
  zoneId: string;
  rank: 1 | 2 | 3;
  label: string;
  phase: OptimizeProgressPhase | null;
  trialDone?: number | null;
  trialTotal?: number | null;
};

type Props = {
  zones: LabZoneActivitySnapshot[];
  /** Reanalizar con Coach en curso. */
  coachPending?: boolean;
  coachStatus?: string | null;
  className?: string;
};

function chipTone(phase: OptimizeProgressPhase | null): string {
  switch (phase) {
    case "pending":
      return "border-amber-500/40 bg-amber-500/10 text-amber-100";
    case "processing":
    case "running":
      return "border-sky-500/45 bg-sky-500/15 text-sky-100";
    case "completed":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-100";
    case "failed":
      return "border-destructive/40 bg-destructive/10 text-destructive";
    default:
      return "border-border/60 bg-muted/30 text-muted-foreground";
  }
}

function chipLabel(phase: OptimizeProgressPhase | null): string {
  switch (phase) {
    case "pending":
      return "En cola";
    case "processing":
    case "running":
      return "Analizando";
    case "completed":
      return "Listo";
    case "failed":
      return "Error";
    default:
      return "—";
  }
}

export function LabBoardActivityBanner({
  zones,
  coachPending = false,
  coachStatus = null,
  className,
}: Props) {
  const active = zones.filter(
    (z) =>
      z.phase === "pending" ||
      z.phase === "processing" ||
      z.phase === "running",
  );
  const show = coachPending || active.length > 0;
  if (!show) return null;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-sky-500/35 bg-gradient-to-r from-sky-500/15 via-sky-500/5 to-emerald-500/10 px-3 py-2.5",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy
    >
      <div className="flex flex-wrap items-center gap-2">
        <Loader2
          className="h-4 w-4 shrink-0 animate-spin text-sky-300"
          aria-hidden
        />
        <p className="text-[12px] font-medium text-foreground">
          {coachPending
            ? "Pasando resultados al Coach…"
            : active.length === 1
              ? `Lab trabajando en zona #${active[0]!.rank}`
              : `Lab trabajando en ${active.length} zonas`}
        </p>
        {coachStatus && (
          <span className="text-[11px] text-muted-foreground">
            {coachStatus}
          </span>
        )}
      </div>

      {!coachPending && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {zones.map((z) => {
            const live =
              z.phase === "pending" ||
              z.phase === "processing" ||
              z.phase === "running";
            return (
              <span
                key={z.zoneId}
                className={cn(
                  "inline-flex max-w-full items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px]",
                  chipTone(z.phase),
                )}
                title={z.label}
              >
                {live && (
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                )}
                <span className="font-semibold">#{z.rank}</span>
                <span className="truncate opacity-90">
                  {chipLabel(z.phase)}
                </span>
                {z.trialDone != null &&
                z.trialTotal != null &&
                z.trialTotal > 0 &&
                live ? (
                  <span className="tabular-nums opacity-80">
                    {z.trialDone}/{z.trialTotal}
                  </span>
                ) : null}
              </span>
            );
          })}
        </div>
      )}

      <div className="relative mt-2 h-1 overflow-hidden rounded-full bg-muted/50">
        <div className="absolute inset-y-0 w-1/3 animate-[lab-board-shimmer_1.5s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-transparent via-sky-400/90 to-transparent" />
      </div>
      <style>{`
        @keyframes lab-board-shimmer {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(380%); }
        }
      `}</style>
    </div>
  );
}
