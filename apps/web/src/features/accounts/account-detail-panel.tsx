import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowUpFromLine } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { InvestmentAccountDto, LedgerEntryDto } from '@bolsa/shared';
import { formatLedgerEntryLabel, ledgerEntryHint } from '@bolsa/shared';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { inputClassName } from '@/components/ui/dialog';
import { AccountInvestorProfileSelect } from '@/features/accounts/account-investor-profile-select';
import { AccountSettingsDialog } from '@/features/accounts/account-settings-dialog';
import { formatPaperLabEvidence } from '@/features/accounts/paper-lab-evidence';
import { PAPER_PATH_LAB } from '@/features/settings/paper-paths-copy';
import { useActivateAccount } from '@/features/accounts/use-active-account';
import { formatPrice } from '@/features/charts/chart-utils';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useActiveAccountStore } from '@/stores/active-account-store';

type DetailTab = 'resumen' | 'posiciones' | 'movimientos' | 'config';

type AccountDetailPanelProps = {
  account: InvestmentAccountDto;
  onDelete: () => void;
};

export function AccountDetailPanel({ account, onDelete }: AccountDetailPanelProps) {
  const queryClient = useQueryClient();
  const activeAccountId = useActiveAccountStore((s) => s.activeAccountId);
  const activateAccount = useActivateAccount();
  const isWorkingAccount = activeAccountId === account.id;
  const [tab, setTab] = useState<DetailTab>('resumen');
  const [editName, setEditName] = useState(account.name);
  const [editDescription, setEditDescription] = useState(account.description ?? '');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [cashTab, setCashTab] = useState<'deposit' | 'withdraw'>('deposit');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isClosed = account.status === 'closed';
  const isSimulated = account.type === 'simulated';
  const isPaper = account.type === 'paper';

  useEffect(() => {
    setEditName(account.name);
    setEditDescription(account.description ?? '');
    setError(null);
    setMessage(null);
  }, [account.id, account.name, account.description]);

  const summaryQuery = useQuery({
    queryKey: ['account-summary', account.id],
    queryFn: async () => (await api.getAccountSummary(account.id)).data,
  });

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', account.id],
    queryFn: api.getPortfolio,
    enabled: !isClosed,
  });

  const ledgerQuery = useQuery({
    queryKey: ['ledger', account.id],
    queryFn: async () => (await api.getAccountLedger(account.id, 30)).data,
  });

  const summary = summaryQuery.data;
  const portfolio = portfolioQuery.data?.data;
  const ledger = ledgerQuery.data ?? [];

  const updateMutation = useMutation({
    mutationFn: () =>
      api.updateAccount(account.id, {
        name: editName.trim(),
        description: editDescription.trim() || null,
      }),
    onSuccess: () => {
      setError(null);
      setMessage('Datos actualizados.');
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summaries'] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const closeMutation = useMutation({
    mutationFn: () => api.closeAccount(account.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summaries'] });
      setMessage('Cuenta cerrada. El historial se conserva para auditoría.');
    },
    onError: (e: Error) => setError(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteAccount(account.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      void queryClient.invalidateQueries({ queryKey: ['account-summaries'] });
      onDelete();
    },
    onError: (e: Error) => setError(e.message),
  });

  const cashMutation = useMutation({
    mutationFn: async () => {
      const parsed = Number(amount.replace(',', '.'));
      if (!Number.isFinite(parsed) || parsed <= 0) {
        throw new Error('Importe inválido');
      }
      if (cashTab === 'deposit') {
        return api.depositCash(account.id, { amount: parsed, note: note.trim() || null });
      }
      return api.withdrawCash(account.id, { amount: parsed, note: note.trim() || null });
    },
    onSuccess: () => {
      setAmount('');
      setNote('');
      setMessage('Movimiento registrado.');
      void queryClient.invalidateQueries({ queryKey: ['account-summary', account.id] });
      void queryClient.invalidateQueries({ queryKey: ['portfolio', account.id] });
      void queryClient.invalidateQueries({ queryKey: ['ledger', account.id] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const tabs: { id: DetailTab; label: string }[] = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'posiciones', label: 'Posiciones' },
    { id: 'movimientos', label: 'Movimientos' },
    { id: 'config', label: 'Configuración' },
  ];

  return (
    <div className="flex min-h-[480px] flex-col rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold">{account.name}</h3>
              {isWorkingAccount && !isClosed && (
                <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-primary">
                  Activa
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {isSimulated ? 'Demo' : isPaper ? 'Paper (futuro · broker)' : 'Live (reservado)'} ·{' '}
              {account.currency}
              {isClosed ? ' · cerrada' : ''}
            </p>
            {isPaper && account.strategyDefinitionId && (
              <p className="mt-1 text-xs text-muted-foreground">
                Estrategia:{' '}
                <Link
                  to="/backtests?tab=strategies"
                  className="font-mono text-primary hover:underline"
                >
                  {account.strategyDefinitionId}
                </Link>
                {account.sourceBacktestRunId ? (
                  <>
                    {' '}
                    · backtest{' '}
                    <span className="font-mono">{account.sourceBacktestRunId.slice(0, 8)}…</span>
                  </>
                ) : null}
              </p>
            )}
            {isPaper && (
              <p
                className="mt-1.5 text-[11px] text-muted-foreground"
                title={
                  account.labEvidence?.note ??
                  'Provenance lab al desplegar. No es gate de producción ni auto-live.'
                }
              >
                Evidencia lab:{' '}
                <span className="text-foreground">
                  {formatPaperLabEvidence(account.labEvidence)}
                </span>
                {' · '}
                {PAPER_PATH_LAB.accountNote}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!isClosed && !isWorkingAccount && (
              <button
                type="button"
                disabled={activateAccount.isPending}
                onClick={() => {
                  void activateAccount.mutateAsync(account.id).then(() => {
                    setMessage('Cuenta Activa cambiada. Se restaurará al reabrir la app.');
                  });
                }}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
              >
                Usar ahora
              </button>
            )}
            <Link to="/history" className="text-xs text-primary hover:underline">
              Historial completo
            </Link>
            <Link to="/fiscal" className="text-xs text-muted-foreground hover:text-primary">
              Informe fiscal
            </Link>
          </div>
        </div>
        <div className="mt-3 flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                'rounded-md px-3 py-1 text-sm',
                tab === t.id ? 'bg-primary/15 text-primary' : 'text-muted-foreground hover:bg-accent',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {message && <p className="mb-3 text-sm text-success">{message}</p>}
        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

        {tab === 'resumen' && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Patrimonio" value={summary ? formatPrice(summary.totalEquity) : '—'} />
            <Metric label="Efectivo" value={summary ? formatPrice(summary.cash) : '—'} />
            <Metric
              label="P&amp;L no realizado"
              value={summary ? formatPrice(summary.totalUnrealizedPnl) : '—'}
              tone={
                summary
                  ? summary.totalUnrealizedPnl >= 0
                    ? 'positive'
                    : 'negative'
                  : undefined
              }
            />
            <Metric label="Posiciones" value={summary ? String(summary.positionsCount) : '—'} />
          </div>
        )}

        {tab === 'posiciones' && (
          <div className="space-y-2">
            {!portfolio?.positions.length && (
              <p className="text-sm text-muted-foreground">Sin posiciones abiertas.</p>
            )}
            {portfolio?.positions.map((pos) => (
              <div
                key={pos.id}
                className="flex justify-between rounded-md border border-border/60 px-3 py-2 text-sm"
              >
                <span>
                  <Link to={`/instruments/${pos.instrumentId}`} className="font-medium hover:text-primary">
                    {pos.symbol}
                  </Link>
                  <span className="ml-2 text-muted-foreground">{pos.quantity} uds.</span>
                </span>
                <span className="tabular-nums">{formatPrice(pos.marketValue)}</span>
              </div>
            ))}
          </div>
        )}

        {tab === 'movimientos' && (
          <div className="space-y-4">
            {!isClosed && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Capital externo (simulado)</CardTitle>
                  <CardDescription>Depósitos y retiradas en modo demo</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap items-end gap-2">
                  <button
                    type="button"
                    onClick={() => setCashTab('deposit')}
                    className={cn(
                      'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs',
                      cashTab === 'deposit' && 'border-primary text-primary',
                    )}
                  >
                    <ArrowDownToLine className="h-3 w-3" /> Depósito
                  </button>
                  <button
                    type="button"
                    onClick={() => setCashTab('withdraw')}
                    className={cn(
                      'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs',
                      cashTab === 'withdraw' && 'border-primary text-primary',
                    )}
                  >
                    <ArrowUpFromLine className="h-3 w-3" /> Retirada
                  </button>
                  <input
                    className={cn(inputClassName, 'w-28')}
                    placeholder="Importe"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                  />
                  <input
                    className={cn(inputClassName, 'min-w-[140px] flex-1')}
                    placeholder="Nota"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <button
                    type="button"
                    disabled={cashMutation.isPending}
                    onClick={() => void cashMutation.mutateAsync()}
                    className="rounded-md bg-primary px-3 py-2 text-xs text-primary-foreground"
                  >
                    Confirmar
                  </button>
                </CardContent>
              </Card>
            )}
            <p className="text-xs text-muted-foreground">
              Los importes negativos (rojo) salen de tu efectivo; los positivos (verde) lo aumentan.
              Las comisiones de cada operación aparecen como líneas «Comisión y cargos» separadas de la
              compra o venta.
            </p>
            <ul className="space-y-2 text-sm">
              {ledger.map((entry) => (
                <LedgerMovementRow key={entry.id} entry={entry} />
              ))}
            </ul>
          </div>
        )}

        {tab === 'config' && (
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-muted/20 p-3 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Cuenta Activa</p>
              <p className="mt-1">
                Es la que usa Trading, la barra inferior y las operaciones. Se guarda al cerrar la
                app y se restaura al volver. Las demás cuentas quedan disponibles para cambiar cuando
                quieras (otras demos / mercados). Paper broker = futuro.
                {isWorkingAccount ? (
                  <span className="text-primary"> Esta es la activa.</span>
                ) : (
                  !isClosed && (
                    <>
                      {' '}
                      <button
                        type="button"
                        className="text-primary underline-offset-2 hover:underline disabled:opacity-50"
                        disabled={activateAccount.isPending}
                        onClick={() => {
                          void activateAccount.mutateAsync(account.id).then(() => {
                            setMessage('Cuenta Activa cambiada.');
                          });
                        }}
                      >
                        Usar ahora
                      </button>
                    </>
                  )
                )}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-muted-foreground">Nombre</span>
                <input
                  className={inputClassName}
                  value={editName}
                  disabled={isClosed}
                  onChange={(e) => setEditName(e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm sm:col-span-2">
                <span className="text-muted-foreground">Descripción</span>
                <input
                  className={inputClassName}
                  value={editDescription}
                  disabled={isClosed}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
              </label>
            </div>
            {!isClosed && (
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  void updateMutation.mutateAsync();
                }}
                className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
              >
                Guardar datos
              </button>
            )}
            {!isClosed ? (
              <AccountInvestorProfileSelect
                accountId={account.id}
                activeProfileId={account.activeProfileId}
              />
            ) : null}
            <div className="rounded-md border border-border bg-muted/20 p-3 text-sm">
              <p className="font-medium">Comisiones y fiscal</p>
              <p className="text-muted-foreground">
                {account.settings?.commission.label ?? '—'} ·{' '}
                {account.settings?.tax.jurisdiction ?? '—'} ·{' '}
                {account.settings?.tax.costBasisMethod.toUpperCase() ?? '—'}
              </p>
              {!isClosed && (
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="mt-2 text-primary hover:underline"
                >
                  Editar perfil, comisiones y fiscal →
                </button>
              )}
            </div>
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Gestión contable (demo)
              </p>
              {!isClosed && (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm('¿Cerrar esta cuenta? Se conservará el historial para auditoría.')) {
                      void closeMutation.mutateAsync();
                    }
                  }}
                  className="mr-2 rounded-md border border-amber-500/50 px-3 py-1.5 text-sm text-amber-400 hover:bg-amber-500/10"
                >
                  Cerrar cuenta
                </button>
              )}
              {isSimulated && isClosed && (
                <button
                  type="button"
                  onClick={() => {
                    if (
                      window.confirm(
                        '¿Eliminar definitivamente esta cuenta demo? Esta acción no se puede deshacer.',
                      )
                    ) {
                      void deleteMutation.mutateAsync();
                    }
                  }}
                  className="rounded-md border border-destructive/50 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10"
                >
                  Eliminar cuenta (demo)
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <AccountSettingsDialog
        account={account}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}

function LedgerMovementRow({ entry }: { entry: LedgerEntryDto }) {
  const hint = ledgerEntryHint(entry);
  return (
    <li className="flex items-start justify-between gap-3 border-b border-border/40 py-2">
      <div className="min-w-0">
        <p className="font-medium">{formatLedgerEntryLabel(entry)}</p>
        {entry.description && (
          <p className="text-xs text-muted-foreground">{entry.description}</p>
        )}
        {hint && !entry.description && (
          <p className="text-xs text-muted-foreground">{hint}</p>
        )}
        {entry.symbol && (
          <p className="text-xs text-muted-foreground">
            {entry.symbol}
            {entry.quantity != null && entry.price != null
              ? ` · ${entry.quantity} × ${formatPrice(entry.price)}`
              : ''}
          </p>
        )}
      </div>
      <span
        className={cn(
          'shrink-0 tabular-nums',
          entry.amount >= 0 ? 'text-success' : 'text-destructive',
        )}
      >
        {formatPrice(entry.amount)}
      </span>
    </li>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'positive' | 'negative';
}) {
  return (
    <div className="rounded-md border border-border/60 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          'text-lg font-semibold tabular-nums',
          tone === 'positive' && 'text-success',
          tone === 'negative' && 'text-destructive',
        )}
      >
        {value}
      </p>
    </div>
  );
}
