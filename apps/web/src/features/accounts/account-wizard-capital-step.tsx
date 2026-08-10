import { FieldRow, inputClassName } from '@/components/ui/dialog';

/**
 * Paso «Capital» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe solo los tres campos de capital + `onPatch`. La lógica de estado se
 * orquesta en `CreateAccountWizardDialog`. Traslada fielmente el bloque original del paso capital.
 */
export function AccountWizardCapitalStep({
  initialDeposit,
  leverage,
  marginCallLevelPct,
  onPatch,
}: {
  initialDeposit: string;
  leverage: string;
  marginCallLevelPct: string;
  onPatch: (values: {
    initialDeposit?: string;
    leverage?: string;
    marginCallLevelPct?: string;
  }) => void;
}) {
  return (
    <div className="space-y-4">
      <FieldRow label="Depósito inicial" hint="Efectivo disponible al abrir la cuenta">
        <input
          type="number"
          min={0}
          step={1000}
          className={inputClassName}
          value={initialDeposit}
          onChange={(e) => onPatch({ initialDeposit: e.target.value })}
        />
      </FieldRow>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldRow label="Apalancamiento" hint="1 = sin apalancamiento (recomendado)">
          <input
            type="number"
            min={1}
            max={10}
            step={0.5}
            className={inputClassName}
            value={leverage}
            onChange={(e) => onPatch({ leverage: e.target.value })}
          />
        </FieldRow>
        <FieldRow label="Nivel margin call (%)" hint="Alerta cuando margen caiga bajo este umbral">
          <input
            type="number"
            min={50}
            max={200}
            className={inputClassName}
            value={marginCallLevelPct}
            onChange={(e) => onPatch({ marginCallLevelPct: e.target.value })}
          />
        </FieldRow>
      </div>
      <p className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        Cuenta simulada: el apalancamiento afectará al cálculo de margen en fases posteriores. Por
        ahora el trading opera con efectivo disponible.
      </p>
    </div>
  );
}
