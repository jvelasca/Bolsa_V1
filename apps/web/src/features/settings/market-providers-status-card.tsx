import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlugZap, Save } from "lucide-react";
import type { MarketProviderStatusDto } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/format";

const PRIORITY_MIN = 0;
const PRIORITY_MAX = 100;
const INTERVAL_MIN = 0;
const INTERVAL_MAX = 120;

export const PROVIDERS_QUERY_KEY = ["market-providers"] as const;

type ProviderDraft = {
  priority: number;
  minIntervalSeconds: number;
  baseUrl: string;
};

function draftFrom(provider: MarketProviderStatusDto): ProviderDraft {
  return {
    priority: provider.priority ?? 0,
    minIntervalSeconds: provider.minIntervalSeconds ?? 0,
    baseUrl: provider.baseUrl ?? "",
  };
}

function providerStateLabel(provider: MarketProviderStatusDto): string {
  if (!provider.enabled) return "Deshabilitado";
  if (provider.id === "xtb" && !provider.baseUrl) return "Sin URL de bridge";
  if (!provider.verified) return "Sin verificar";
  return provider.healthy ? "Disponible" : "Sin respuesta";
}

function providerStateTone(provider: MarketProviderStatusDto): string {
  if (!provider.enabled) return "text-muted-foreground";
  if (provider.id === "xtb" && !provider.baseUrl) return "text-amber-400";
  if (!provider.verified) return "text-muted-foreground";
  return provider.healthy ? "text-emerald-400" : "text-red-400";
}

function validationError(
  provider: MarketProviderStatusDto,
  draft: ProviderDraft,
) {
  if (draft.priority < PRIORITY_MIN || draft.priority > PRIORITY_MAX) {
    return `Prioridad fuera de rango (${PRIORITY_MIN}–${PRIORITY_MAX}).`;
  }
  if (
    draft.minIntervalSeconds < INTERVAL_MIN ||
    draft.minIntervalSeconds > INTERVAL_MAX
  ) {
    return `Intervalo fuera de rango (${INTERVAL_MIN}–${INTERVAL_MAX} s).`;
  }
  const url = draft.baseUrl.trim();
  if (provider.id === "xtb" && url && !/^https?:\/\/[^\s/]+/.test(url)) {
    return "La URL del bridge debe empezar por http:// o https://.";
  }
  return null;
}

function ProviderCard({ provider }: { provider: MarketProviderStatusDto }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ProviderDraft>(() => draftFrom(provider));
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [probe, setProbe] = useState<{ ok: boolean; message: string } | null>(
    null,
  );

  // La respuesta del servidor es la fuente de verdad: tras guardar o probar, el borrador
  // se reajusta a lo persistido en vez de mantener un valor optimista.
  useEffect(() => {
    setDraft(draftFrom(provider));
  }, [provider]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: PROVIDERS_QUERY_KEY });

  const updateMutation = useMutation({
    mutationFn: (body: Parameters<typeof api.updateMarketProvider>[1]) =>
      api.updateMarketProvider(provider.id, body),
    onSuccess: () => {
      setSavedAt(new Date().toISOString());
      void invalidate();
    },
  });

  const testMutation = useMutation({
    mutationFn: () => api.testMarketProvider(provider.id),
    onSuccess: (response) => {
      setProbe({ ok: response.data.ok, message: response.data.message });
      void invalidate();
    },
    onError: (error: unknown) => {
      setProbe({
        ok: false,
        message:
          error instanceof Error
            ? error.message
            : "Error al probar el proveedor",
      });
    },
  });

  const error = validationError(provider, draft);
  const capabilities = provider.capabilities ?? [];
  const urlChanged = draft.baseUrl.trim() !== (provider.baseUrl ?? "");

  return (
    <Card data-testid={`provider-card-${provider.id}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          {provider.label}
          <span
            data-testid={`provider-state-${provider.id}`}
            className={cn("text-xs font-normal", providerStateTone(provider))}
          >
            {providerStateLabel(provider)}
          </span>
        </CardTitle>
        <CardDescription>
          {provider.description || provider.message}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-xs text-muted-foreground">{provider.message}</p>

        <p
          className="text-[11px] text-muted-foreground"
          data-testid={`provider-last-check-${provider.id}`}
        >
          {provider.lastCheckAt
            ? `Última comprobación: ${formatDateTime(provider.lastCheckAt)}${
                provider.lastCheckOk === false ? " (sin respuesta)" : ""
              }`
            : "Sin comprobar todavía: «Sin verificar» no es «disponible»."}
          {" · Cadencia en «Comprobación de servidores»."}
        </p>

        {capabilities.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Capacidades">
            {capabilities.map((capability) => (
              <li
                key={capability}
                className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground"
              >
                {capability}
              </li>
            ))}
          </ul>
        )}

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label={`Habilitar ${provider.label}`}
            checked={provider.enabled}
            disabled={updateMutation.isPending}
            onChange={(event) =>
              updateMutation.mutate({ enabled: event.target.checked })
            }
          />
          Usar este proveedor
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">
              Prioridad (menor = antes)
            </span>
            <input
              type="number"
              min={PRIORITY_MIN}
              max={PRIORITY_MAX}
              aria-label={`Prioridad de ${provider.label}`}
              className="rounded border border-border bg-background px-2 py-1"
              value={draft.priority}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  priority: Number(event.target.value),
                }))
              }
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">
              Intervalo mínimo entre peticiones (s)
            </span>
            <input
              type="number"
              min={INTERVAL_MIN}
              max={INTERVAL_MAX}
              aria-label={`Intervalo de ${provider.label}`}
              className="rounded border border-border bg-background px-2 py-1"
              value={draft.minIntervalSeconds}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  minIntervalSeconds: Number(event.target.value),
                }))
              }
            />
          </label>
        </div>

        {provider.id === "xtb" && (
          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">URL del bridge</span>
            <input
              type="url"
              placeholder="http://127.0.0.1:3002"
              aria-label="URL del bridge XTB"
              className="rounded border border-border bg-background px-2 py-1"
              value={draft.baseUrl}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, baseUrl: event.target.value }))
              }
            />
            <span className="text-[11px] text-muted-foreground">
              {provider.baseUrlSource === "env"
                ? "Ahora mismo se usa la URL del entorno (XTB_BRIDGE_URL)."
                : provider.baseUrlSource === "config"
                  ? "URL guardada en Configuración."
                  : "Sin URL: el bridge no se consultará."}
            </span>
          </label>
        )}

        {error && (
          <p role="alert" className="text-xs text-red-400">
            {error}
          </p>
        )}
        {updateMutation.isError && (
          <p role="alert" className="text-xs text-red-400">
            {updateMutation.error instanceof Error
              ? updateMutation.error.message
              : "No se pudo guardar el proveedor"}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
            disabled={updateMutation.isPending || error !== null}
            onClick={() =>
              updateMutation.mutate({
                priority: draft.priority,
                minIntervalSeconds: draft.minIntervalSeconds,
                ...(provider.id === "xtb"
                  ? { baseUrl: draft.baseUrl.trim() || null }
                  : {}),
              })
            }
          >
            <Save className="h-4 w-4" />
            Guardar
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 hover:bg-accent disabled:opacity-50"
            disabled={testMutation.isPending || !provider.enabled}
            onClick={() => testMutation.mutate()}
          >
            <PlugZap className="h-4 w-4" />
            {testMutation.isPending ? "Probando…" : "Probar conexión"}
          </button>
          {savedAt && (
            <span className="text-[11px] text-muted-foreground">
              Guardado {formatDateTime(savedAt)}
            </span>
          )}
        </div>

        {urlChanged && provider.id === "xtb" && (
          <p className="text-[11px] text-amber-400">
            Hay cambios de URL sin guardar: pulsa Guardar para aplicarlos.
          </p>
        )}

        {probe && (
          <p
            data-testid={`provider-probe-${provider.id}`}
            className={cn(
              "text-xs",
              probe.ok ? "text-emerald-400" : "text-red-400",
            )}
          >
            {probe.ok ? "Conexión OK" : "Conexión fallida"}: {probe.message}
          </p>
        )}

        <p className="text-[11px] text-muted-foreground">
          {provider.verified && provider.lastCheckAt
            ? `Última verificación: ${formatDateTime(provider.lastCheckAt)}`
            : "Sin verificación registrada todavía."}
        </p>
      </CardContent>
    </Card>
  );
}

/** Estado y configuración de los proveedores de datos — Config → Sync / proveedores. */
export function MarketProvidersStatusCard() {
  const marketQuery = useQuery({
    queryKey: PROVIDERS_QUERY_KEY,
    queryFn: api.getMarketProviders,
    refetchInterval: 60_000,
  });

  const providers = marketQuery.data?.data ?? [];

  if (marketQuery.isLoading) {
    return (
      <p className="text-sm text-muted-foreground">Comprobando proveedores…</p>
    );
  }
  if (marketQuery.isError) {
    return (
      <p className="text-sm text-red-400">
        No se pudo leer el estado de los proveedores:{" "}
        {marketQuery.error instanceof Error
          ? marketQuery.error.message
          : "error desconocido"}
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {providers.map((provider) => (
        <ProviderCard key={provider.id} provider={provider} />
      ))}
    </div>
  );
}
