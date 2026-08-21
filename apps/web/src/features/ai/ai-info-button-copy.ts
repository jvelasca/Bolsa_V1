/**
 * CTA del diálogo IA: `supervised-f3` firma en Confirmar; el resto abre Ayuda.
 */

import { CONFIRMAR_LABEL } from "@/features/confirm/daily-nav";

export const AI_INFO_HELP_CTA_AYUDA = "Abrir Ayuda · Plataforma IA" as const;

/** `helpPanel === "supervised-f3"` → Confirmar; sin panel → Ayuda. */
export function aiInfoHelpCtaLabel(helpPanel?: "supervised-f3" | null): string {
  return helpPanel === "supervised-f3"
    ? `Abrir ${CONFIRMAR_LABEL}`
    : AI_INFO_HELP_CTA_AYUDA;
}
