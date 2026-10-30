import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type {
  AccountSettings,
  CommissionPresetId,
  CommissionProfile,
  TaxJurisdiction,
} from "@bolsa/shared";
import {
  COMMISSION_PRESET_IDS,
  COST_BASIS_LABELS,
  TAX_JURISDICTION_LABELS,
  TAX_PRESETS,
  calculateTradeFees,
  commissionPresetLabel,
  defaultAccountSettings,
  describeCommissionPreset,
  resolveCommissionProfile,
} from "@bolsa/shared";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { AccountVenuePreference } from "@/features/accounts/account-venue-preference";
import { formatPrice } from "@/features/charts/chart-utils";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AccountSettingsPanelProps {
  accountId: string;
  currency: string;
  settings: AccountSettings | null;
  onSaved?: () => void;
  compact?: boolean;
  /** Pestaña con la que abre el panel (deep-link `?tab=config&focus=fiscal`). */
  initialTab?: PanelTab;
}

type PanelTab = "commissions" | "tax";

function cloneSettings(source: AccountSettings | null): AccountSettings {
  if (!source) return defaultAccountSettings();
  return {
    commission: { ...source.commission },
    tax: { ...source.tax },
    notes: source.notes,
  };
}

/**
 * Validación de CLIENTE del mismo contrato que aplica la API
 * (`apps/api-python/src/bolsa_api/schemas/accounts.py`): un tope menor que el mínimo o
 * un mes fuera de 1..12 son 422 en el servidor. Aquí se detectan antes de enviar para
 * no gastar una petición ni mostrar el texto crudo del backend.
 */
export function validateAccountSettings(draft: AccountSettings): string | null {
  const { commission, tax } = draft;
  const numeric: [string, number][] = [
    ["La comisión (%)", commission.stockCommissionPct],
    ["El mínimo por operación", commission.stockCommissionMin],
    ["El IVA sobre comisión (%)", commission.vatOnCommissionPct],
    ["La conversión FX (%)", commission.fxConversionPct],
    ["El impuesto de transmisiones (%)", tax.stampDutyBuyPct],
    ["La retención de dividendos (%)", tax.dividendWithholdingPct],
  ];
  for (const [label, value] of numeric) {
    if (!Number.isFinite(value) || value < 0) {
      return `${label} debe ser un número mayor o igual que cero.`;
    }
  }
  if (commission.stockCommissionMax != null) {
    if (
      !Number.isFinite(commission.stockCommissionMax) ||
      commission.stockCommissionMax < 0
    ) {
      return "El máximo por operación debe ser un número mayor o igual que cero (o vacío).";
    }
    if (commission.stockCommissionMax < commission.stockCommissionMin) {
      return "El máximo por operación no puede ser menor que el mínimo.";
    }
  }
  if (commission.custodyAnnualPct != null) {
    if (
      !Number.isFinite(commission.custodyAnnualPct) ||
      commission.custodyAnnualPct < 0
    ) {
      return "La custodia anual (%) debe ser un número mayor o igual que cero (o vacío).";
    }
  }
  if (tax.capitalGainsTaxPct != null) {
    if (
      !Number.isFinite(tax.capitalGainsTaxPct) ||
      tax.capitalGainsTaxPct < 0
    ) {
      return "El tipo sobre plusvalías debe ser un número mayor o igual que cero (o vacío).";
    }
  }
  if (
    !Number.isInteger(tax.fiscalYearStartMonth) ||
    tax.fiscalYearStartMonth < 1 ||
    tax.fiscalYearStartMonth > 12
  ) {
    return "El inicio del año fiscal debe ser un mes entre 1 y 12.";
  }
  return null;
}

export function AccountSettingsPanel({
  accountId,
  currency,
  settings,
  onSaved,
  compact = false,
  initialTab = "commissions",
}: AccountSettingsPanelProps) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AccountSettings>(() =>
    cloneSettings(settings),
  );
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<PanelTab>(initialTab);

  useEffect(() => {
    setDraft(cloneSettings(settings));
    setError(null);
  }, [accountId, settings]);

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab, accountId]);

  const sampleFees = useMemo(
    () => calculateTradeFees(5000, "buy", draft, { currency }),
    [draft, currency],
  );

  const validationError = useMemo(
    () => validateAccountSettings(draft),
    [draft],
  );

  const saveMutation = useMutation({
    mutationFn: () => api.updateAccountSettings(accountId, draft),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({
        queryKey: ["account-summary", accountId],
      });
      void queryClient.invalidateQueries({ queryKey: ["tax-report"] });
      setError(null);
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  function setPreset(presetId: CommissionPresetId) {
    if (presetId === "custom") {
      setDraft((prev) => ({
        ...prev,
        commission: resolveCommissionProfile("custom", prev.commission),
      }));
      return;
    }
    setDraft((prev) => ({
      ...prev,
      commission: resolveCommissionProfile(presetId),
    }));
  }

  function patchCommission(values: Partial<CommissionProfile>) {
    setDraft((prev) => ({
      ...prev,
      commission: {
        ...prev.commission,
        ...values,
        presetId: "custom",
        label: values.label ?? prev.commission.label ?? "Personalizado",
      },
    }));
  }

  function patchTax(values: Partial<AccountSettings["tax"]>) {
    setDraft((prev) => ({
      ...prev,
      tax: { ...prev.tax, ...values },
    }));
  }

  const presetId = draft.commission.presetId;

  return (
    <div className={cn("space-y-4", compact && "text-sm")}>
      <AccountVenuePreference accountId={accountId} />

      <div className="flex gap-1 border-b border-border" role="tablist">
        {(
          [
            { id: "commissions" as const, label: "Comisiones" },
            { id: "tax" as const, label: "Fiscal" },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            data-testid={`settings-tab-${item.id}`}
            onClick={() => setTab(item.id)}
            className={cn(
              "border-b-2 px-3 py-2 text-xs font-medium transition-colors",
              tab === item.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "commissions" && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Perfil simulado aplicado a cada operación. Los importes se registran
            en el historial de movimientos como entradas de tipo fee.
          </p>
          {COMMISSION_PRESET_IDS.map((id) => (
            <label
              key={id}
              className={cn(
                "flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors",
                presetId === id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-accent/40",
              )}
            >
              <input
                type="radio"
                name={`commission-${accountId}`}
                checked={presetId === id}
                onChange={() => setPreset(id)}
                className="mt-1"
                data-testid={`settings-preset-${id}`}
              />
              <div>
                <p className="font-medium">{commissionPresetLabel(id)}</p>
                <p className="text-xs text-muted-foreground">
                  {describeCommissionPreset(id, { currency })}
                </p>
              </div>
            </label>
          ))}

          {presetId === "custom" && (
            <div className="grid gap-3 rounded-md border border-dashed border-border p-3 sm:grid-cols-2">
              <FieldRow label="Comisión (%)" hint="Sobre importe operado">
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  className={inputClassName}
                  value={draft.commission.stockCommissionPct}
                  onChange={(e) =>
                    patchCommission({
                      stockCommissionPct: Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
              <FieldRow label="Mínimo por operación">
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  className={inputClassName}
                  value={draft.commission.stockCommissionMin}
                  onChange={(e) =>
                    patchCommission({
                      stockCommissionMin: Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
              <FieldRow label="Máximo (vacío = sin tope)">
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  className={inputClassName}
                  value={draft.commission.stockCommissionMax ?? ""}
                  onChange={(e) =>
                    patchCommission({
                      stockCommissionMax:
                        e.target.value === ""
                          ? null
                          : Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
              <FieldRow label="IVA sobre comisión (%)">
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  className={inputClassName}
                  value={draft.commission.vatOnCommissionPct}
                  onChange={(e) =>
                    patchCommission({
                      vatOnCommissionPct: Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
              <FieldRow label="Conversión FX (%)">
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  className={inputClassName}
                  value={draft.commission.fxConversionPct}
                  onChange={(e) =>
                    patchCommission({
                      fxConversionPct: Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
              <FieldRow
                label="Custodia anual (%)"
                hint="Cargo automático anual sobre patrimonio total de la cuenta"
              >
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  className={inputClassName}
                  value={draft.commission.custodyAnnualPct ?? ""}
                  onChange={(e) =>
                    patchCommission({
                      custodyAnnualPct:
                        e.target.value === ""
                          ? null
                          : Number(e.target.value) || 0,
                    })
                  }
                />
              </FieldRow>
            </div>
          )}

          <div className="rounded-md border border-border bg-muted/20 p-3 text-xs">
            <p className="font-medium">
              Vista previa — compra 5.000 {currency}
            </p>
            <p className="mt-1 tabular-nums text-muted-foreground">
              Comisión {formatPrice(sampleFees.commission, currency)} · IVA{" "}
              {formatPrice(sampleFees.vatOnCommission, currency)} ·
              Transmisiones {formatPrice(sampleFees.stampDuty, currency)} ·{" "}
              <span className="font-medium text-foreground">
                Total {formatPrice(sampleFees.total, currency)}
              </span>
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Cálculo con la misma fórmula y redondeo (4 decimales) que aplica
              el servidor al registrar la operación.
            </p>
          </div>
        </div>
      )}

      {tab === "tax" && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Parámetros para simulación y para el informe fiscal. No constituyen
            asesoramiento fiscal.
          </p>
          <FieldRow label="Jurisdicción fiscal">
            <select
              className={inputClassName}
              value={draft.tax.jurisdiction}
              data-testid="settings-tax-jurisdiction"
              onChange={(e) => {
                const j = e.target.value as TaxJurisdiction;
                const preset = TAX_PRESETS[j];
                patchTax({
                  jurisdiction: j,
                  stampDutyBuyPct: preset.stampDutyBuyPct,
                  dividendWithholdingPct: preset.dividendWithholdingPct,
                  costBasisMethod: preset.costBasisMethod,
                  capitalGainsTaxPct: preset.capitalGainsTaxPct,
                  fiscalYearStartMonth: preset.fiscalYearStartMonth,
                });
              }}
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
          <div className="grid gap-3 sm:grid-cols-2">
            <FieldRow label="Método de coste">
              <select
                className={inputClassName}
                value={draft.tax.costBasisMethod}
                onChange={(e) =>
                  patchTax({
                    costBasisMethod: e.target.value as "fifo" | "average",
                  })
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
            <FieldRow label="Imp. transmisiones compra (%)">
              <input
                type="number"
                min={0}
                step={0.01}
                className={inputClassName}
                value={draft.tax.stampDutyBuyPct}
                onChange={(e) =>
                  patchTax({ stampDutyBuyPct: Number(e.target.value) || 0 })
                }
              />
            </FieldRow>
            <FieldRow label="Retención dividendos (%)">
              <input
                type="number"
                min={0}
                step={0.5}
                className={inputClassName}
                value={draft.tax.dividendWithholdingPct}
                onChange={(e) =>
                  patchTax({
                    dividendWithholdingPct: Number(e.target.value) || 0,
                  })
                }
              />
            </FieldRow>
            <FieldRow
              label="Tipo estimado sobre plusvalías (%)"
              hint="Solo proyección del informe fiscal; no se retiene en la simulación. Vacío = no estimar."
            >
              <input
                type="number"
                min={0}
                step={0.5}
                className={inputClassName}
                data-testid="settings-tax-capital-gains"
                value={draft.tax.capitalGainsTaxPct ?? ""}
                onChange={(e) =>
                  patchTax({
                    capitalGainsTaxPct:
                      e.target.value === ""
                        ? null
                        : Number(e.target.value) || 0,
                  })
                }
              />
            </FieldRow>
            <FieldRow label="Inicio año fiscal (mes)">
              <input
                type="number"
                min={1}
                max={12}
                className={inputClassName}
                value={draft.tax.fiscalYearStartMonth}
                onChange={(e) =>
                  patchTax({
                    fiscalYearStartMonth: Number(e.target.value) || 1,
                  })
                }
              />
            </FieldRow>
          </div>
          <FieldRow label="Notas internas">
            <textarea
              className={cn(inputClassName, "min-h-[56px] resize-y")}
              value={draft.notes ?? ""}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  notes: e.target.value.trim() || null,
                }))
              }
            />
          </FieldRow>
        </div>
      )}

      {validationError && (
        <p
          className="text-sm text-destructive"
          data-testid="settings-validation-error"
        >
          {validationError}
        </p>
      )}

      {error && (
        <p
          className="text-sm text-destructive"
          data-testid="settings-api-error"
        >
          {error}
        </p>
      )}

      <div className="flex items-center justify-end gap-3 border-t border-border pt-3">
        {validationError ? (
          <p className="mr-auto text-xs text-muted-foreground">
            Corrige los valores marcados para poder guardar.
          </p>
        ) : null}
        <button
          type="button"
          disabled={saveMutation.isPending || validationError != null}
          onClick={() => void saveMutation.mutateAsync()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {saveMutation.isPending
            ? "Guardando…"
            : "Guardar comisiones y fiscal"}
        </button>
      </div>
    </div>
  );
}
