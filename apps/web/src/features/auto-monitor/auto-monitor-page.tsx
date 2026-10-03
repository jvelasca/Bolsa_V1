/**
 * AUTO Operational Monitor (§11-§15) — espejo UI read-only de la cadena AUTO.
 *
 * Ruta `/auto-monitor`. Pinta el DTO canónico: header (declarado vs habilitado) + timeline de
 * ciclo + ownership de reservas + concurrencia + huecos declarados. No interpreta ni re-deriva.
 */

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AutoConcurrencyPanel } from "@/features/auto-monitor/auto-concurrency-panel";
import { AutoCycleTimeline } from "@/features/auto-monitor/auto-cycle-timeline";
import { AutoMonitorHeader } from "@/features/auto-monitor/auto-monitor-header";
import { AutoReservationPanel } from "@/features/auto-monitor/auto-reservation-panel";
import { DiaDAutoPanel } from "@/features/auto-monitor/dia-d-auto-panel";
import {
  AutoMonitorModeToolbar,
  type AutoMonitorMode,
} from "@/features/auto-monitor/dia-d-auto-toolbar";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";

export function AutoMonitorPage() {
  const { view, isLoading, isError, isFetching, refetch } =
    useAutoOperationalMonitor();
  const [mode, setMode] = useState<AutoMonitorMode>("current");

  return (
    <div
      className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6"
      data-testid="auto-monitor-page"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight">
            Monitor AUTO
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Cadena completa{" "}
            <span className="text-foreground/70">
              SIGNAL → TOP-N → RIESGO → RESERVA → ORDEN → FILL → PROTECCIÓN →
              LIQUIDACIÓN → CICLO CERRADO
            </span>{" "}
            desde el estado durable. Read-only.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Un paso sin traza durable se declara <strong>NO MEDIDO</strong>;
            nunca se rellena con 0.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <AutoMonitorModeToolbar mode={mode} onChange={setMode} />
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void refetch()}
            disabled={isFetching}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar
          </Button>
        </div>
      </div>

      {mode === "dia-d" ? <DiaDAutoPanel /> : null}

      {mode === "current" && isLoading ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="auto-monitor-loading"
        >
          Cargando monitor…
        </p>
      ) : null}

      {mode === "current" && isError ? (
        <p
          className="text-sm text-destructive"
          data-testid="auto-monitor-error"
        >
          No se pudo cargar el monitor operativo.
        </p>
      ) : null}

      {mode === "current" && view ? (
        <>
          <AutoMonitorHeader header={view.header} />

          {view.notes && view.notes.length > 0 ? (
            <Card className="rounded-xl border border-amber-500/30 bg-amber-500/5">
              <CardContent className="py-3">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                  Huecos declarados
                </p>
                <ul
                  className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground"
                  data-testid="auto-monitor-notes"
                >
                  {view.notes.map((note) => (
                    <li key={note} className="font-mono">
                      {note}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          <AutoCycleTimeline cycles={view.cycles} />

          <div className="grid gap-4 lg:grid-cols-2">
            <AutoReservationPanel reservations={view.reservations} />
            <AutoConcurrencyPanel concurrency={view.concurrency} />
          </div>
        </>
      ) : null}
    </div>
  );
}
