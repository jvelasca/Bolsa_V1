/**
 * RFC-008 — Catálogo ART-PROFILE + asignación a la cuenta activa.
 * Declared ≠ Policy; Observed solo lectura.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import type {
  ExperienceLevel,
  InvestmentAccountDto,
  InvestorProfileV1,
  ProfileHorizon,
  RiskTolerance,
  SuggestablePolicyTemplateId,
} from '@bolsa/shared';
import {
  POLICY_TEMPLATE_LABELS,
  getTradingPolicyTemplate,
  observeInvestorProfile,
  suggestPolicyTemplateFromDeclared,
} from '@bolsa/shared';
import { FieldRow, inputClassName } from '@/components/ui/dialog';
import {
  InvestorProfilePicker,
  profileUsageByAccount,
} from '@/features/accounts/investor-profile-picker';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

const HORIZON_OPTIONS: { id: ProfileHorizon; label: string }[] = [
  { id: 'intraday', label: 'Intradía' },
  { id: 'swing', label: 'Swing (días–semanas)' },
  { id: 'position', label: 'Posicional (semanas–meses)' },
  { id: 'long_term', label: 'Largo plazo' },
];

const RISK_OPTIONS: { id: RiskTolerance; label: string; hint: string }[] = [
  { id: 'low', label: 'Baja', hint: 'Preservar capital' },
  { id: 'moderate', label: 'Moderada', hint: 'Equilibrio' },
  { id: 'high', label: 'Alta', hint: 'Mayor volatilidad aceptada' },
];

const EXPERIENCE_OPTIONS: { id: ExperienceLevel; label: string }[] = [
  { id: 'novice', label: 'Principiante' },
  { id: 'intermediate', label: 'Intermedio' },
  { id: 'advanced', label: 'Avanzado' },
  { id: 'professional', label: 'Profesional' },
];

const OBJECTIVE_OPTIONS = [
  { id: 'preservation', label: 'Preservación' },
  { id: 'income', label: 'Renta / dividendos' },
  { id: 'growth', label: 'Crecimiento' },
  { id: 'speculation', label: 'Especulación' },
] as const;

const TEMPLATE_OPTIONS: SuggestablePolicyTemplateId[] = [
  'conservative',
  'moderate',
  'aggressive_swing',
];

interface DraftState {
  name: string;
  horizon: ProfileHorizon;
  riskTolerance: RiskTolerance;
  experience: ExperienceLevel;
  objectives: string[];
  maxAcceptableLossPct: string;
  selectedPolicyTemplateId: SuggestablePolicyTemplateId | null;
  followSuggestion: boolean;
}

function emptyDraft(): DraftState {
  return {
    name: '',
    horizon: 'swing',
    riskTolerance: 'moderate',
    experience: 'intermediate',
    objectives: ['growth'],
    maxAcceptableLossPct: '',
    selectedPolicyTemplateId: null,
    followSuggestion: true,
  };
}

function draftFromProfile(p: InvestorProfileV1 | null | undefined): DraftState {
  if (!p) return emptyDraft();
  const suggested = p.suggestedPolicyTemplateId as SuggestablePolicyTemplateId;
  const selected = p.selectedPolicyTemplateId as SuggestablePolicyTemplateId;
  return {
    name: p.name,
    horizon: p.declared.horizon,
    riskTolerance: p.declared.riskTolerance,
    experience: p.declared.experience,
    objectives: [...p.declared.objectives],
    maxAcceptableLossPct:
      p.declared.maxAcceptableLossPct != null ? String(p.declared.maxAcceptableLossPct) : '',
    selectedPolicyTemplateId: selected,
    followSuggestion: suggested === selected,
  };
}

interface InvestorProfilePanelProps {
  accountId: string;
  activeProfileId?: string | null;
  accounts?: InvestmentAccountDto[];
  /** Solo catálogo CRUD; la asignación vive en la config de cada cuenta. */
  catalogOnly?: boolean;
  onSaved?: () => void;
}

export function InvestorProfilePanel({
  accountId,
  activeProfileId,
  accounts = [],
  catalogOnly = false,
  onSaved,
}: InvestorProfilePanelProps) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(activeProfileId ?? null);
  const [draft, setDraft] = useState<DraftState>(emptyDraft);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'edit' | 'create'>('edit');
  const [bootstrapped, setBootstrapped] = useState(false);

  const listQuery = useQuery({
    queryKey: ['investor-profiles'],
    queryFn: async () => (await api.listInvestorProfiles()).data,
  });

  // Cuentas antiguas sin perfil → crear moderate + asignar una vez
  const ensureMutation = useMutation({
    mutationFn: () => api.ensureDefaultInvestorProfiles(),
    onSuccess: (res) => {
      void queryClient.setQueryData(['investor-profiles'], res.data);
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setBootstrapped(true);
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  useEffect(() => {
    if (bootstrapped || ensureMutation.isPending || listQuery.isLoading) return;
    const needsEnsure =
      (listQuery.isSuccess && (listQuery.data?.length ?? 0) === 0) ||
      accounts.some((a) => a.status === 'active' && !a.activeProfileId);
    if (needsEnsure) {
      ensureMutation.mutate();
    } else {
      setBootstrapped(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot bootstrap
  }, [listQuery.isSuccess, listQuery.isLoading, accounts, bootstrapped]);

  const profiles = useMemo(() => listQuery.data ?? [], [listQuery.data]);

  useEffect(() => {
    setSelectedId(activeProfileId ?? null);
  }, [activeProfileId, accountId]);

  useEffect(() => {
    if (mode === 'create') {
      setDraft(emptyDraft());
      return;
    }
    const current = profiles.find((p) => p.profileId === selectedId) ?? null;
    setDraft(draftFromProfile(current));
    setError(null);
  }, [selectedId, profiles, mode]);

  const declaredPreview = useMemo(
    () => ({
      horizon: draft.horizon,
      riskTolerance: draft.riskTolerance,
      experience: draft.experience,
      objectives: draft.objectives,
      maxAcceptableLossPct: draft.maxAcceptableLossPct
        ? Number(draft.maxAcceptableLossPct)
        : undefined,
    }),
    [draft],
  );

  const suggested = useMemo(
    () => suggestPolicyTemplateFromDeclared(declaredPreview),
    [declaredPreview],
  );

  const selected: SuggestablePolicyTemplateId = draft.followSuggestion
    ? suggested
    : (draft.selectedPolicyTemplateId ?? suggested);

  const policyPreview = useMemo(() => getTradingPolicyTemplate(selected), [selected]);
  const observedPreview = useMemo(
    () => observeInvestorProfile(declaredPreview, []),
    [declaredPreview],
  );

  const saveMutation = useMutation({
    mutationFn: async () => {
      const loss = draft.maxAcceptableLossPct.trim()
        ? Number(draft.maxAcceptableLossPct)
        : undefined;
      if (loss != null && (Number.isNaN(loss) || loss < 0 || loss > 100)) {
        throw new Error('Pérdida máxima aceptable debe estar entre 0 y 100');
      }
      if (draft.objectives.length === 0) {
        throw new Error('Selecciona al menos un objetivo');
      }
      const name = draft.name.trim() || 'Perfil sin nombre';
      const body = {
        name,
        horizon: draft.horizon,
        riskTolerance: draft.riskTolerance,
        experience: draft.experience,
        objectives: [...draft.objectives],
        maxAcceptableLossPct: loss ?? null,
        suggestedPolicyTemplateId: suggested,
        selectedPolicyTemplateId: selected,
      };
      if (mode === 'create' || !selectedId) {
        const created = (await api.createInvestorProfile(body)).data;
        if (!catalogOnly) {
          await api.assignAccountProfile(accountId, created.profileId);
        }
        return created;
      }
      return (await api.updateInvestorProfile(selectedId, body)).data;
    },
    onSuccess: (p) => {
      void queryClient.invalidateQueries({ queryKey: ['investor-profiles'] });
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summary', accountId] });
      setSelectedId(p.profileId);
      setMode('edit');
      setError(null);
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (profileId: string) => api.deleteInvestorProfile(profileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['investor-profiles'] });
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setSelectedId(null);
      setMode('create');
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  function toggleObjective(id: string) {
    setDraft((prev) => {
      const has = prev.objectives.includes(id);
      return {
        ...prev,
        objectives: has
          ? prev.objectives.filter((x) => x !== id)
          : [...prev.objectives, id],
      };
    });
  }

  const openAccounts = accounts.filter((a) => a.status === 'active');
  const usage = useMemo(() => profileUsageByAccount(accounts), [accounts]);

  const [assignAccountId, setAssignAccountId] = useState(accountId);
  const [assignProfileId, setAssignProfileId] = useState(activeProfileId ?? selectedId ?? '');

  useEffect(() => {
    setAssignAccountId(accountId);
  }, [accountId]);

  useEffect(() => {
    if (selectedId) setAssignProfileId(selectedId);
    else if (activeProfileId) setAssignProfileId(activeProfileId);
  }, [selectedId, activeProfileId]);

  const assignMutation = useMutation({
    mutationFn: async () => {
      if (!assignAccountId) throw new Error('Elige una cuenta');
      if (!assignProfileId) throw new Error('Elige un perfil del catálogo');
      return api.assignAccountProfile(assignAccountId, assignProfileId);
    },
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summary'] });
      onSaved?.();
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="space-y-5 text-sm">
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
        <p className="font-medium text-foreground">Modelo: catálogo ↔ cuenta</p>
        <p className="mt-1">
          Los perfiles viven en un <span className="text-foreground">catálogo reutilizable</span>.
          Cada cuenta de inversión tiene <span className="text-foreground">un solo perfil activo</span>{' '}
          (varias cuentas pueden compartir el mismo). También puedes elegirlo al crear una demo.
        </p>
        {ensureMutation.isPending ? (
          <p className="mt-1 text-[10px]">Preparando perfiles por defecto…</p>
        ) : null}
      </div>

      {openAccounts.length > 0 ? (
        <section className="space-y-3 rounded-md border border-border p-3">
          <div>
            <h3 className="font-medium">Asignar a una cuenta</h3>
            <p className="text-xs text-muted-foreground">
              Elige cuenta + perfil del catálogo y aplica. Sustituye el perfil activo anterior.
            </p>
          </div>
          <FieldRow label="Cuenta">
            <select
              className={inputClassName}
              value={assignAccountId}
              onChange={(e) => setAssignAccountId(e.target.value)}
            >
              {openAccounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                  {acc.activeProfileId
                    ? ` · ${profiles.find((p) => p.profileId === acc.activeProfileId)?.name ?? 'perfil'}`
                    : ' · sin perfil'}
                </option>
              ))}
            </select>
          </FieldRow>
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Perfil del catálogo</p>
            <InvestorProfilePicker
              value={assignProfileId}
              onChange={(id) => {
                setAssignProfileId(id);
                setSelectedId(id);
                setMode('edit');
              }}
              usedByAccounts={usage}
              maxHeightClassName="max-h-40"
              disabled={assignMutation.isPending || profiles.length === 0}
            />
          </div>
          <button
            type="button"
            disabled={assignMutation.isPending || !assignAccountId || !assignProfileId}
            onClick={() => assignMutation.mutate()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
          >
            {assignMutation.isPending ? 'Asignando…' : 'Aplicar perfil a la cuenta'}
          </button>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="py-1 pr-2 font-medium">Cuenta</th>
                <th className="py-1 font-medium">Perfil activo</th>
              </tr>
            </thead>
            <tbody>
              {openAccounts.map((acc) => {
                const linked = profiles.find((p) => p.profileId === acc.activeProfileId);
                return (
                  <tr key={acc.id} className="border-b border-border/60">
                    <td className="py-1.5 pr-2">{acc.name}</td>
                    <td className="py-1.5">
                      {linked?.name ?? <span className="text-muted-foreground">Sin asignar</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Perfiles del catálogo</h3>
          <button
            type="button"
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-accent"
            onClick={() => {
              setMode('create');
              setSelectedId(null);
              setDraft(emptyDraft());
            }}
          >
            + Nuevo perfil
          </button>
        </div>

        {listQuery.isLoading || ensureMutation.isPending ? (
          <p className="text-xs text-muted-foreground">Cargando catálogo…</p>
        ) : null}
        {listQuery.isError ? (
          <p className="text-xs text-destructive">
            No se pudo cargar el catálogo. ¿Está la API en marcha?
          </p>
        ) : null}
        {!listQuery.isLoading && !ensureMutation.isPending && profiles.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Aún no hay perfiles. Pulsa «+ Nuevo perfil» o el botón de bootstrap.
            <button
              type="button"
              className="ml-2 text-primary hover:underline"
              onClick={() => ensureMutation.mutate()}
            >
              Crear perfiles por defecto
            </button>
          </p>
        ) : null}

        {profiles.length > 0 ? (
          <ul className="space-y-1.5">
            {profiles.map((p) => {
              const isActive = activeProfileId === p.profileId;
              const isEditing = mode === 'edit' && selectedId === p.profileId;
              const templateLabel =
                POLICY_TEMPLATE_LABELS[
                  p.selectedPolicyTemplateId as SuggestablePolicyTemplateId
                ] ?? p.selectedPolicyTemplateId;
              return (
                <li
                  key={p.profileId}
                  className={cn(
                    'flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2.5',
                    isActive
                      ? 'border-emerald-500/50 bg-emerald-500/5'
                      : isEditing
                        ? 'border-primary bg-primary/5'
                        : 'border-border',
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => {
                      setMode('edit');
                      setSelectedId(p.profileId);
                    }}
                  >
                    <div className="font-medium text-foreground">{p.name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {templateLabel} · {p.declared.horizon} · riesgo {p.declared.riskTolerance}
                      {isActive ? ' · asignado a esta cuenta' : ''}
                    </div>
                  </button>
                  <div className="flex shrink-0 gap-2">
                    {isActive && !catalogOnly ? (
                      <span className="rounded-md border border-emerald-500/40 px-2 py-1 text-[11px] text-emerald-700 dark:text-emerald-400">
                        En uso (cuenta activa)
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="text-[11px] text-muted-foreground hover:text-foreground hover:underline"
                      onClick={() => {
                        setMode('edit');
                        setSelectedId(p.profileId);
                      }}
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      className="text-[11px] text-destructive hover:underline"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`¿Eliminar perfil «${p.name}»?`)) {
                          deleteMutation.mutate(p.profileId);
                        }
                      }}
                    >
                      Eliminar
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

      <section className="space-y-3 rounded-md border border-dashed border-border p-3">
        <h3 className="font-medium">
          {mode === 'create' ? 'Crear perfil' : 'Editar perfil seleccionado'}
        </h3>

        <FieldRow label="Nombre del perfil">
          <input
            className={inputClassName}
            value={draft.name}
            onChange={(e) => setDraft((p) => ({ ...p, name: e.target.value }))}
            placeholder="p. ej. Swing moderado"
          />
        </FieldRow>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Horizonte</h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {HORIZON_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDraft((p) => ({ ...p, horizon: opt.id }))}
                className={cn(
                  'rounded-md border px-3 py-2 text-left text-sm',
                  draft.horizon === opt.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-accent',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Aversión al riesgo</h4>
          <div className="grid gap-2 sm:grid-cols-3">
            {RISK_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDraft((p) => ({ ...p, riskTolerance: opt.id }))}
                className={cn(
                  'rounded-md border px-3 py-2 text-left text-sm',
                  draft.riskTolerance === opt.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-accent',
                )}
              >
                <div className="font-medium">{opt.label}</div>
                <div className="text-[10px] text-muted-foreground">{opt.hint}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Experiencia</h4>
          <div className="flex flex-wrap gap-2">
            {EXPERIENCE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDraft((p) => ({ ...p, experience: opt.id }))}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs',
                  draft.experience === opt.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-accent',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Objetivos</h4>
          <div className="flex flex-wrap gap-2">
            {OBJECTIVE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleObjective(opt.id)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs',
                  draft.objectives.includes(opt.id)
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:bg-accent',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <FieldRow label="Pérdida máxima aceptable (% cuenta, opcional)">
          <input
            className={inputClassName}
            value={draft.maxAcceptableLossPct}
            onChange={(e) => setDraft((p) => ({ ...p, maxAcceptableLossPct: e.target.value }))}
            placeholder="p. ej. 1.5"
            inputMode="decimal"
          />
        </FieldRow>

        <div className="space-y-2 rounded-md border border-border p-3">
          <h4 className="font-medium">Trading Policy (plantilla)</h4>
          <p className="text-xs text-muted-foreground">
            Sugerida: {POLICY_TEMPLATE_LABELS[suggested]}. Puedes override.
          </p>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={draft.followSuggestion}
              onChange={(e) => setDraft((p) => ({ ...p, followSuggestion: e.target.checked }))}
            />
            Seguir sugerencia automática
          </label>
          {!draft.followSuggestion ? (
            <div className="flex flex-wrap gap-2">
              {TEMPLATE_OPTIONS.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() =>
                    setDraft((p) => ({
                      ...p,
                      selectedPolicyTemplateId: id,
                      followSuggestion: false,
                    }))
                  }
                  className={cn(
                    'rounded-md border px-3 py-1.5 text-xs',
                    selected === id ? 'border-primary bg-primary/5' : 'border-border',
                  )}
                >
                  {POLICY_TEMPLATE_LABELS[id]}
                </button>
              ))}
            </div>
          ) : null}
          <p className="text-[10px] text-muted-foreground">
            Riesgo/trade {policyPreview.risk.maxRiskPerTradePct}% · R:R{' '}
            {policyPreview.risk.minRewardToRiskRatio} · max pos.{' '}
            {policyPreview.exposure.maxOpenPositions}
          </p>
        </div>

        <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Perfil observado (solo lectura)</p>
          <p className="mt-1">
            Muestras: {observedPreview.sampleTradeCount}
            {observedPreview.notes?.[0] ? ` · ${observedPreview.notes[0]}` : ''}
          </p>
        </div>
      </section>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {saveMutation.isPending
            ? 'Guardando…'
            : mode === 'create'
              ? catalogOnly
                ? 'Crear en el catálogo'
                : 'Crear y asignar a la cuenta activa'
              : 'Guardar cambios del perfil'}
        </button>
      </div>
    </div>
  );
}
