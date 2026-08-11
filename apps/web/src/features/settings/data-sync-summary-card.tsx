import { useQuery } from "@tanstack/react-query";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { api } from "@/lib/api";

import { cn } from "@/lib/utils";

import { useUiStore } from "@/stores/ui-store";

export function DataSyncSummaryCard() {
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);

  const settingsQuery = useQuery({
    queryKey: ["sync-settings"],

    queryFn: async () => (await api.getSyncSettings()).data,
  });

  const queueQuery = useQuery({
    queryKey: ["sync-queue"],

    queryFn: async () => (await api.getSyncQueue()).data,

    refetchInterval: 60_000,
  });

  const settings = settingsQuery.data;

  const queue = queueQuery.data ?? [];

  const pendingCount = queue.filter((item) => item.status === "pending").length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Datos de mercado</CardTitle>

        <CardDescription>
          Captura Yahoo → BD local · sincronización automática
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        {settingsQuery.isLoading && (
          <p className="text-muted-foreground">Cargando…</p>
        )}

        {settings && (
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={cn(
                "rounded border px-2 py-0.5 text-xs font-medium",

                settings.autoSyncEnabled
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                  : "border-border text-muted-foreground",
              )}
            >
              Auto-sync {settings.autoSyncEnabled ? "activo" : "inactivo"}
            </span>

            <span className="text-muted-foreground">
              Escaneo cada {settings.scanIntervalMinutes} min · pausa{" "}
              {settings.minDelaySeconds}s
            </span>

            {pendingCount > 0 && (
              <span className="text-amber-400">{pendingCount} en cola</span>
            )}
          </div>
        )}

        <p className="text-muted-foreground">
          Configura proveedores, cola programada y roadmap gráfico en
          Configuración.
        </p>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => openPlatformConfig("other")}
            className="text-primary hover:underline"
          >
            Captura de datos →
          </button>

          <button
            type="button"
            onClick={() => openPlatformConfig("other")}
            className="text-primary hover:underline"
          >
            Sincronización automática →
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
