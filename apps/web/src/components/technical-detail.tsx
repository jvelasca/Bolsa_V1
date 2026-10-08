/**
 * UI Contract 5.0 (`RT-04`, enmienda UI 6.x) — mecanismo ÚNICO de profundidad.
 *
 * Todo el vocabulario de ingeniería (identificadores de modelo, sesiones, gates, ledger,
 * fills, trials, params crudos…) vive detrás de este disclosure. Por defecto va cerrado:
 * el usuario básico no lo atraviesa para operar; el experto lo abre cuando lo pide.
 *
 * No se crean disclosures paralelos: el rótulo es siempre `Detalle técnico`.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md (RT-04, R-G1)
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md
 */

import { cn } from "@/lib/utils";

/** Rótulo único de nivel 3 (auditoría). */
export const TECHNICAL_DETAIL_LABEL = "Detalle técnico";

/** Marca DOM para que el gate falsable localice el contenido de nivel 3. */
export const TECHNICAL_DETAIL_ATTR = "data-technical-detail";

export function TechnicalDetail({
  children,
  testId = "technical-detail",
  label = TECHNICAL_DETAIL_LABEL,
  className,
}: {
  children: React.ReactNode;
  testId?: string;
  label?: string;
  className?: string;
}) {
  return (
    <details
      className={cn("rounded-lg border border-border bg-card", className)}
      data-testid={testId}
      data-technical-detail="true"
    >
      <summary className="cursor-pointer px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </summary>
      <div className="space-y-4 border-t border-border p-4 text-xs">
        {children}
      </div>
    </details>
  );
}
