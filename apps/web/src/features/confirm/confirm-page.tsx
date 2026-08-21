/**
 * Página Confirmar (R-12 C1).
 *
 * Primer nivel de firma: reutiliza `SupervisedF3Panel` (cola F3 existente).
 * No reescribe la cola. Destino de `openHelpAiPlatform({ panel: "supervised-f3" })`.
 *
 * @see docs/engineering/plan-r12-track-c-frontend-2026-08-21.md § C1
 */

import { SupervisedF3Panel } from "@/features/settings/supervised-f3-panel";

export function ConfirmPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Confirmar</h2>
        <p className="text-sm text-muted-foreground">
          La app propone operaciones sobre tu Universo. Tú las firmas aquí.
          Nunca se envían solas.
        </p>
      </div>
      <SupervisedF3Panel />
    </div>
  );
}
