/**
 * Página Confirmar (R-12 C1).
 *
 * Primer nivel de firma: reutiliza `ConfirmContent` → `SupervisedF3Panel`.
 * No reescribe la cola. Destino deep-link `/confirm` y nav primer nivel.
 * Desde Trading/Operativa también hay slide-over (U3) sin salir de la mesa.
 *
 * @see docs/engineering/plan-r12-track-c-frontend-2026-08-21.md § C1
 */

import { FeatureErrorBoundary } from "@/components/layout/feature-error-boundary";
import { ConfirmContent } from "@/features/confirm/confirm-content";

export function ConfirmPage() {
  return (
    <FeatureErrorBoundary
      featureName="Confirmar"
      fallbackMessage="No se pudo mostrar Confirm. Tus posiciones siguen intactas; reintenta o usa el libro."
    >
      <div className="mx-auto max-w-5xl">
        <ConfirmContent />
      </div>
    </FeatureErrorBoundary>
  );
}
