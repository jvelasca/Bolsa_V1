/**
 * Apertura del panel lateral Confirmar (U3) sin salir de la mesa Trading.
 *
 * No sustituye la ruta `/confirm` (deep-link / nav primer nivel).
 * El host escucha `BOLSA_CONFIRM_DRAWER_EVENT` y monta el mismo contenido SEMI.
 *
 * @see apps/web/src/features/confirm/confirm-drawer-host.tsx
 */

import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { setChartSignedStopPrefill } from "@/features/charts/chart-signed-stop-prefill";

/** Evento SPA: abrir/cerrar el drawer Confirmar. */
export const BOLSA_CONFIRM_DRAWER_EVENT = "bolsa:confirm-drawer" as const;

export type ConfirmDrawerDetail = {
  open: boolean;
  /** V1.34 B-γ — prefill stop firmado desde drag del gráfico. */
  signedStop?: number;
  instrumentId?: string;
};

/** Label del CTA en Operativa (abre drawer, no navega). */
export const CONFIRM_DRAWER_CTA_LABEL = "Cola Confirm" as const;

/** Link a la página completa desde el drawer. */
export const CONFIRM_FULL_PAGE_LINK_LABEL = "Abrir página completa" as const;

export type OpenConfirmDrawerOptions = {
  signedStop?: number;
  instrumentId?: string;
};

/**
 * True si el detalle del evento pide abrir el drawer.
 */
export function isConfirmDrawerOpenDetail(
  detail: unknown,
): detail is ConfirmDrawerDetail & { open: true } {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as ConfirmDrawerDetail).open === true
  );
}

/**
 * True si el detalle pide cerrar (open === false).
 */
export function isConfirmDrawerCloseDetail(
  detail: unknown,
): detail is ConfirmDrawerDetail & { open: false } {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as ConfirmDrawerDetail).open === false
  );
}

/** Dispara apertura del drawer (host en PlatformShell). */
export function openConfirmDrawer(opts?: OpenConfirmDrawerOptions): void {
  if (
    opts?.signedStop != null &&
    Number.isFinite(opts.signedStop) &&
    opts.signedStop > 0 &&
    opts.instrumentId
  ) {
    setChartSignedStopPrefill({
      instrumentId: opts.instrumentId,
      signedStop: opts.signedStop,
    });
  }
  const detail: ConfirmDrawerDetail = { open: true };
  if (opts?.signedStop != null && Number.isFinite(opts.signedStop)) {
    detail.signedStop = opts.signedStop;
  }
  if (opts?.instrumentId) detail.instrumentId = opts.instrumentId;
  window.dispatchEvent(new CustomEvent(BOLSA_CONFIRM_DRAWER_EVENT, { detail }));
}

/** Cierra el drawer si está abierto. */
export function closeConfirmDrawer(): void {
  window.dispatchEvent(
    new CustomEvent(BOLSA_CONFIRM_DRAWER_EVENT, {
      detail: { open: false } satisfies ConfirmDrawerDetail,
    }),
  );
}

/**
 * Texto del botón Operativa con conteo opcional de cola.
 */
export function formatConfirmDrawerCtaLabel(queueCount: number): string {
  if (queueCount <= 0) return CONFIRM_DRAWER_CTA_LABEL;
  return `${CONFIRM_DRAWER_CTA_LABEL} (${queueCount})`;
}

/** Ruta de la página completa (mismo contrato SEMI). */
export function confirmFullPagePath(): typeof CONFIRM_PATH {
  return CONFIRM_PATH;
}
