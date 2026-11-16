/**
 * Hub de la puerta ASESOR (`/research`) — A1 del refactor.
 *
 * Cuatro pestañas visibles (`Cartera`, `Análisis`, `Diario`, `Laboratorio`) y dos
 * ids de compatibilidad que NO se pintan como botón:
 * - `history` es un alias de `dashboard`: ambos montan el resumen corto del
 *   Laboratorio. El historial de experimentos y su detalle viven en `/backtests`
 *   (R5 · una sola puerta); los enlaces antiguos con `trialId` se redirigen allí.
 * - `journal` monta la tarjeta puente histórica; el Journal ya no es pestaña.
 *
 * Los seis ids internos se conservan porque los consumen `app-top-bar.tsx`,
 * `alert-toasts.tsx`, `daily-nav.ts` y el E2E.
 *
 * @see docs/adr/040-user-information-architecture.md
 * @see docs/engineering/auditoria-operativa-asesor-2026-11-15.md §8 (slice A1)
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Ids internos del hub (se conservan uno a uno; ver el encabezado). */
export type HubTab =
  | "cartera"
  | "dashboard"
  | "diario"
  | "history"
  | "opiniones"
  | "journal";

/**
 * Parsea el parámetro `?tab=`.
 *
 * Acepta los seis ids históricos y normaliza cualquier valor desconocido al
 * destino por defecto, que en A1 pasa a ser `cartera` (la pestaña que responde
 * «¿qué tengo?» sin plegar sus métricas tras un detalle técnico).
 */
export function parseTab(raw: string | null): HubTab {
  if (raw === "cartera") return "cartera";
  if (raw === "history") return "history";
  if (raw === "opiniones") return "opiniones";
  if (raw === "diario") return "diario";
  if (raw === "journal") return "journal";
  if (raw === "dashboard") return "dashboard";
  return "cartera";
}

/**
 * `dashboard` y `history` son el mismo destino visible: el Laboratorio, que
 * fusiona el resumen del laboratorio con el historial de experimentos.
 */
export function isLabTab(tab: HubTab): boolean {
  return tab === "dashboard" || tab === "history";
}

/**
 * Botón de pestaña del hub. Conserva el estilo visual previo; añade la semántica
 * de pestañas que faltaba (`role="tab"` + `aria-selected`, dentro del `tablist`).
 */
export function HubTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium",
        active
          ? "bg-accent text-primary"
          : "text-muted-foreground hover:bg-accent/50",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Barra de pestañas del hub ASESOR.
 *
 * Orden visible: Cartera · Análisis · Diario · Laboratorio. El Journal vive como
 * enlace en el encabezado de la página y `?tab=journal` sigue montando su tarjeta
 * puente, pero no aparece como pestaña.
 */
export function AsesorHubTabsBar({
  tab,
  onTab,
}: {
  tab: HubTab;
  onTab: (next: HubTab) => void;
}) {
  return (
    <div
      className="flex flex-wrap gap-2"
      role="tablist"
      aria-label="Secciones de Asesor"
    >
      <HubTabButton active={tab === "cartera"} onClick={() => onTab("cartera")}>
        Cartera
      </HubTabButton>
      <HubTabButton
        active={tab === "opiniones"}
        onClick={() => onTab("opiniones")}
      >
        Análisis
      </HubTabButton>
      <HubTabButton active={tab === "diario"} onClick={() => onTab("diario")}>
        Diario
      </HubTabButton>
      <HubTabButton active={isLabTab(tab)} onClick={() => onTab("dashboard")}>
        Laboratorio
      </HubTabButton>
    </div>
  );
}
