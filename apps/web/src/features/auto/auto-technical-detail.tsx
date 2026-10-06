/**
 * AUTO UI REFACTOR 3.0 (S3) — bloque «Detalle técnico» plegable.
 *
 * Separa el primer nivel (usuario) del vocabulario/densidad de ingeniería (spec 3.0 §1.8). Por
 * defecto va cerrado: el usuario no lo atraviesa para operar; el experto lo abre cuando lo pide.
 */

export function AutoTechnicalDetail({
  children,
  testId = "auto-technical-detail",
  label = "Detalle técnico",
}: {
  children: React.ReactNode;
  testId?: string;
  label?: string;
}) {
  return (
    <details
      className="rounded-lg border border-border bg-card"
      data-testid={testId}
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
