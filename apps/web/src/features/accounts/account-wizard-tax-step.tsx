import type { TaxJurisdiction } from "@bolsa/shared";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Paso «Fiscal» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe los campos fiscales + `onPatch` + `onJurisdictionChange`. La lógica de
 * aplicar el preset al cambiar jurisdicción se orquesta en `CreateAccountWizardDialog` para
 * mantener el componente sin efectos de negocio.
 */
export function AccountWizardTaxStep({
  taxJurisdiction,
  costBasisMethod,
  stampDutyBuyPct,
  dividendWithholdingPct,
  notes,
  onPatch,
  onJurisdictionChange,
}: {
  taxJurisdiction: TaxJurisdiction;
  costBasisMethod: "fifo" | "average";
  stampDutyBuyPct: string;
  dividendWithholdingPct: string;
  notes: string;
  onPatch: (values: {
    taxJurisdiction?: TaxJurisdiction;
    costBasisMethod?: "fifo" | "average";
    stampDutyBuyPct?: string;
    dividendWithholdingPct?: string;
    notes?: string;
  }) => void;
  onJurisdictionChange: (value: TaxJurisdiction) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Parámetros fiscales para simulación y futuros informes. No constituyen
        asesoramiento fiscal.
      </p>
      <FieldRow label="Jurisdicción fiscal">
        <select
          className={inputClassName}
          value={taxJurisdiction}
          onChange={(e) =>
            onJurisdictionChange(e.target.value as TaxJurisdiction)
          }
        >
          <option value="ES">España (ES)</option>
          <option value="EU_OTHER">Unión Europea (otro)</option>
          <option value="US">Estados Unidos</option>
          <option value="CUSTOM">Personalizado</option>
        </select>
      </FieldRow>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldRow
          label="Método de coste"
          hint="FIFO recomendado para fiscalidad ES"
        >
          <select
            className={inputClassName}
            value={costBasisMethod}
            onChange={(e) =>
              onPatch({ costBasisMethod: e.target.value as "fifo" | "average" })
            }
          >
            <option value="fifo">FIFO (primero en entrar)</option>
            <option value="average">Coste medio ponderado</option>
          </select>
        </FieldRow>
        <FieldRow
          label="Imp. transmisiones compra (%)"
          hint="España acciones ~0,2 %"
        >
          <input
            type="number"
            min={0}
            step={0.01}
            className={inputClassName}
            value={stampDutyBuyPct}
            onChange={(e) => onPatch({ stampDutyBuyPct: e.target.value })}
          />
        </FieldRow>
        <FieldRow
          label="Retención dividendos (%)"
          hint="Referencia IRPF / doble imposición"
        >
          <input
            type="number"
            min={0}
            step={0.5}
            className={inputClassName}
            value={dividendWithholdingPct}
            onChange={(e) =>
              onPatch({ dividendWithholdingPct: e.target.value })
            }
          />
        </FieldRow>
      </div>
      <FieldRow label="Notas internas (opcional)">
        <textarea
          className={cn(inputClassName, "min-h-[56px] resize-y")}
          value={notes}
          onChange={(e) => onPatch({ notes: e.target.value })}
        />
      </FieldRow>
    </div>
  );
}
