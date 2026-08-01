/**
 * Selector del perfil inversor activo de UNA cuenta.
 * El catálogo se gestiona en Configuración → Perfil inversor.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import type { SuggestablePolicyTemplateId } from '@bolsa/shared';
import { POLICY_TEMPLATE_LABELS } from '@bolsa/shared';
import {
  InvestorProfilePicker,
  profileUsageByAccount,
} from '@/features/accounts/investor-profile-picker';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/ui-store';

interface AccountInvestorProfileSelectProps {
  accountId: string;
  activeProfileId?: string | null;
  disabled?: boolean;
  className?: string;
  /** Mostrar enlace al catálogo (Configuración → Perfil inversor). */
  showCatalogLink?: boolean;
}

export function AccountInvestorProfileSelect({
  accountId,
  activeProfileId,
  disabled = false,
  className,
  showCatalogLink = true,
}: AccountInvestorProfileSelectProps) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(activeProfileId ?? '');
  const [error, setError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ['investor-profiles'],
    queryFn: async () => (await api.listInvestorProfiles()).data,
  });

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => (await api.getAccounts()).data,
  });

  const ensureMutation = useMutation({
    mutationFn: () => api.ensureDefaultInvestorProfiles(),
    onSuccess: (res) => {
      void queryClient.setQueryData(['investor-profiles'], res.data);
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
    },
  });

  useEffect(() => {
    setValue(activeProfileId ?? '');
  }, [activeProfileId, accountId]);

  useEffect(() => {
    if (listQuery.isSuccess && (listQuery.data?.length ?? 0) === 0 && !ensureMutation.isPending) {
      ensureMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listQuery.isSuccess, listQuery.data?.length]);

  const assignMutation = useMutation({
    mutationFn: (profileId: string | null) => api.assignAccountProfile(accountId, profileId),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summary', accountId] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const profiles = listQuery.data ?? [];
  const selected = profiles.find((p) => p.profileId === value);
  const usage = useMemo(
    () => profileUsageByAccount(accountsQuery.data ?? []),
    [accountsQuery.data],
  );

  return (
    <div className={cn('space-y-2 rounded-md border border-border p-3', className)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-foreground">Perfil inversor</p>
          <p className="text-xs text-muted-foreground">
            Un perfil activo por cuenta. Define la Trading Policy del Policy Gate.
          </p>
        </div>
        {showCatalogLink ? (
          <button
            type="button"
            className="shrink-0 text-xs text-primary hover:underline"
            onClick={() => useUiStore.getState().openPlatformConfig('investor-profile')}
          >
            Gestionar catálogo →
          </button>
        ) : null}
      </div>

      <InvestorProfilePicker
        value={value}
        onChange={(next) => {
          setValue(next);
          assignMutation.mutate(next || null);
        }}
        disabled={
          disabled ||
          listQuery.isLoading ||
          ensureMutation.isPending ||
          assignMutation.isPending ||
          profiles.length === 0
        }
        usedByAccounts={usage}
        maxHeightClassName="max-h-48"
      />

      {selected ? (
        <p className="text-[11px] text-muted-foreground">
          Activo:{' '}
          <span className="font-medium text-foreground">{selected.name}</span>
          {' · '}
          {POLICY_TEMPLATE_LABELS[
            selected.selectedPolicyTemplateId as SuggestablePolicyTemplateId
          ] ?? selected.selectedPolicyTemplateId}
        </p>
      ) : null}

      {assignMutation.isPending ? (
        <p className="text-[11px] text-muted-foreground">Guardando asignación…</p>
      ) : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
