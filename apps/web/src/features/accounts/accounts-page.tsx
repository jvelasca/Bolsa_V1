import { useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import type { InvestmentAccountDto, InvestmentAccountType, PaperLabEvidenceSnapshot } from '@bolsa/shared';
import { AccountDetailPanel } from '@/features/accounts/account-detail-panel';
import { formatPaperLabEvidence } from '@/features/accounts/paper-lab-evidence';
import { useActivateAccount } from '@/features/accounts/use-active-account';
import { formatPrice } from '@/features/charts/chart-utils';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useActiveAccountStore } from '@/stores/active-account-store';
import { useUiStore } from '@/stores/ui-store';

function accountTypeLabel(type: InvestmentAccountType): string {
  if (type === 'simulated') return 'Demo';
  if (type === 'paper') return 'Paper (futuro · broker)';
  return 'Live (reservado)';
}

function AccountListItem({
  account,
  selected,
  onSelect,
  isWorking,
  totalEquity,
}: {
  account: InvestmentAccountDto;
  selected: boolean;
  onSelect: () => void;
  isWorking?: boolean;
  totalEquity?: number;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-lg border px-3 py-3 text-left transition-colors',
        selected ? 'border-primary bg-primary/10' : 'border-border hover:bg-accent/40',
        account.status === 'closed' && 'opacity-70',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">{account.name}</p>
          <p className="text-xs text-muted-foreground">
            {account.currency} · {accountTypeLabel(account.type)}
            {account.status === 'closed' ? ' · cerrada' : ''}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          {isWorking && account.status === 'active' && (
            <span className="text-[10px] uppercase text-primary" title="La app opera con esta cuenta">
              Activa
            </span>
          )}
        </div>
      </div>
      {totalEquity != null && (
        <p className="mt-1 text-sm tabular-nums text-muted-foreground">
          {formatPrice(totalEquity)}
        </p>
      )}
    </button>
  );
}

type HubFilter = 'demo' | 'paper' | 'all';

export function AccountsPage() {
  const activeAccountId = useActiveAccountStore((s) => s.activeAccountId);
  const activateAccount = useActivateAccount();
  const openWizard = useUiStore((s) => s.openCreateAccountWizard);
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const deployState = location.state as {
    paperLabEvidence?: PaperLabEvidenceSnapshot | null;
    paperDeployNote?: string;
  } | null;
  const [showClosed, setShowClosed] = useState(false);
  const [deployBanner, setDeployBanner] = useState<string | null>(
    deployState?.paperDeployNote
      ? `${deployState.paperDeployNote} ${formatPaperLabEvidence(deployState.paperLabEvidence)}`
      : null,
  );

  useEffect(() => {
    if (!deployState?.paperDeployNote) return;
    setDeployBanner(
      `${deployState.paperDeployNote} ${formatPaperLabEvidence(deployState.paperLabEvidence)}`,
    );
  }, [deployState?.paperDeployNote, deployState?.paperLabEvidence]);

  const hubFilter: HubFilter = useMemo(() => {
    const raw = searchParams.get('type');
    if (raw === 'paper') return 'paper';
    if (raw === 'all') return 'all';
    return 'demo';
  }, [searchParams]);

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => (await api.getAccounts()).data,
  });
  const summariesQuery = useQuery({
    queryKey: ['account-summaries'],
    queryFn: async () => (await api.getAccountSummaries()).data,
    staleTime: 30_000,
  });

  const accounts = useMemo(() => accountsQuery.data ?? [], [accountsQuery.data]);
  const equityByAccountId = useMemo(() => {
    const map = new Map<string, number>();
    for (const summary of summariesQuery.data ?? []) {
      map.set(summary.account.id, summary.totalEquity);
    }
    return map;
  }, [summariesQuery.data]);

  const filteredAccounts = useMemo(() => {
    if (hubFilter === 'paper') return accounts.filter((a) => a.type === 'paper');
    if (hubFilter === 'demo') return accounts.filter((a) => a.type === 'simulated');
    return accounts;
  }, [accounts, hubFilter]);

  const activeAccounts = useMemo(
    () => filteredAccounts.filter((a) => a.status === 'active'),
    [filteredAccounts],
  );
  const closedAccounts = useMemo(
    () => filteredAccounts.filter((a) => a.status === 'closed'),
    [filteredAccounts],
  );

  const demoActiveCount = useMemo(
    () => accounts.filter((a) => a.type === 'simulated' && a.status === 'active').length,
    [accounts],
  );
  const paperActiveCount = useMemo(
    () => accounts.filter((a) => a.type === 'paper' && a.status === 'active').length,
    [accounts],
  );

  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('selected'));

  useEffect(() => {
    const fromUrl = searchParams.get('selected');
    if (fromUrl) setSelectedId(fromUrl);
  }, [searchParams]);

  const effectiveSelectedId =
    selectedId ??
    activeAccountId ??
    activeAccounts.find((a) => a.isDefault)?.id ??
    activeAccounts[0]?.id ??
    filteredAccounts[0]?.id ??
    null;

  const selectedAccount =
    accounts.find((a) => a.id === effectiveSelectedId) ??
    filteredAccounts.find((a) => a.id === effectiveSelectedId) ??
    null;

  useEffect(() => {
    if (selectedAccount?.status !== 'active') return;
    if (selectedAccount.id === activeAccountId) return;
    void activateAccount.mutateAsync(selectedAccount.id);
    // Solo al cambiar de cuenta seleccionada; mutateAsync es estable en TanStack Query.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- avoid re-fire on mutation identity
  }, [selectedAccount?.id, selectedAccount?.status, activeAccountId]);

  function setHubFilter(next: HubFilter) {
    const params = new URLSearchParams(searchParams);
    if (next === 'demo') params.delete('type');
    else params.set('type', next);
    setSearchParams(params);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-xl space-y-1">
          <h2 className="text-2xl font-semibold tracking-tight">Cuentas</h2>
          <p className="text-sm text-muted-foreground">
            La <span className="text-foreground">Activa</span> es la única con la que opera la app
            (Trading, demo ledger, Coach…). Hoy: solo cuentas <span className="text-foreground">DEMO</span>.
            Paper = broker real futuro (no crear aún).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-border p-0.5">
            {(
              [
                { id: 'demo' as const, label: `Demo (${demoActiveCount})` },
                {
                  id: 'paper' as const,
                  label: `Paper futuro (${paperActiveCount})`,
                },
                { id: 'all' as const, label: 'Todas' },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm',
                  hubFilter === tab.id ? 'bg-accent text-primary' : 'text-muted-foreground',
                )}
                onClick={() => setHubFilter(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={openWizard}
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
            Nueva demo
          </button>
        </div>
      </div>

      {deployBanner && (
        <div className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">Desplegado en demo activa. </span>
            {deployBanner}
          </p>
          <button
            type="button"
            className="text-primary hover:underline"
            onClick={() => setDeployBanner(null)}
          >
            Cerrar
          </button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(240px,300px)_1fr]">
        <aside className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Activas ({activeAccounts.length})
          </p>
          <div className="space-y-2">
            {activeAccounts.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
                {hubFilter === 'paper'
                  ? 'Aún no hay cuentas Paper. Se crean al desplegar una estrategia desde Backtesting.'
                  : 'No hay cuentas demo activas.'}
              </p>
            ) : (
              activeAccounts.map((account) => (
                <AccountListItem
                  key={account.id}
                  account={account}
                  selected={account.id === effectiveSelectedId}
                  isWorking={account.id === activeAccountId}
                  totalEquity={equityByAccountId.get(account.id)}
                  onSelect={() => setSelectedId(account.id)}
                />
              ))
            )}
          </div>

          {closedAccounts.length > 0 && (
            <div className="pt-1">
              <button
                type="button"
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => setShowClosed((v) => !v)}
              >
                {showClosed ? 'Ocultar cerradas' : `Mostrar cerradas (${closedAccounts.length})`}
              </button>
              {showClosed && (
                <div className="mt-2 space-y-2">
                  {closedAccounts.map((account) => (
                    <AccountListItem
                      key={account.id}
                      account={account}
                      selected={account.id === effectiveSelectedId}
                      totalEquity={equityByAccountId.get(account.id)}
                      onSelect={() => setSelectedId(account.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>

        <section>
          {selectedAccount ? (
            <AccountDetailPanel
              key={selectedAccount.id}
              account={selectedAccount}
              onDelete={() => setSelectedId(null)}
              initialTab={(() => {
                const t = searchParams.get('tab');
                return t === 'config' ||
                  t === 'resumen' ||
                  t === 'posiciones' ||
                  t === 'movimientos'
                  ? t
                  : undefined;
              })()}
              focus={searchParams.get('focus')}
            />
          ) : (
            <div className="flex min-h-[320px] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
              Selecciona una cuenta a la izquierda.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
