import type { CommissionPresetId, TradeFeeBreakdownDto } from "@bolsa/shared";
import {
  COMMISSION_PRESET_IDS,
  commissionPresetLabel,
  describeCommissionPreset,
} from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

/**
 * Paso «Comisiones» del asistente de cuenta demo (Diseño B).
 *
 * Presentacional: recibe la selección actual, el callback `onPatch` y el desglose de comisiones
 * de ejemplo ya calculado por el orquestador. La lógica de cálculo vive en `CreateAccountWizardDialog`.
 *
 * El catálogo (ids, etiquetas y hints) sale de `@bolsa/shared`, la misma fuente que usa el
 * panel de configuración: antes cada superficie tenía su copia y se desincronizaba.
 * El preset `custom` no se ofrece aquí a propósito: el wizard crea la cuenta y los
 * parámetros manuales se afinan después en Configuración (una sola superficie de edición).
 */
export function AccountWizardCommissionsStep({
  commissionPresetId,
  sampleFees,
  currency,
  onPatch,
}: {
  commissionPresetId: CommissionPresetId;
  sampleFees: TradeFeeBreakdownDto;
  currency: string;
  onPatch: (
    values: Partial<{ commissionPresetId: CommissionPresetId }>,
  ) => void;
}) {
  const options = COMMISSION_PRESET_IDS.filter((id) => id !== "custom");
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Perfil de comisiones simuladas. Se aplican en cada operación y se
        registran en el historial de movimientos. Los parámetros manuales se
        ajustan después en Configuración → Comisiones y fiscal.
      </p>
      {options.map((id) => (
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
            data-testid={`wizard-preset-${id}`}
          />
          <div>
            <p className="text-sm font-medium">{commissionPresetLabel(id)}</p>
            <p className="text-xs text-muted-foreground">
              {describeCommissionPreset(id, { currency })}
            </p>
          </div>
        </label>
      ))}
      <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">
          Ejemplo compra 5.000 {currency}
        </p>
        <p className="mt-1 tabular-nums">
          Comisión {formatPrice(sampleFees.commission, currency)} · IVA{" "}
          {formatPrice(sampleFees.vatOnCommission, currency)} · Transmisiones{" "}
          {formatPrice(sampleFees.stampDuty, currency)} ·{" "}
          <span className="font-medium text-foreground">
            Total {formatPrice(sampleFees.total, currency)}
          </span>
        </p>
      </div>
    </div>
  );
}
