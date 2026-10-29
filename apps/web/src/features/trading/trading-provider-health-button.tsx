/**
 * Icono «servidores de datos» de la barra de estado del terminal Mercado.
 *
 * Verde si todos los proveedores HABILITADOS están medidos y OK · rojo si alguno de
 * ellos ha caído · ámbar si falta medir, hay una sonda en curso o la última medición ya
 * no se refresca (`stale`: la comprobación automática está ON pero su bucle no corre) ·
 * gris si no hay ninguno habilitado. Un proveedor deshabilitado a propósito NO pinta
 * rojo: se declara en el tooltip.
 *
 * La cadencia del poll se deriva de la política publicada por el backend (060): nunca se
 * duplica un «60 s» en el cliente. Con la comprobación automática OFF se consulta despacio
 * (no hay nada que refrescar solo).
 *
 * Clic → Configuración · Sync / proveedores.
 *
 * @see docs/engineering/seguimiento-ui-proveedores-2026-10-29.md
 */

import { useQuery } from "@tanstack/react-query";
import { Server } from "lucide-react";

import { api } from "@/lib/api";
import { formatDateTimeShort } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import type {
  ProviderHealthStatus,
  ProviderHealthSummaryDto,
} from "@bolsa/shared";

/** Cadencia de consulta del icono: ni más de 60 s ni menos de 15 s. */
const PROVIDER_HEALTH_POLL_MIN_MS = 15_000;
const PROVIDER_HEALTH_POLL_MAX_MS = 60_000;
/** Con la comprobación automática OFF no hay nada que refrescar: se consulta despacio. */
export const PROVIDER_HEALTH_POLL_OFF_MS = 120_000;

type Props = {
  className?: string;
};

function toneDotClass(status: ProviderHealthStatus): string {
  if (status === "ok") return "bg-emerald-500";
  if (status === "degraded") return "bg-rose-500";
  if (status === "unverified" || status === "stale") return "bg-amber-500";
  return "bg-muted-foreground/50";
}

function toneTextClass(status: ProviderHealthStatus): string {
  if (status === "ok") return "text-emerald-700 dark:text-emerald-300";
  if (status === "degraded") return "text-rose-700 dark:text-rose-300";
  if (status === "unverified" || status === "stale")
    return "text-amber-700 dark:text-amber-300";
  return "text-muted-foreground";
}

const STATUS_HEADLINE: Record<ProviderHealthStatus, string> = {
  ok: "Servidores de datos verificados",
  degraded: "Algún servidor de datos ha caído",
  stale: "La comprobación automática no está refrescando la medición",
  unverified: "Sin medición reciente de los servidores de datos",
  none: "Sin servidores de datos habilitados",
};

/** Intervalo de poll derivado de la política del backend (mismo número, no una copia). */
export function healthPollIntervalMs(
  summary?: ProviderHealthSummaryDto,
): number {
  if (summary?.autoCheckEnabled === false) return PROVIDER_HEALTH_POLL_OFF_MS;
  const intervalMs = (summary?.checkIntervalSeconds ?? 60) * 1_000;
  return Math.min(
    PROVIDER_HEALTH_POLL_MAX_MS,
    Math.max(PROVIDER_HEALTH_POLL_MIN_MS, Math.round(intervalMs / 2)),
  );
}

function policyNote(summary?: ProviderHealthSummaryDto): string {
  if (summary?.autoCheckEnabled === false) {
    return "Comprobación automática desactivada: se muestra la última medición guardada.";
  }
  const seconds = summary?.checkIntervalSeconds ?? 60;
  const next = summary?.nextCheckAt
    ? `; próxima ${formatDateTimeShort(summary.nextCheckAt)}`
    : "";
  return `Se comprueba cada ${seconds} s${next}.`;
}

export function TradingProviderHealthButton({ className }: Props) {
  const openPlatformConfig = useUiStore((s) => s.openPlatformConfig);
  const healthQuery = useQuery({
    queryKey: ["provider-health"],
    queryFn: async () => (await api.getProviderHealth()).data,
    refetchInterval: (query) => healthPollIntervalMs(query.state.data),
    staleTime: 15_000,
    retry: 1,
  });

  const summary = healthQuery.data;
  // Sin dato todavía: no se afirma nada (ámbar), nunca verde por optimismo.
  const status: ProviderHealthStatus = summary?.status ?? "unverified";
  const probing = summary?.probing === true && status !== "ok";
  const detail = [
    STATUS_HEADLINE[status],
    ...(summary?.providers ?? []).map((provider) =>
      provider.enabled
        ? `${provider.label}: ${provider.message}`
        : `${provider.label}: deshabilitado (no cuenta para el veredicto)`,
    ),
    summary?.measuredAt
      ? `Última medición: ${formatDateTimeShort(summary.measuredAt)}`
      : null,
    probing ? "Comprobando ahora…" : null,
    policyNote(summary),
    status === "stale"
      ? "Ámbar «stale»: hay medición, pero más antigua que la cadencia declarada; el bucle no está corriendo."
      : null,
    "Clic → Configuración · Sync / proveedores",
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <button
      type="button"
      className={cn(
        "flex h-5 shrink-0 items-center gap-1 rounded px-0.5 text-[10px] hover:bg-accent",
        toneTextClass(status),
        className,
      )}
      title={detail}
      aria-label={`Servidores de datos: ${STATUS_HEADLINE[status]}. Abrir configuración de proveedores`}
      data-testid="status-bar-provider-health"
      data-tone={status}
      data-probing={probing ? "1" : "0"}
      onClick={() => openPlatformConfig("other")}
    >
      <Server className="h-3 w-3 shrink-0 opacity-80" aria-hidden />
      <span
        className={cn(
          "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
          toneDotClass(status),
          probing && "animate-pulse",
        )}
        aria-hidden
      />
    </button>
  );
}
