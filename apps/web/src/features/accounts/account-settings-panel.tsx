import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type {
  AccountSettings,
  CommissionPresetId,
  CommissionProfile,
  TaxJurisdiction,
} from "@bolsa/shared";
import {
  COMMISSION_PRESETS,
  TAX_PRESETS,
  calculateTradeFees,
  defaultAccountSettings,
  resolveCommissionProfile,
} from "@bolsa/shared";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { AccountInvestorProfileSelect } from "@/features/accounts/account-investor-profile-select";
import { AccountVenuePreference } from "@/features/accounts/account-venue-preference";
import { formatPrice } from "@/features/charts/chart-utils";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const COMMISSION_OPTIONS: { id: CommissionPresetId; hint: string }[] = [
  {
    id: "standard_es",
    hint: "0,10 % · mín. 1 € · IVA 21 % · custodia 0,2 % anual",
  },
  { id: "xtb_zero_stock", hint: "0 % comisión en acciones · FX 0,5 %" },
  { id: "ibkr_tiered", hint: "0,05 % · mín. 1,25 € · IVA 21 %" },
  { id: "custom", hint: "Parámetros manuales de comisión e IVA" },
  { id: "none", hint: "Sin comisiones ni impuestos simulados" },
];

interface AccountSettingsPanelProps {
  accountId: string;
  currency: string;
  settings: AccountSettings | null;
  activeProfileId?: string | null;
  onSaved?: () => void;
  compact?: boolean;
}

function cloneSettings(source: AccountSettings | null): AccountSettings {
  if (!source) return defaultAccountSettings();
  return {
    commission: { ...source.commission },
    tax: { ...source.tax },
    notes: source.notes,
  };
}

export function AccountSettingsPanel({
  accountId,
  currency,
  settings,
  activeProfileId,
  onSaved,
  compact = false,
}: AccountSettingsPanelProps) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AccountSettings>(() =>
    cloneSettings(settings),
  );
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"commissions" | "tax">("commissions");

  useEffect(() => {
    setDraft(cloneSettings(settings));
    setError(null);
  }, [accountId, settings]);

  const sampleFees = useMemo(
    () => calculateTradeFees(5000, "buy", draft, { currency }),
    [draft, currency],
  );

  const saveMutation = useMutation({
    mutationFn: () => api.updateAccountSettings(accountId, draft),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({
        queryKey: ["account-summary", accountId],
      });
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
      <AccountInvestorProfileSelect
        accountId={accountId}
        activeProfileId={activeProfileId}
      />

      <AccountVenuePreference accountId={accountId} />

      <div className="flex gap-1 border-b border-border">
        {(
          [
            { id: "commissions" as const, label: "Comisiones" },
            { id: "tax" as const, label: "Fiscal" },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
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
            en el ledger como entradas de tipo fee.
          </p>
          {COMMISSION_OPTIONS.map(({ id, hint }) => {
            const preset =
              id === "custom"
                ? null
                : COMMISSION_PRESETS[id as keyof typeof COMMISSION_PRESETS];
            const label =
              id === "custom" ? "Personalizado" : (preset?.label ?? id);
            return (
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
                />
                <div>
                  <p className="font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground">{hint}</p>
                </div>
              </label>
            );
          })}

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
              Comisión {formatPrice(sampleFees.commission)} · IVA{" "}
              {formatPrice(sampleFees.vatOnCommission)} · Transmisiones{" "}
              {formatPrice(sampleFees.stampDuty)} ·{" "}
              <span className="font-medium text-foreground">
                Total {formatPrice(sampleFees.total)}
              </span>
            </p>
          </div>
        </div>
      )}

      {tab === "tax" && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Parámetros para simulación y futuros informes. No constituyen
            asesoramiento fiscal.
          </p>
          <FieldRow label="Jurisdicción fiscal">
            <select
              className={inputClassName}
              value={draft.tax.jurisdiction}
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
              <option value="ES">España (ES)</option>
              <option value="EU_OTHER">Unión Europea (otro)</option>
              <option value="US">Estados Unidos</option>
              <option value="CUSTOM">Personalizado</option>
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
                <option value="fifo">FIFO</option>
                <option value="average">Coste medio ponderado</option>
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

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex justify-end border-t border-border pt-3">
        <button
          type="button"
          disabled={saveMutation.isPending}
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
