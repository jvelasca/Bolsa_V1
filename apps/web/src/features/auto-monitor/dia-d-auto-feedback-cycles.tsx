/**
 * P2 — Ciclos de la ventana DÍA-D con su estado de verificación ENLAZADA (durable).
 *
 * Read-only. Lista el índice `cycles[]` del artefacto de feedback (que hoy no se pintaba)
 * y declara, por ciclo, si existe un registro durable que enlace la verificación D→hoy
 * con ESE ciclo. Huecos declarados: «Sin verificación» ≠ «Sin dato todavía» (ciclo sin
 * `cycleId`) ≠ «No disponible» (fallo de lectura).
 */

import { useMemo } from "react";
import type { components } from "@/api/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useDiaDCycleVerifications } from "@/features/auto-monitor/use-auto-dia-d-feedback";
import {
  DIA_D_CYCLE_VERIFICATION_LABELS,
  resolveDiaDCycleVerificationState,
} from "@/features/auto-monitor/dia-d-cycle-verification-status";

type DiaDFeedbackCycleDto = components["schemas"]["DiaDFeedbackCycleDto"];

const STATE_STYLE: Record<string, string> = {
  linked: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  "not-verified": "bg-muted text-muted-foreground",
  unknown: "bg-muted text-muted-foreground",
};

function formatR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "NO MEDIDO";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function DiaDAutoFeedbackCycles({
  cycles,
}: {
  cycles: readonly DiaDFeedbackCycleDto[];
}) {
  // Verificaciones del principal: el registro durable que enlaza verificación ↔ ciclo.
  const verificationsQuery = useDiaDCycleVerifications();
  const verifiedIds = useMemo(
    () => new Set((verificationsQuery.data?.data ?? []).map((v) => v.cycleId)),
    [verificationsQuery.data],
  );

  if (cycles.length === 0) return null;

  return (
    <Card className="rounded-xl border border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Ciclos de la ventana</CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Cada ciclo con su enlace a la verificación DÍA-D. «Verificación
          vinculada» solo si existe el registro durable; «Sin verificación» si
          no lo hay.
        </p>
      </CardHeader>
      <CardContent>
        <table className="w-full" data-testid="dia-d-auto-feedback-cycles">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
              <th className="pb-1 pr-3 font-semibold">Ciclo</th>
              <th className="pb-1 pr-3 font-semibold">Valor</th>
              <th className="pb-1 pr-3 font-semibold">Días</th>
              <th className="pb-1 pr-3 font-semibold">Estrategia</th>
              <th className="pb-1 pr-3 font-semibold">R</th>
              <th className="pb-1 font-semibold">Verificación DÍA-D</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((cycle) => {
              const state = verificationsQuery.isError
                ? ("unknown" as const)
                : resolveDiaDCycleVerificationState({
                    cycleId: cycle.cycleId,
                    verified: verifiedIds.has(cycle.cycleId),
                  });
              const label = verificationsQuery.isLoading
                ? "Comprobando…"
                : verificationsQuery.isError
                  ? "No disponible"
                  : DIA_D_CYCLE_VERIFICATION_LABELS[state];
              return (
                <tr
                  key={cycle.cycleId}
                  data-testid="dia-d-auto-feedback-cycle"
                  data-cycle-id={cycle.cycleId}
                  data-verification-state={state}
                  className="border-t border-border/50"
                >
                  <td className="py-1.5 pr-3 font-mono text-[11px] text-foreground/90">
                    {cycle.cycleId.slice(0, 10)}…
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-[11px]">
                    {cycle.symbol}
                  </td>
                  <td className="py-1.5 pr-3 text-[11px] text-muted-foreground">
                    {cycle.entryDay ?? "—"} → {cycle.exitDay ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-[11px] text-muted-foreground">
                    {cycle.strategyVersion ?? "Sin dato todavía"}
                  </td>
                  <td className="py-1.5 pr-3 tabular-nums text-[11px]">
                    {formatR(cycle.realizedR)}
                  </td>
                  <td className="py-1.5">
                    <span
                      data-testid="dia-d-auto-feedback-cycle-verification"
                      data-state={state}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        STATE_STYLE[state] ?? "bg-muted text-muted-foreground",
                      )}
                    >
                      {label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
