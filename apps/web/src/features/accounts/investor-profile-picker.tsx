/**
 * Selector visual del catálogo ART-PROFILE (una cuenta = un perfil activo).
 * No asigna por sí solo: el padre decide (wizard payload o PUT active-profile).
 */

import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import type { InvestorProfileV1, SuggestablePolicyTemplateId } from '@bolsa/shared';
import { POLICY_TEMPLATE_LABELS } from '@bolsa/shared';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface InvestorProfilePickerProps {
  value: string;
  onChange: (profileId: string) => void;
  disabled?: boolean;
  className?: string;
  /** Resaltar perfiles usados por estas cuentas (mapa profileId → nombres). */
  usedByAccounts?: Record<string, string[]>;
  maxHeightClassName?: string;
}

function templateLabel(p: InvestorProfileV1): string {
  return (
    POLICY_TEMPLATE_LABELS[p.selectedPolicyTemplateId as SuggestablePolicyTemplateId] ??
    p.selectedPolicyTemplateId
  );
}

export function InvestorProfilePicker({
  value,
  onChange,
  disabled = false,
  className,
  usedByAccounts,
  maxHeightClassName = 'max-h-56',
}: InvestorProfilePickerProps) {
  const listQuery = useQuery({
    queryKey: ['investor-profiles'],
    queryFn: async () => (await api.listInvestorProfiles()).data,
  });

  const profiles = listQuery.data ?? [];

  if (listQuery.isLoading) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Cargando catálogo…
      </p>
    );
  }

  if (listQuery.isError) {
    return (
      <p className="text-xs text-destructive">
        No se pudo cargar el catálogo. ¿Está la API en marcha?
      </p>
    );
  }

  if (profiles.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        El catálogo está vacío. Crea un perfil abajo o en Configuración → Perfil inversor.
      </p>
    );
  }

  return (
    <ul
      className={cn(
        'scroll-area space-y-1.5 overflow-auto rounded-md border border-border p-1.5',
        maxHeightClassName,
        className,
      )}
      role="listbox"
      aria-label="Perfiles del catálogo"
    >
      {profiles.map((p) => {
        const selected = value === p.profileId;
        const usedBy = usedByAccounts?.[p.profileId] ?? [];
        return (
          <li key={p.profileId}>
            <button
              type="button"
              role="option"
              aria-selected={selected}
              disabled={disabled}
              onClick={() => onChange(p.profileId)}
              className={cn(
                'flex w-full flex-col gap-0.5 rounded-md border px-3 py-2.5 text-left transition-colors disabled:opacity-50',
                selected
                  ? 'border-primary bg-primary/10'
                  : 'border-transparent hover:bg-accent/50',
              )}
            >
              <span className="text-sm font-medium text-foreground">{p.name}</span>
              <span className="text-[11px] text-muted-foreground">
                {templateLabel(p)} · {p.declared.horizon} · riesgo {p.declared.riskTolerance} ·{' '}
                {p.declared.experience}
                {p.declared.objectives?.length
                  ? ` · ${p.declared.objectives.join(', ')}`
                  : ''}
              </span>
              {usedBy.length > 0 ? (
                <span className="text-[10px] text-muted-foreground">
                  En uso: {usedBy.join(', ')}
                </span>
              ) : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function profileUsageByAccount(
  accounts: { id: string; name: string; activeProfileId?: string | null; status: string }[],
): Record<string, string[]> {
  const map: Record<string, string[]> = {};
  for (const a of accounts) {
    if (a.status !== 'active' || !a.activeProfileId) continue;
    const list = map[a.activeProfileId] ?? [];
    list.push(a.name);
    map[a.activeProfileId] = list;
  }
  return map;
}
