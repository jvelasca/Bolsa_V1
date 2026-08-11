import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const CURRENCIES = ["EUR", "USD", "GBP"] as const;

/**
 * Paso «Identidad» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe solo el estado del formulario que necesita + `onPatch`. La lógica de
 * estado/navegación/creación vive en el orquestador `CreateAccountWizardDialog`. Se traslada
 * fielmente el bloque `<div className="space-y-4">` original del paso identity.
 */
export function AccountWizardIdentityStep({
  name,
  description,
  currency,
  onPatch,
}: {
  name: string;
  description: string;
  currency: string;
  onPatch: (values: {
    name?: string;
    description?: string;
    currency?: string;
  }) => void;
}) {
  return (
    <div className="space-y-4">
      <FieldRow
        label="Nombre de la cuenta"
        hint="Ej. Paper IBEX, Estrategia dividendos"
      >
        <input
          className={inputClassName}
          value={name}
          onChange={(e) => onPatch({ name: e.target.value })}
          placeholder="Cuenta demo EUR"
          autoFocus
        />
      </FieldRow>
      <FieldRow label="Descripción (opcional)">
        <textarea
          className={cn(inputClassName, "min-h-[72px] resize-y")}
          value={description}
          onChange={(e) => onPatch({ description: e.target.value })}
          placeholder="Objetivo, horizonte, notas…"
        />
      </FieldRow>
      <FieldRow label="Moneda de la cuenta">
        <select
          className={inputClassName}
          value={currency}
          onChange={(e) => onPatch({ currency: e.target.value })}
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </FieldRow>
    </div>
  );
}
