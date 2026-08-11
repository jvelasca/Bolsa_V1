import { useEffect, useRef, useState } from "react";
import type {
  ChartTimeframe,
  DataFreshnessStatus,
  InstrumentDataStatusDto,
} from "@bolsa/shared";
import { ChartDatabaseDialog } from "@/features/charts/chart-database-dialog";
import { cn } from "@/lib/utils";

const FLASH_MS = 5000;

function formatStatusDate(iso: string | null, timeframe: ChartTimeframe) {
  if (!iso) return "—";
  const isDaily = timeframe === "1d" || iso.length === 10;
  const d = isDaily ? new Date(`${iso.slice(0, 10)}T12:00:00`) : new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (isDaily) {
    return d.toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isBdHealthy(status: DataFreshnessStatus | undefined): boolean {
  return status === "current" || status === "gap_detected";
}

export function ChartDataStatusBadge({
  status,
  syncing,
  timeframe,
  barsLoaded,
  instrumentId,
  symbol,
  onSync,
  className,
}: {
  status: InstrumentDataStatusDto | undefined;
  syncing?: boolean;
  timeframe: ChartTimeframe;
  barsLoaded?: number;
  instrumentId?: string;
  symbol?: string;
  onSync?: () => void;
  className?: string;
}) {
  const [flash, setFlash] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const prevBarsRef = useRef<number | undefined>(undefined);

  const key: DataFreshnessStatus = syncing
    ? "syncing"
    : (status?.freshnessStatus ?? "empty");
  const healthy = isBdHealthy(key) && (status?.barCount ?? 0) > 0;
  const lastBar = status?.lastBarDate ?? null;

  useEffect(() => {
    if (barsLoaded == null || barsLoaded === 0) return;
    if (prevBarsRef.current === barsLoaded) return;
    prevBarsRef.current = barsLoaded;
    if (status && status.barCount > 0) {
      setFlash(true);
      const timer = window.setTimeout(() => setFlash(false), FLASH_MS);
      return () => window.clearTimeout(timer);
    }
  }, [barsLoaded, status]);

  if (!status && !syncing) return null;

  if (syncing) {
    return (
      <div
        className={cn(
          "max-w-[10rem] truncate rounded-md border border-sky-500/40 bg-sky-950/90 px-2 py-1 text-xs text-sky-300 shadow-sm sm:max-w-none",
          className,
        )}
        title="Actualizando y guardando en BD"
      >
        <span className="hidden sm:inline">
          Actualizando y guardando en BD…
        </span>
        <span className="sm:hidden">Sync BD…</span>
      </div>
    );
  }

  if (flash && status && status.barCount > 0) {
    return (
      <div
        className={cn(
          "max-w-[11rem] truncate rounded-md border border-emerald-500/50 bg-emerald-950/90 px-2 py-1 text-xs text-emerald-300 shadow-sm sm:max-w-none",
          className,
        )}
        title="Actualizados y guardados en BD"
      >
        <span className="hidden font-medium sm:inline">
          Actualizados y guardados en BD
        </span>
        <span className="font-medium sm:hidden">BD OK</span>
        {lastBar && (
          <span className="ml-1 hidden tabular-nums sm:inline">
            · {formatStatusDate(lastBar, timeframe)}
          </span>
        )}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        title="Estado de datos en PostgreSQL — clic para ver detalle"
        onClick={() => setDialogOpen(true)}
        className={cn(
          "rounded border px-2 py-0.5 text-[11px] font-semibold tabular-nums transition-colors",
          healthy
            ? "border-emerald-500/60 bg-emerald-950/80 text-emerald-300 hover:bg-emerald-900/90"
            : "border-red-500/60 bg-red-950/80 text-red-300 hover:bg-red-900/90",
          dialogOpen && "ring-1 ring-primary/50",
          className,
        )}
      >
        BD
      </button>

      {status && (
        <ChartDatabaseDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          status={status}
          timeframe={timeframe}
          symbol={symbol}
          instrumentId={instrumentId}
          syncing={syncing}
          onSync={onSync}
        />
      )}
    </>
  );
}
