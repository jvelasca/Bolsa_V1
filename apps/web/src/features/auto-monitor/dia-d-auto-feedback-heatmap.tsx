/**
 * DÍA-D AUTO · FEEDBACK — heatmap VALOR × DÍA.
 *
 * Una fila por instrumento y una celda por día de la ventana. El color resume el desenlace
 * declarado del día: ganancia / pérdida / plano / sin medir, y un error de cualquier familia.
 * Un día sin medición se pinta atenuado — nunca como un cero.
 */

import type { components } from "@/api/schema";
import { cn } from "@/lib/utils";

type DiaDFeedbackMatrixRowDto =
  components["schemas"]["DiaDFeedbackMatrixRowDto"];

const OUTCOME_CLASS: Record<string, string> = {
  GAIN: "bg-emerald-500/70",
  LOSS: "bg-red-500/70",
  FLAT: "bg-slate-400/40",
  NOT_MEASURED: "bg-muted/30",
  ERROR: "bg-amber-500/80 ring-1 ring-destructive/60",
};

const OUTCOME_LABEL: Record<string, string> = {
  GAIN: "ganancia",
  LOSS: "pérdida",
  FLAT: "plano",
  NOT_MEASURED: "NO MEDIDO",
  ERROR: "error",
};

export function formatOutcomeR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "NO MEDIDO";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}R`;
}

export function DiaDAutoFeedbackHeatmap({
  matrix,
  days,
  className,
}: {
  matrix: DiaDFeedbackMatrixRowDto[];
  days: string[];
  className?: string;
}) {
  if (matrix.length === 0 || days.length === 0) {
    return (
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="dia-d-auto-feedback-heatmap-empty"
      >
        Sin matriz valor × día para esta ventana.
      </p>
    );
  }

  return (
    <div
      className={cn("overflow-x-auto", className)}
      data-testid="dia-d-auto-feedback-heatmap"
    >
      <div
        className="inline-grid gap-px rounded-md border border-border/50 bg-border/40 p-px"
        style={{
          gridTemplateColumns: `auto repeat(${days.length}, minmax(1.6rem, 1fr))`,
        }}
      >
        <div />
        {days.map((day) => (
          <div
            key={`head-${day}`}
            className="px-0.5 text-center text-[8px] tabular-nums text-muted-foreground"
            title={day}
          >
            {day.slice(5)}
          </div>
        ))}
        {matrix.map((row) => (
          <div key={`row-${row.symbol}`} className="contents">
            <div
              className="flex items-center pr-1 text-[9px] font-mono text-foreground/80"
              title={row.symbol}
            >
              {row.symbol}
            </div>
            {days.map((day) => {
              const cell = (row.cells ?? []).find((item) => item.day === day);
              const outcome = cell?.outcome ?? "NOT_MEASURED";
              return (
                <div
                  key={`${row.symbol}-${day}`}
                  data-testid="dia-d-auto-feedback-cell"
                  data-outcome={outcome}
                  data-day={day}
                  data-symbol={row.symbol}
                  title={`${row.symbol} · ${day} · ${
                    OUTCOME_LABEL[outcome] ?? outcome
                  } · ${formatOutcomeR(cell?.realizedR ?? null)} · ${
                    cell?.cycles ?? 0
                  } ciclo(s) · ${cell?.errors ?? 0} error(es)`}
                  className={cn(
                    "h-4 min-w-[1.6rem] rounded-[2px]",
                    OUTCOME_CLASS[outcome] ?? "bg-muted/30",
                  )}
                />
              );
            })}
          </div>
        ))}
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">
        Verde ganancia · rojo pérdida · ámbar error · atenuado NO MEDIDO. Cada
        celda se atribuye por día de ENTRADA (decisión), no por día de salida.
      </p>
    </div>
  );
}
