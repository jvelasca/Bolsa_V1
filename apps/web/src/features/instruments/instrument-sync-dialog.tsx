/** Diálogo global para sincronizar histórico Yahoo cuando un gráfico no tiene OHLCV. */
import { RefreshCw } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  formatSyncError,
  useInstrumentSync,
} from "@/features/instruments/use-instrument-sync";
import { useUiStore } from "@/stores/ui-store";

export function InstrumentSyncDialog() {
  const target = useUiStore((s) => s.instrumentSyncTarget);
  const close = useUiStore((s) => s.closeInstrumentSyncDialog);
  const instrumentId = target?.instrumentId;
  const symbol = target?.symbol ?? "";
  const syncMutation = useInstrumentSync(instrumentId);

  async function handleSync() {
    try {
      const result = await syncMutation.mutateAsync();
      if (result.data.status !== "failed") {
        close();
      }
    } catch {
      // error shown below
    }
  }

  return (
    <Dialog
      open={Boolean(target)}
      onClose={close}
      title={`Histórico no disponible — ${symbol}`}
      description="Este valor aún no tiene barras diarias en la base de datos. Sincroniza desde Yahoo Finance para dibujar el gráfico."
      className="max-w-md"
    >
      <div className="space-y-4 text-sm">
        <p className="text-muted-foreground">
          Descargaremos hasta 5 años de velas diarias (OHLCV) y las guardaremos
          localmente, igual que en la ficha de instrumento.
        </p>

        {syncMutation.isError && (
          <p className="text-destructive">
            {formatSyncError(syncMutation.error)}
          </p>
        )}

        {syncMutation.isSuccess &&
          syncMutation.data?.data.status === "partial" && (
            <p className="text-amber-400">
              Sincronización parcial:{" "}
              {syncMutation.data.data.error ?? "sin barras nuevas"}
            </p>
          )}

        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={close}>
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={syncMutation.isPending}
            onClick={() => void handleSync()}
          >
            <RefreshCw
              className={cn(
                "mr-1 h-4 w-4",
                syncMutation.isPending && "animate-spin",
              )}
            />
            {syncMutation.isPending ? "Sincronizando…" : "Sincronizar Yahoo"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
