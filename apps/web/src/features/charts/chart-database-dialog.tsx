import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ChartTimeframe, InstrumentDataStatusDto } from "@bolsa/shared";
import { RefreshCw } from "lucide-react";
import {
  ChartDatabaseActivityTab,
  ChartDatabaseInstrumentTab,
  ChartDatabaseQualityTab,
  ChartDatabaseServerTab,
  DATA_STATUS_COLORS,
  DATA_STATUS_LABELS,
} from "@/features/charts/chart-database-panel";
import { Dialog, DialogTabs } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type DatabaseDialogTab = "instrument" | "server" | "quality" | "activity";

interface ChartDatabaseDialogProps {
  open: boolean;
  onClose: () => void;
  status: InstrumentDataStatusDto;
  timeframe: ChartTimeframe;
  symbol?: string;
  instrumentId?: string;
  syncing?: boolean;
  onSync?: () => void;
}

export function ChartDatabaseDialog({
  open,
  onClose,
  status,
  timeframe,
  symbol,
  instrumentId,
  syncing,
  onSync,
}: ChartDatabaseDialogProps) {
  const [tab, setTab] = useState<DatabaseDialogTab>("instrument");

  const dbSummaryQuery = useQuery({
    queryKey: ["database-summary", instrumentId],
    queryFn: () => api.getDatabaseSummary(instrumentId),
    enabled: open,
    staleTime: 30_000,
  });

  const statusColor =
    DATA_STATUS_COLORS[status.freshnessStatus] ?? "text-foreground";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Base de datos"
      description={
        symbol
          ? `${symbol} · ${timeframe.toUpperCase()} · PostgreSQL`
          : `PostgreSQL · ${timeframe.toUpperCase()}`
      }
      className="max-w-lg"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/20 px-3 py-2">
        <div className="min-w-0">
          <p className={cn("text-sm font-semibold", statusColor)}>
            {DATA_STATUS_LABELS[status.freshnessStatus] ??
              status.freshnessStatus}
          </p>
          <p className="text-xs text-muted-foreground">
            {status.barCount.toLocaleString("es-ES")} barras en el timeframe
            activo
          </p>
        </div>
        {onSync && (
          <button
            type="button"
            disabled={syncing}
            onClick={onSync}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", syncing && "animate-spin")}
            />
            {syncing ? "Sincronizando…" : "Sincronizar 1D"}
          </button>
        )}
      </div>

      <DialogTabs
        tabs={[
          { id: "instrument", label: "Instrumento" },
          { id: "activity", label: "Actividad" },
          { id: "server", label: "Servidor" },
          { id: "quality", label: "Calidad" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as DatabaseDialogTab)}
      />

      {tab === "instrument" && (
        <ChartDatabaseInstrumentTab
          status={status}
          timeframe={timeframe}
          symbol={symbol}
          dbSummary={dbSummaryQuery.data?.data}
        />
      )}
      {tab === "activity" && (
        <ChartDatabaseActivityTab
          status={status}
          timeframe={timeframe}
          dbSummary={dbSummaryQuery.data?.data}
        />
      )}
      {tab === "server" && (
        <ChartDatabaseServerTab
          dbSummary={dbSummaryQuery.data?.data}
          loadingDb={dbSummaryQuery.isLoading}
        />
      )}
      {tab === "quality" && <ChartDatabaseQualityTab status={status} />}
    </Dialog>
  );
}
