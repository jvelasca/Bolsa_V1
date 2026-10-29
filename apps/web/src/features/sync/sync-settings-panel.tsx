import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Save } from "lucide-react";
import type { SyncScope, SyncSettingsDto } from "@bolsa/shared";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/format";
import { PROVIDERS_QUERY_KEY } from "@/features/settings/market-providers-status-card";

const LIMITS = {
  scanIntervalMinutes: { min: 5, max: 1440 },
  minDelaySeconds: { min: 1, max: 120 },
  maxRetries: { min: 1, max: 20 },
  retryBackoffMinutes: { min: 5, max: 1440 },
  // Mismo rango que el dominio y el CHECK de la 060: la UI valida antes, no acota después.
  providerCheckIntervalSeconds: { min: 15, max: 3600 },
} as const;

const QUEUE_STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  processing: "Procesando",
  failed: "Fallido",
  completed: "Completado",
};

type NumericField = keyof typeof LIMITS;

function queueStatusLabel(status: string): string {
  return QUEUE_STATUS_LABEL[status] ?? status;
}

function queueStatusTone(status: string): string {
  if (status === "failed") return "text-red-400";
  if (status === "processing") return "text-amber-400";
  if (status === "pending") return "text-foreground";
  return "text-muted-foreground";
}

function validationError(draft: SyncSettingsDto): string | null {
  for (const field of Object.keys(LIMITS) as NumericField[]) {
    const value = draft[field];
    const { min, max } = LIMITS[field];
    if (!Number.isFinite(value) || value < min || value > max) {
      return `${field} fuera de rango (${min}–${max}).`;
    }
  }
  return null;
}

export function SyncSettingsPanel({
  embedded = false,
}: {
  embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<SyncSettingsDto | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [enqueueNote, setEnqueueNote] = useState<string | null>(null);
  const [checkNote, setCheckNote] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["sync-settings"],
    queryFn: async () => (await api.getSyncSettings()).data,
  });

  const queueQuery = useQuery({
    queryKey: ["sync-queue"],
    queryFn: async () => (await api.getSyncQueue()).data,
    refetchInterval: 30_000,
  });

  const providersQuery = useQuery({
    queryKey: PROVIDERS_QUERY_KEY,
    queryFn: api.getMarketProviders,
  });

  const settings = settingsQuery.data;
  const queue = queueQuery.data ?? [];
  const yahooDisabled =
    providersQuery.data?.data?.find((provider) => provider.id === "yahoo")
      ?.enabled === false;

  // El borrador se rellena UNA vez con lo persistido; después solo cambia por acción del
  // usuario. Refrescarlo en cada refetch machacaría lo que está escribiendo.
  useEffect(() => {
    if (settings && draft === null) setDraft(settings);
  }, [settings, draft]);

  const counts = useMemo(() => {
    const items = queueQuery.data ?? [];
    return items.reduce<Record<string, number>>((acc, item) => {
      acc[item.status] = (acc[item.status] ?? 0) + 1;
      return acc;
    }, {});
  }, [queueQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (patch: Parameters<typeof api.updateSyncSettings>[0]) =>
      api.updateSyncSettings(patch),
    onSuccess: (response) => {
      setDraft(response.data);
      setSavedAt(new Date().toISOString());
      void queryClient.invalidateQueries({ queryKey: ["sync-settings"] });
      void queryClient.invalidateQueries({ queryKey: ["sync-queue"] });
    },
  });

  const enqueueMutation = useMutation({
    mutationFn: () => api.enqueueStaleInstruments(),
    onSuccess: (response) => {
      const { scanned, enqueued, skippedReason } = response.data;
      setEnqueueNote(
        skippedReason
          ? `No se encoló nada: ${skippedReason}`
          : `Escaneados ${scanned}, encolados ${enqueued}.`,
      );
      void queryClient.invalidateQueries({ queryKey: ["sync-queue"] });
    },
  });

  // «Comprobar ahora» mide de verdad (POST), a diferencia del GET del icono: es la acción
  // explícita del operador y funciona aunque la comprobación automática esté OFF.
  const checkNowMutation = useMutation({
    mutationFn: () => api.checkProviderHealth(),
    onSuccess: (response) => {
      const summary = response.data;
      setCheckNote(
        summary.status === "degraded"
          ? "Comprobación terminada: algún proveedor no responde (ver detalle abajo)."
          : "Comprobación terminada: proveedores medidos.",
      );
      void queryClient.invalidateQueries({ queryKey: PROVIDERS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["provider-health"] });
    },
    onError: (error) => {
      setCheckNote(
        error instanceof Error
          ? `No se pudo comprobar: ${error.message}`
          : "No se pudo comprobar los servidores",
      );
    },
  });

  const error = draft ? validationError(draft) : null;

  const changes = useMemo(() => {
    if (!draft || !settings) return {};
    const patch: Partial<SyncSettingsDto> = {};
    if (draft.autoSyncEnabled !== settings.autoSyncEnabled) {
      patch.autoSyncEnabled = draft.autoSyncEnabled;
    }
    if (draft.postMarketOnly !== settings.postMarketOnly) {
      patch.postMarketOnly = draft.postMarketOnly;
    }
    if (draft.scope !== settings.scope) patch.scope = draft.scope;
    if (draft.providerCheckEnabled !== settings.providerCheckEnabled) {
      patch.providerCheckEnabled = draft.providerCheckEnabled;
    }
    for (const field of Object.keys(LIMITS) as NumericField[]) {
      if (draft[field] !== settings[field]) patch[field] = draft[field];
    }
    return patch;
  }, [draft, settings]);

  const dirty = Object.keys(changes).length > 0;

  if (!settings || !draft) {
    const loading = (
      <p className="text-sm text-muted-foreground">Cargando configuración…</p>
    );
    if (embedded) return loading;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Automatización de datos y servidores</CardTitle>
        </CardHeader>
        <CardContent>{loading}</CardContent>
      </Card>
    );
  }

  const numberField = (field: NumericField, label: string) => (
    <label className="flex flex-col gap-1">
      <span className="text-muted-foreground">{label}</span>
      <input
        type="number"
        min={LIMITS[field].min}
        max={LIMITS[field].max}
        aria-label={label}
        className="rounded border border-border bg-background px-2 py-1"
        value={draft[field]}
        onChange={(event) =>
          setDraft((prev) =>
            prev === null
              ? prev
              : { ...prev, [field]: Number(event.target.value) },
          )
        }
      />
    </label>
  );

  const body = (
    <>
      <section className="space-y-3" aria-labelledby="sync-block-velas">
        <div>
          <h3 id="sync-block-velas" className="text-sm font-medium">
            Velas (histórico)
          </h3>
          <p className="text-xs text-muted-foreground">
            Descarga y mantiene fresco el histórico OHLCV. No comprueba
            servidores.
          </p>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label="Activar auto-actualización"
            checked={draft.autoSyncEnabled}
            onChange={(event) =>
              setDraft((prev) =>
                prev === null
                  ? prev
                  : { ...prev, autoSyncEnabled: event.target.checked },
              )
            }
          />
          Activar auto-actualización en segundo plano
        </label>

        {yahooDisabled && (
          <p
            role="status"
            data-testid="sync-provider-disabled"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-300"
          >
            Yahoo Finance está deshabilitado: no se encolará ni se sincronizará
            nada hasta volver a habilitarlo en «Proveedores».
          </p>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {numberField("scanIntervalMinutes", "Escanear cada (min)")}
          {numberField("minDelaySeconds", "Pausa entre peticiones (s)")}
          {numberField("maxRetries", "Reintentos máx.")}
          {numberField("retryBackoffMinutes", "Backoff reintentos (min)")}
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">
            Universo a mantener fresco
          </span>
          <select
            aria-label="Universo a mantener fresco"
            className="rounded border border-border bg-background px-2 py-1"
            value={draft.scope}
            onChange={(event) =>
              setDraft((prev) =>
                prev === null
                  ? prev
                  : { ...prev, scope: event.target.value as SyncScope },
              )
            }
          >
            <option value="lists">Solo valores en listas (recomendado)</option>
            <option value="stale">
              Todos los instrumentos activos desfasados
            </option>
          </select>
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label="Solo tras cierre de mercado"
            checked={draft.postMarketOnly}
            onChange={(event) =>
              setDraft((prev) =>
                prev === null
                  ? prev
                  : { ...prev, postMarketOnly: event.target.checked },
              )
            }
          />
          Solo procesar cola tras cierre de mercado (17:35 Madrid)
        </label>

        <p className="text-xs text-muted-foreground">
          Por defecto solo se encolan valores que están en alguna lista
          (universo de rastreadores). El worker procesa ~1 valor cada 15 s + la
          pausa entre peticiones, y Yahoo lleva su propio throttle. Si falla un
          sync, el ítem reintenta con backoff. XTB no escribe histórico; solo
          cotización live / validación.
        </p>
      </section>

      <section
        className="space-y-3 border-t border-border/60 pt-3"
        aria-labelledby="sync-block-servidores"
      >
        <div>
          <h3 id="sync-block-servidores" className="text-sm font-medium">
            Comprobación de servidores
          </h3>
          <p className="text-xs text-muted-foreground">
            Mide conectividad de los proveedores habilitados. Solo prueba la
            conexión: no descarga datos.
          </p>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label="Comprobar servidores automáticamente"
            checked={draft.providerCheckEnabled}
            onChange={(event) =>
              setDraft((prev) =>
                prev === null
                  ? prev
                  : { ...prev, providerCheckEnabled: event.target.checked },
              )
            }
          />
          Comprobar servidores automáticamente
        </label>

        <div className="grid gap-3 md:grid-cols-2">
          {numberField("providerCheckIntervalSeconds", "Comprobar cada (s)")}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={checkNowMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
            onClick={() => void checkNowMutation.mutateAsync()}
          >
            <RefreshCw
              className={cn(
                "h-4 w-4",
                checkNowMutation.isPending && "animate-spin",
              )}
            />
            Comprobar ahora
          </button>
          {checkNote && (
            <span
              data-testid="provider-check-note"
              className="text-[11px] text-muted-foreground"
            >
              {checkNote}
            </span>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          {draft.providerCheckEnabled
            ? `El servidor comprueba cada ${draft.providerCheckIntervalSeconds} s aunque la app esté cerrada; si el bucle se detiene, el icono de la barra pasa a ámbar "stale".`
            : "Desactivada: no hay comprobaciones automáticas. El icono de la barra muestra la última medición guardada y «Comprobar ahora» sigue disponible."}
        </p>
      </section>

      {error && (
        <p role="alert" className="text-xs text-red-400">
          {error}
        </p>
      )}
      {updateMutation.isError && (
        <p role="alert" className="text-xs text-red-400">
          {updateMutation.error instanceof Error
            ? updateMutation.error.message
            : "No se pudo guardar la configuración"}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={updateMutation.isPending || error !== null || !dirty}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
          onClick={() => updateMutation.mutate(changes)}
        >
          <Save className="h-4 w-4" />
          {updateMutation.isPending ? "Guardando…" : "Guardar cambios"}
        </button>
        <button
          type="button"
          disabled={!dirty}
          className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
          onClick={() => setDraft(settings)}
        >
          Descartar
        </button>
        {!dirty && savedAt && (
          <span className="text-[11px] text-muted-foreground">
            Guardado {formatDateTime(savedAt)}
          </span>
        )}
        {dirty && !error && (
          <span className="text-[11px] text-amber-400">
            Cambios sin guardar
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
        <button
          type="button"
          disabled={enqueueMutation.isPending}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
          onClick={() => void enqueueMutation.mutateAsync()}
        >
          <RefreshCw
            className={cn(
              "h-4 w-4",
              enqueueMutation.isPending && "animate-spin",
            )}
          />
          Encolar valores desactualizados ahora
        </button>
        {enqueueNote && (
          <span
            data-testid="enqueue-note"
            className="text-[11px] text-muted-foreground"
          >
            {enqueueNote}
          </span>
        )}
      </div>

      {queue.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] text-muted-foreground">
            Pendientes: {counts.pending ?? 0} · Procesando:{" "}
            {counts.processing ?? 0} · Fallidos: {counts.failed ?? 0}
          </p>
          <div className="max-h-56 overflow-auto rounded border border-border">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-left">
                <tr>
                  <th className="px-2 py-1">Símbolo</th>
                  <th className="px-2 py-1">Estado</th>
                  <th className="px-2 py-1">Intentos</th>
                  <th className="hidden px-2 py-1 sm:table-cell">Programado</th>
                  <th className="px-2 py-1">Último error</th>
                </tr>
              </thead>
              <tbody>
                {queue.slice(0, 30).map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-2 py-1">{item.symbol}</td>
                    <td
                      className={cn("px-2 py-1", queueStatusTone(item.status))}
                    >
                      {queueStatusLabel(item.status)}
                    </td>
                    <td className="px-2 py-1">{item.attempts}</td>
                    <td className="hidden px-2 py-1 sm:table-cell">
                      {formatDateTime(item.scheduledAt)}
                    </td>
                    <td className="max-w-[16rem] truncate px-2 py-1 text-muted-foreground">
                      {item.lastError ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );

  if (embedded) {
    return <div className="space-y-4 text-sm">{body}</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Automatización de datos y servidores</CardTitle>
        <CardDescription>
          Dos automatizaciones distintas en una sola configuración: descarga de
          velas (histórico) y comprobación de conectividad de los servidores.
          Una no hace el trabajo de la otra.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">{body}</CardContent>
    </Card>
  );
}
