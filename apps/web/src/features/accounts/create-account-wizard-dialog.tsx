import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type {
  AccountSettings,
  CommissionPresetId,
  CreateInvestmentAccountRequestDto,
  ExperienceLevel,
  ProfileHorizon,
  RiskTolerance,
  SuggestablePolicyTemplateId,
  TaxJurisdiction,
} from '@bolsa/shared';
import {
  COMMISSION_PRESETS,
  POLICY_TEMPLATE_LABELS,
  TAX_PRESETS,
  calculateTradeFees,
  resolveCommissionProfile,
  suggestPolicyTemplateFromDeclared,
} from '@bolsa/shared';
import { Dialog, FieldRow, inputClassName } from '@/components/ui/dialog';
import { InvestorProfilePicker } from '@/features/accounts/investor-profile-picker';
import { formatPrice } from '@/features/charts/chart-utils';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useActiveAccountStore } from '@/stores/active-account-store';
import { useUiStore } from '@/stores/ui-store';

const STEPS = [
  { id: 'identity', label: 'Identidad' },
  { id: 'capital', label: 'Capital' },
  { id: 'profile', label: 'Perfil' },
  { id: 'commissions', label: 'Comisiones' },
  { id: 'tax', label: 'Fiscal' },
  { id: 'review', label: 'Revisión' },
] as const;

type StepId = (typeof STEPS)[number]['id'];

const CURRENCIES = ['EUR', 'USD', 'GBP'] as const;

const COMMISSION_OPTIONS: { id: CommissionPresetId; hint: string }[] = [
  { id: 'standard_es', hint: '0,10 % · mín. 1 € · IVA 21 % · custodia 0,2 % anual' },
  { id: 'xtb_zero_stock', hint: '0 % comisión en acciones · FX 0,5 %' },
  { id: 'ibkr_tiered', hint: '0,05 % · mín. 1,25 € · IVA 21 %' },
  { id: 'none', hint: 'Sin comisiones ni impuestos simulados' },
];

const HORIZON_OPTIONS: { id: ProfileHorizon; label: string }[] = [
  { id: 'intraday', label: 'Intradía' },
  { id: 'swing', label: 'Swing' },
  { id: 'position', label: 'Posicional' },
  { id: 'long_term', label: 'Largo plazo' },
];

const RISK_OPTIONS: { id: RiskTolerance; label: string; hint: string }[] = [
  { id: 'low', label: 'Baja', hint: 'Preservar capital' },
  { id: 'moderate', label: 'Moderada', hint: 'Equilibrio' },
  { id: 'high', label: 'Alta', hint: 'Mayor volatilidad' },
];

const EXPERIENCE_OPTIONS: { id: ExperienceLevel; label: string }[] = [
  { id: 'novice', label: 'Principiante' },
  { id: 'intermediate', label: 'Intermedio' },
  { id: 'advanced', label: 'Avanzado' },
  { id: 'professional', label: 'Profesional' },
];

const OBJECTIVE_OPTIONS = [
  { id: 'preservation', label: 'Preservación' },
  { id: 'income', label: 'Renta' },
  { id: 'growth', label: 'Crecimiento' },
  { id: 'speculation', label: 'Especulación' },
] as const;

type ProfileMode = 'new' | 'existing';

interface FormState {
  name: string;
  description: string;
  currency: string;
  initialDeposit: string;
  leverage: string;
  marginCallLevelPct: string;
  portfolioName: string;
  portfolioDescription: string;
  strategyTag: string;
  profileMode: ProfileMode;
  existingProfileId: string;
  profileName: string;
  horizon: ProfileHorizon;
  riskTolerance: RiskTolerance;
  experience: ExperienceLevel;
  objectives: string[];
  commissionPresetId: CommissionPresetId;
  taxJurisdiction: TaxJurisdiction;
  stampDutyBuyPct: string;
  dividendWithholdingPct: string;
  costBasisMethod: 'fifo' | 'average';
  notes: string;
}

const INITIAL_FORM: FormState = {
  name: '',
  description: '',
  currency: 'EUR',
  initialDeposit: '100000',
  leverage: '1',
  marginCallLevelPct: '100',
  portfolioName: 'Cartera principal',
  portfolioDescription: '',
  strategyTag: 'core',
  profileMode: 'existing',
  existingProfileId: '',
  profileName: '',
  horizon: 'swing',
  riskTolerance: 'moderate',
  experience: 'intermediate',
  objectives: ['growth'],
  commissionPresetId: 'standard_es',
  taxJurisdiction: 'ES',
  stampDutyBuyPct: '0.2',
  dividendWithholdingPct: '19',
  costBasisMethod: 'fifo',
  notes: '',
};

function buildSettings(form: FormState): AccountSettings {
  const commission = resolveCommissionProfile(form.commissionPresetId);
  const taxBase = TAX_PRESETS[form.taxJurisdiction];
  return {
    commission,
    tax: {
      ...taxBase,
      jurisdiction: form.taxJurisdiction,
      costBasisMethod: form.costBasisMethod,
      stampDutyBuyPct: Number(form.stampDutyBuyPct) || 0,
      dividendWithholdingPct: Number(form.dividendWithholdingPct) || 0,
    },
    notes: form.notes.trim() || null,
  };
}

function buildPayload(form: FormState): CreateInvestmentAccountRequestDto {
  const base: CreateInvestmentAccountRequestDto = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    currency: form.currency,
    baseCurrency: form.currency,
    initialDeposit: Number(form.initialDeposit) || 0,
    leverage: Number(form.leverage) || 1,
    marginCallLevelPct: Number(form.marginCallLevelPct) || 100,
    portfolioName: form.portfolioName.trim() || 'Cartera principal',
    portfolioDescription: form.portfolioDescription.trim() || null,
    strategyTag: form.strategyTag,
    settings: buildSettings(form),
  };

  if (form.profileMode === 'existing' && form.existingProfileId) {
    return { ...base, activeProfileId: form.existingProfileId };
  }

  const suggested = suggestPolicyTemplateFromDeclared({
    horizon: form.horizon,
    riskTolerance: form.riskTolerance,
    experience: form.experience,
  });
  const profileName =
    form.profileName.trim() ||
    `Perfil · ${form.name.trim()}`.slice(0, 80) ||
    'Perfil por defecto';

  return {
    ...base,
    investorProfile: {
      name: profileName,
      horizon: form.horizon,
      riskTolerance: form.riskTolerance,
      experience: form.experience,
      objectives: form.objectives.length ? form.objectives : ['growth'],
      suggestedPolicyTemplateId: suggested,
      selectedPolicyTemplateId: suggested,
    },
  };
}

function StepIndicator({ current }: { current: StepId }) {
  const index = STEPS.findIndex((s) => s.id === current);
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {STEPS.map((step, i) => (
        <div
          key={step.id}
          className={cn(
            'rounded-full px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
            i === index
              ? 'bg-primary text-primary-foreground'
              : i < index
                ? 'bg-primary/20 text-primary'
                : 'bg-muted text-muted-foreground',
          )}
        >
          {step.label}
        </div>
      ))}
    </div>
  );
}

export function CreateAccountWizardDialog() {
  const open = useUiStore((s) => s.createAccountWizardOpen);
  const close = useUiStore((s) => s.closeCreateAccountWizard);
  const queryClient = useQueryClient();
  const setActiveAccountId = useActiveAccountStore((s) => s.setActiveAccountId);

  const [step, setStep] = useState<StepId>('identity');
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(null);

  const profilesQuery = useQuery({
    queryKey: ['investor-profiles'],
    queryFn: async () => (await api.listInvestorProfiles()).data,
    enabled: open,
  });

  const settings = useMemo(() => buildSettings(form), [form]);
  const sampleFees = useMemo(
    () => calculateTradeFees(5000, 'buy', settings, { currency: form.currency }),
    [settings, form.currency],
  );
  const suggestedTemplate = useMemo(
    () =>
      suggestPolicyTemplateFromDeclared({
        horizon: form.horizon,
        riskTolerance: form.riskTolerance,
        experience: form.experience,
      }),
    [form.horizon, form.riskTolerance, form.experience],
  );

  const catalogProfiles = profilesQuery.data ?? [];
  const selectedCatalog = catalogProfiles.find((p) => p.profileId === form.existingProfileId);

  const createMutation = useMutation({
    mutationFn: (payload: CreateInvestmentAccountRequestDto) => api.createAccount(payload),
    onSuccess: async (response) => {
      setActiveAccountId(response.data.id);
      try {
        await api.setDefaultAccount(response.data.id);
      } catch {
        /* Activa local ya fijada; espejo servidor best-effort */
      }
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summaries'] });
      void queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      void queryClient.invalidateQueries({ queryKey: ['investor-profiles'] });
      setForm(INITIAL_FORM);
      setStep('identity');
      setError(null);
      close();
    },
    onError: (err: Error) => setError(err.message),
  });

  function patch(values: Partial<FormState>) {
    setForm((prev) => ({ ...prev, ...values }));
    setError(null);
  }

  // Catálogo primero: al abrir / al cargar, preseleccionar un perfil existente
  useEffect(() => {
    if (!open || profilesQuery.isLoading) return;
    const list = profilesQuery.data ?? [];
    if (list.length === 0) {
      setForm((prev) =>
        prev.profileMode === 'existing' ? { ...prev, profileMode: 'new' } : prev,
      );
      return;
    }
    setForm((prev) => {
      if (prev.existingProfileId) return prev;
      return {
        ...prev,
        profileMode: 'existing',
        existingProfileId: list[0]!.profileId,
      };
    });
  }, [open, profilesQuery.isLoading, profilesQuery.data]);

  function toggleObjective(id: string) {
    setForm((prev) => {
      const has = prev.objectives.includes(id);
      const next = has ? prev.objectives.filter((o) => o !== id) : [...prev.objectives, id];
      return { ...prev, objectives: next.length ? next : ['growth'] };
    });
    setError(null);
  }

  function validateStep(current: StepId): string | null {
    if (current === 'identity' && !form.name.trim()) return 'Indica un nombre para la cuenta.';
    if (current === 'capital') {
      const deposit = Number(form.initialDeposit);
      if (!Number.isFinite(deposit) || deposit <= 0) return 'El depósito inicial debe ser mayor que cero.';
      const lev = Number(form.leverage);
      if (!Number.isFinite(lev) || lev < 1 || lev > 10) return 'Apalancamiento entre 1 y 10.';
    }
    if (current === 'profile' && form.profileMode === 'existing' && !form.existingProfileId) {
      return 'Elige un perfil del catálogo o crea uno nuevo.';
    }
    return null;
  }

  function goNext() {
    const msg = validateStep(step);
    if (msg) {
      setError(msg);
      return;
    }
    const idx = STEPS.findIndex((s) => s.id === step);
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1]!.id);
  }

  function goBack() {
    const idx = STEPS.findIndex((s) => s.id === step);
    if (idx > 0) setStep(STEPS[idx - 1]!.id);
  }

  function handleClose() {
    if (createMutation.isPending) return;
    close();
  }

  function profileReviewLabel(): string {
    if (form.profileMode === 'existing' && selectedCatalog) {
      const tpl =
        POLICY_TEMPLATE_LABELS[
          selectedCatalog.selectedPolicyTemplateId as SuggestablePolicyTemplateId
        ] ?? selectedCatalog.selectedPolicyTemplateId;
      return `${selectedCatalog.name} · ${tpl}`;
    }
    const tpl = POLICY_TEMPLATE_LABELS[suggestedTemplate];
    const name =
      form.profileName.trim() ||
      (form.name.trim() ? `Perfil · ${form.name.trim()}` : 'Nuevo perfil');
    return `${name} · ${tpl} · ${form.riskTolerance}`;
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title="Nueva cuenta demo"
      description="Simulación local — capital, perfil inversor, comisiones y fiscal."
      className="max-w-2xl"
    >
      <StepIndicator current={step} />

      {step === 'identity' && (
        <div className="space-y-4">
          <FieldRow label="Nombre de la cuenta" hint="Ej. Paper IBEX, Estrategia dividendos">
            <input
              className={inputClassName}
              value={form.name}
              onChange={(e) => patch({ name: e.target.value })}
              placeholder="Cuenta demo EUR"
              autoFocus
            />
          </FieldRow>
          <FieldRow label="Descripción (opcional)">
            <textarea
              className={cn(inputClassName, 'min-h-[72px] resize-y')}
              value={form.description}
              onChange={(e) => patch({ description: e.target.value })}
              placeholder="Objetivo, horizonte, notas…"
            />
          </FieldRow>
          <FieldRow label="Moneda de la cuenta">
            <select
              className={inputClassName}
              value={form.currency}
              onChange={(e) => patch({ currency: e.target.value })}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </FieldRow>
        </div>
      )}

      {step === 'capital' && (
        <div className="space-y-4">
          <FieldRow label="Depósito inicial" hint="Efectivo disponible al abrir la cuenta">
            <input
              type="number"
              min={0}
              step={1000}
              className={inputClassName}
              value={form.initialDeposit}
              onChange={(e) => patch({ initialDeposit: e.target.value })}
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
                value={form.leverage}
                onChange={(e) => patch({ leverage: e.target.value })}
              />
            </FieldRow>
            <FieldRow label="Nivel margin call (%)" hint="Alerta cuando margen caiga bajo este umbral">
              <input
                type="number"
                min={50}
                max={200}
                className={inputClassName}
                value={form.marginCallLevelPct}
                onChange={(e) => patch({ marginCallLevelPct: e.target.value })}
              />
            </FieldRow>
          </div>
          <p className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            Cuenta simulada: el apalancamiento afectará al cálculo de margen en fases posteriores. Por
            ahora el trading opera con efectivo disponible.
          </p>
        </div>
      )}

      {step === 'profile' && (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium text-foreground">Perfil inversor de esta cuenta</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Cada cuenta tiene <span className="text-foreground">un solo perfil activo</span> del
              catálogo (Policy Gate). Elige uno existente o crea uno nuevo. No confundir con el
              preset de comisiones del paso siguiente.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {(
              [
                { id: 'existing' as const, label: 'Del catálogo' },
                { id: 'new' as const, label: 'Crear nuevo' },
              ] as const
            ).map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() =>
                  patch({
                    profileMode: opt.id,
                    existingProfileId:
                      opt.id === 'existing' && !form.existingProfileId && catalogProfiles[0]
                        ? catalogProfiles[0].profileId
                        : form.existingProfileId,
                  })
                }
                className={cn(
                  'rounded-md border px-3 py-1.5 text-sm transition-colors',
                  form.profileMode === opt.id
                    ? 'border-primary bg-primary/10 text-foreground'
                    : 'border-border text-muted-foreground hover:bg-accent/40',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {form.profileMode === 'existing' ? (
            <div className="space-y-2">
              <InvestorProfilePicker
                value={form.existingProfileId}
                onChange={(profileId) => patch({ existingProfileId: profileId })}
                disabled={createMutation.isPending}
                maxHeightClassName="max-h-64"
              />
              {selectedCatalog ? (
                <p className="text-xs text-muted-foreground">
                  Seleccionado:{' '}
                  <span className="font-medium text-foreground">{selectedCatalog.name}</span>
                  {' · '}
                  {POLICY_TEMPLATE_LABELS[
                    selectedCatalog.selectedPolicyTemplateId as SuggestablePolicyTemplateId
                  ] ?? selectedCatalog.selectedPolicyTemplateId}
                </p>
              ) : null}
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => useUiStore.getState().openPlatformConfig('investor-profile')}
              >
                Gestionar catálogo →
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Se creará un perfil nuevo en el catálogo y se asignará a esta cuenta.
              </p>
              <FieldRow
                label="Nombre del perfil (opcional)"
                hint="Si lo dejas vacío: «Perfil · {nombre de la cuenta}»"
              >
                <input
                  className={inputClassName}
                  value={form.profileName}
                  onChange={(e) => patch({ profileName: e.target.value })}
                  placeholder={
                    form.name.trim()
                      ? `Perfil · ${form.name.trim()}`
                      : 'Perfil · Cuenta demo'
                  }
                />
              </FieldRow>

              <div>
                <p className="mb-2 text-xs text-muted-foreground">Tolerancia al riesgo</p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {RISK_OPTIONS.map((opt) => (
                    <label
                      key={opt.id}
                      className={cn(
                        'flex cursor-pointer flex-col rounded-lg border p-3 transition-colors',
                        form.riskTolerance === opt.id
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:bg-accent/40',
                      )}
                    >
                      <input
                        type="radio"
                        name="riskTolerance"
                        className="sr-only"
                        checked={form.riskTolerance === opt.id}
                        onChange={() => patch({ riskTolerance: opt.id })}
                      />
                      <span className="text-sm font-medium">{opt.label}</span>
                      <span className="text-[11px] text-muted-foreground">{opt.hint}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FieldRow label="Horizonte">
                  <select
                    className={inputClassName}
                    value={form.horizon}
                    onChange={(e) => patch({ horizon: e.target.value as ProfileHorizon })}
                  >
                    {HORIZON_OPTIONS.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </FieldRow>
                <FieldRow label="Experiencia">
                  <select
                    className={inputClassName}
                    value={form.experience}
                    onChange={(e) => patch({ experience: e.target.value as ExperienceLevel })}
                  >
                    {EXPERIENCE_OPTIONS.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </FieldRow>
              </div>

              <div>
                <p className="mb-2 text-xs text-muted-foreground">Objetivos</p>
                <div className="flex flex-wrap gap-2">
                  {OBJECTIVE_OPTIONS.map((o) => {
                    const on = form.objectives.includes(o.id);
                    return (
                      <button
                        key={o.id}
                        type="button"
                        onClick={() => toggleObjective(o.id)}
                        className={cn(
                          'rounded-md border px-2.5 py-1 text-xs transition-colors',
                          on
                            ? 'border-primary bg-primary/10 text-foreground'
                            : 'border-border text-muted-foreground hover:bg-accent/40',
                        )}
                      >
                        {o.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
                Plantilla de política sugerida:{' '}
                <span className="font-medium text-foreground">
                  {POLICY_TEMPLATE_LABELS[suggestedTemplate]}
                </span>
                . Puedes afinarla después en Configuración → Perfil inversor.
              </p>
            </div>
          )}
        </div>
      )}

      {step === 'commissions' && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Perfil de comisiones simuladas. Se aplican en cada operación y se registran en el ledger.
          </p>
          {COMMISSION_OPTIONS.map(({ id, hint }) => {
            const preset = COMMISSION_PRESETS[id as keyof typeof COMMISSION_PRESETS];
            if (!preset && id !== 'custom') return null;
            const label = id === 'standard_es' ? COMMISSION_PRESETS.standard_es.label : preset?.label ?? id;
            return (
              <label
                key={id}
                className={cn(
                  'flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors',
                  form.commissionPresetId === id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-accent/40',
                )}
              >
                <input
                  type="radio"
                  name="commissionPreset"
                  checked={form.commissionPresetId === id}
                  onChange={() => patch({ commissionPresetId: id })}
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
              Comisión {formatPrice(sampleFees.commission)} · IVA {formatPrice(sampleFees.vatOnCommission)}{' '}
              · Transmisiones {formatPrice(sampleFees.stampDuty)} ·{' '}
              <span className="font-medium text-foreground">Total {formatPrice(sampleFees.total)}</span>
            </p>
          </div>
        </div>
      )}

      {step === 'tax' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Parámetros fiscales para simulación y futuros informes. No constituyen asesoramiento fiscal.
          </p>
          <FieldRow label="Jurisdicción fiscal">
            <select
              className={inputClassName}
              value={form.taxJurisdiction}
              onChange={(e) => {
                const j = e.target.value as TaxJurisdiction;
                const preset = TAX_PRESETS[j];
                patch({
                  taxJurisdiction: j,
                  stampDutyBuyPct: String(preset.stampDutyBuyPct),
                  dividendWithholdingPct: String(preset.dividendWithholdingPct),
                  costBasisMethod: preset.costBasisMethod,
                });
              }}
            >
              <option value="ES">España (ES)</option>
              <option value="EU_OTHER">Unión Europea (otro)</option>
              <option value="US">Estados Unidos</option>
              <option value="CUSTOM">Personalizado</option>
            </select>
          </FieldRow>
          <div className="grid gap-4 sm:grid-cols-2">
            <FieldRow label="Método de coste" hint="FIFO recomendado para fiscalidad ES">
              <select
                className={inputClassName}
                value={form.costBasisMethod}
                onChange={(e) => patch({ costBasisMethod: e.target.value as 'fifo' | 'average' })}
              >
                <option value="fifo">FIFO (primero en entrar)</option>
                <option value="average">Coste medio ponderado</option>
              </select>
            </FieldRow>
            <FieldRow label="Imp. transmisiones compra (%)" hint="España acciones ~0,2 %">
              <input
                type="number"
                min={0}
                step={0.01}
                className={inputClassName}
                value={form.stampDutyBuyPct}
                onChange={(e) => patch({ stampDutyBuyPct: e.target.value })}
              />
            </FieldRow>
            <FieldRow label="Retención dividendos (%)" hint="Referencia IRPF / doble imposición">
              <input
                type="number"
                min={0}
                step={0.5}
                className={inputClassName}
                value={form.dividendWithholdingPct}
                onChange={(e) => patch({ dividendWithholdingPct: e.target.value })}
              />
            </FieldRow>
          </div>
          <FieldRow label="Notas internas (opcional)">
            <textarea
              className={cn(inputClassName, 'min-h-[56px] resize-y')}
              value={form.notes}
              onChange={(e) => patch({ notes: e.target.value })}
            />
          </FieldRow>
        </div>
      )}

      {step === 'review' && (
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-border divide-y divide-border">
            {[
              ['Cuenta', form.name],
              ['Moneda', form.currency],
              ['Depósito inicial', formatPrice(Number(form.initialDeposit) || 0)],
              ['Apalancamiento', `${form.leverage}x`],
              ['Perfil inversor', profileReviewLabel()],
              ['Comisiones', settings.commission.label],
              ['Fiscal', `${form.taxJurisdiction} · ${form.costBasisMethod.toUpperCase()}`],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 px-3 py-2">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-medium text-right">{value}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Se creará la cuenta demo con cartera, depósito en el ledger, perfil inversor activo y
            preset de comisiones/fiscal.
          </p>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      <div className="mt-6 flex items-center justify-between gap-2 border-t border-border pt-4">
        <button
          type="button"
          onClick={step === 'identity' ? handleClose : goBack}
          className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          <ChevronLeft className="h-4 w-4" />
          {step === 'identity' ? 'Cancelar' : 'Atrás'}
        </button>
        {step === 'review' ? (
          <button
            type="button"
            disabled={createMutation.isPending}
            onClick={() => void createMutation.mutateAsync(buildPayload(form))}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creando cuenta…' : 'Crear cuenta'}
          </button>
        ) : (
          <button
            type="button"
            onClick={goNext}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Siguiente
            <ChevronRight className="h-4 w-4" />
          </button>
        )}
      </div>
    </Dialog>
  );
}

export function openCreateAccountWizard() {
  useUiStore.getState().openCreateAccountWizard();
}
