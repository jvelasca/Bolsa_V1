import type { TaxJurisdiction, TaxProfile } from "@bolsa/shared";
import { COST_BASIS_LABELS, TAX_JURISDICTION_LABELS } from "@bolsa/shared";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const MONTHS = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

function pct(value: number): string {
  return `${String(Number(value.toFixed(4))).replace(".", ",")} %`;
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums text-foreground">{value}</span>
    </div>
  );
}

/**
 * Paso «Fiscal» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe los campos fiscales + `onPatch` + `onJurisdictionChange`. La lógica de
 * aplicar el preset al cambiar jurisdicción se orquesta en `CreateAccountWizardDialog` para
 * mantener el componente sin efectos de negocio.
 *
 * El bloque «Lo que aplicará el servidor» se deriva del perfil ya resuelto (`tax`), no de
 * una copia de los presets: el wizard enseñaba solo dos campos editables y el usuario no
 * veía el tipo de plusvalías ni el inicio del ejercicio que el backend usa de verdad.
 */
export function AccountWizardTaxStep({
  taxJurisdiction,
  costBasisMethod,
  stampDutyBuyPct,
  dividendWithholdingPct,
  tax,
  notes,
  onPatch,
  onJurisdictionChange,
}: {
  taxJurisdiction: TaxJurisdiction;
  costBasisMethod: "fifo" | "average";
  stampDutyBuyPct: string;
  dividendWithholdingPct: string;
  /** Perfil fiscal resuelto (preset de la jurisdicción + overrides del formulario). */
  tax: TaxProfile;
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
  const startMonth =
    MONTHS[(tax.fiscalYearStartMonth ?? 1) - 1] ??
    `mes ${tax.fiscalYearStartMonth}`;
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
          data-testid="wizard-tax-jurisdiction"
          onChange={(e) =>
            onJurisdictionChange(e.target.value as TaxJurisdiction)
          }
        >
          {(Object.keys(TAX_JURISDICTION_LABELS) as TaxJurisdiction[]).map(
            (id) => (
              <option key={id} value={id}>
                {TAX_JURISDICTION_LABELS[id]}
              </option>
            ),
          )}
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
            {(Object.keys(COST_BASIS_LABELS) as ("fifo" | "average")[]).map(
              (id) => (
                <option key={id} value={id}>
                  {COST_BASIS_LABELS[id]}
                </option>
              ),
            )}
          </select>
        </FieldRow>
        <FieldRow
          label="Imp. transmisiones compra (%)"
          hint="España acciones ~0,2 %; se cobra en cada compra aunque el preset de comisión sea «sin comisiones»"
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

      <div
        className="rounded-md border border-border bg-muted/20 p-3 text-xs"
        data-testid="wizard-tax-summary"
      >
        <p className="font-medium text-foreground">
          Lo que aplicará el servidor
        </p>
        <div className="mt-2 space-y-1">
          <SummaryRow
            label="Tipo sobre plusvalías"
            value={
              tax.capitalGainsTaxPct != null && tax.capitalGainsTaxPct > 0
                ? `${pct(tax.capitalGainsTaxPct)} · proyección del informe`
                : "No se estima"
            }
          />
          <SummaryRow
            label="Retención de dividendos"
            value={pct(tax.dividendWithholdingPct)}
          />
          <SummaryRow
            label="Transmisiones (solo compras)"
            value={pct(tax.stampDutyBuyPct)}
          />
          <SummaryRow
            label="Ejercicio fiscal"
            value={`Desde el 1 de ${startMonth}`}
          />
        </div>
        <p className="mt-2 text-[10px] text-muted-foreground">
          El tipo sobre plusvalías es una orientación de un solo tramo; el IRPF
          del ahorro real es progresivo.
        </p>
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
