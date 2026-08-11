import type { CommissionPresetId, TradeFeeBreakdownDto } from "@bolsa/shared";
import { COMMISSION_PRESETS } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

const COMMISSION_OPTIONS: { id: CommissionPresetId; hint: string }[] = [
  {
    id: "standard_es",
    hint: "0,10 % · mín. 1 € · IVA 21 % · custodia 0,2 % anual",
  },
  { id: "xtb_zero_stock", hint: "0 % comisión en acciones · FX 0,5 %" },
  { id: "ibkr_tiered", hint: "0,05 % · mín. 1,25 € · IVA 21 %" },
  { id: "none", hint: "Sin comisiones ni impuestos simulados" },
];

/**
 * Paso «Comisiones» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe la selección actual, el callback `onPatch` y el desglose de comisiones
 * de ejemplo ya calculado por el orquestador. La lógica de cálculo vive en `CreateAccountWizardDialog`.
 */
export function AccountWizardCommissionsStep({
  commissionPresetId,
  sampleFees,
  onPatch,
}: {
  commissionPresetId: CommissionPresetId;
  sampleFees: TradeFeeBreakdownDto;
  onPatch: (
    values: Partial<{ commissionPresetId: CommissionPresetId }>,
  ) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Perfil de comisiones simuladas. Se aplican en cada operación y se
        registran en el ledger.
      </p>
      {COMMISSION_OPTIONS.map(({ id, hint }) => {
        const preset =
          COMMISSION_PRESETS[id as keyof typeof COMMISSION_PRESETS];
        if (!preset && id !== "custom") return null;
        const label =
          id === "standard_es"
            ? COMMISSION_PRESETS.standard_es.label
            : (preset?.label ?? id);
        return (
          <label
            key={id}
            className={cn(
              "flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors",
              commissionPresetId === id
                ? "border-primary bg-primary/5"
                : "border-border hover:bg-accent/40",
            )}
          >
            <input
              type="radio"
              name="commissionPreset"
              checked={commissionPresetId === id}
              onChange={() => onPatch({ commissionPresetId: id })}
              className="mt-1"
            />
            <div>
              <p className="text-sm font-medium">{label}</p>
              <p className="text-xs text-muted-foreground">{hint}</p>
            </div>
          </label>
        );
      })}
      <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">Ejemplo compra 5.000 €</p>
        <p className="mt-1 tabular-nums">
          Comisión {formatPrice(sampleFees.commission)} · IVA{" "}
          {formatPrice(sampleFees.vatOnCommission)} · Transmisiones{" "}
          {formatPrice(sampleFees.stampDuty)} ·{" "}
          <span className="font-medium text-foreground">
            Total {formatPrice(sampleFees.total)}
          </span>
        </p>
      </div>
    </div>
  );
}
