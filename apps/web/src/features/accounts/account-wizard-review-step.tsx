/**
 * Paso «Revisión» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe las filas resumen ya resueltas por el orquestador. No contiene estado ni
 * lógica de negocio; solo renderiza la tabla de revisión previa a la creación.
 */
export function AccountWizardReviewStep({ rows }: { rows: [string, string][] }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-lg border border-border divide-y divide-border">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 px-3 py-2">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-medium text-right">{value}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Se creará la cuenta demo con cartera, depósito en el ledger, perfil inversor activo y preset
        de comisiones/fiscal.
      </p>
    </div>
  );
}
