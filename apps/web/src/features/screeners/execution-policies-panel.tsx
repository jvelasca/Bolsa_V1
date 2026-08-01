import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Zap } from 'lucide-react';
import { useState } from 'react';
import {
  ALERT_CHANNEL_LABELS,
  DEFAULT_ALERT_CHANNELS,
  SIGNAL_KIND_LABELS,
  type AlertChannelType,
  type ExecutionMode,
  type SignalKind,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';
import { PAPER_PATH_RADAR, PAPER_PATHS_COMPARE, defaultRequireValidatedBacktest } from '@/features/settings/paper-paths-copy';

const MODE_LABELS: Record<ExecutionMode, string> = {
  inform_only: 'Solo informar',
  alert: 'Alerta',
  paper_auto: PAPER_PATH_RADAR.modeLabel,
  live_auto: 'Live dry-run (sin broker)',
};

const MODE_OPTIONS: ExecutionMode[] = ['inform_only', 'alert', 'paper_auto', 'live_auto'];
const KIND_OPTIONS: SignalKind[] = ['entry_long', 'exit', 'entry_short', 'watch'];
const CHANNEL_OPTIONS: AlertChannelType[] = ['toast', 'webhook', 'email'];

export function ExecutionPoliciesPanel({ embedded }: { embedded?: boolean } = {}) {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [mode, setMode] = useState<ExecutionMode>('inform_only');
  const [accountId, setAccountId] = useState('');
  const [signalKinds, setSignalKinds] = useState<SignalKind[]>(['entry_long', 'exit']);
  const [channels, setChannels] = useState<AlertChannelType[]>([...DEFAULT_ALERT_CHANNELS]);
  const [webhookUrl, setWebhookUrl] = useState('');
  const [emailTo, setEmailTo] = useState('');
  const [requireValidatedBacktest, setRequireValidatedBacktest] = useState(false);

  const policiesQuery = useQuery({
    queryKey: ['execution-policies'],
    queryFn: () => api.getExecutionPolicies(),
  });

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => (await api.getAccounts()).data,
  });

  const policies = policiesQuery.data?.data ?? [];
  const paperAccounts = (accountsQuery.data ?? []).filter(
    (account) => account.type === 'paper' || account.type === 'simulated',
  );

  const createMutation = useMutation({
    mutationFn: () =>
      api.createExecutionPolicy({
        name: name.trim(),
        mode,
        accountId: mode === 'paper_auto' ? accountId || null : null,
        signalKinds,
        channels: mode === 'alert' ? channels : undefined,
        webhookUrl: mode === 'alert' && channels.includes('webhook') ? webhookUrl || null : null,
        emailTo: mode === 'alert' && channels.includes('email') ? emailTo || null : null,
        requireValidatedBacktest,
        enabled: true,
      }),
    onSuccess: () => {
      setShowCreate(false);
      setName('');
      setMode('inform_only');
      setAccountId('');
      setSignalKinds(['entry_long', 'exit']);
      setChannels([...DEFAULT_ALERT_CHANNELS]);
      setWebhookUrl('');
      setEmailTo('');
      setRequireValidatedBacktest(false);
      void queryClient.invalidateQueries({ queryKey: ['execution-policies'] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.updateExecutionPolicy(id, { enabled }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['execution-policies'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteExecutionPolicy(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['execution-policies'] }),
  });

  const createError =
    createMutation.error instanceof ApiError
      ? createMutation.error.message
      : createMutation.error instanceof Error
        ? createMutation.error.message
        : null;

  function toggleKind(kind: SignalKind) {
    setSignalKinds((current) =>
      current.includes(kind) ? current.filter((k) => k !== kind) : [...current, kind],
    );
  }

  function toggleChannel(channel: AlertChannelType) {
    setChannels((current) =>
      current.includes(channel) ? current.filter((c) => c !== channel) : [...current, channel],
    );
  }

  const canCreate =
    name.trim().length > 0 &&
    signalKinds.length > 0 &&
    (mode !== 'paper_auto' || Boolean(accountId));

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Políticas de ejecución"
      description={
        embedded
          ? undefined
          : `${PAPER_PATHS_COMPARE} Informar, alertar o paper_auto (P5).`
      }
      icon={Zap}
    >
        <Button type="button" size="sm" variant="outline" onClick={() => setShowCreate((v) => !v)}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Nueva política
        </Button>

        {showCreate && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
            <label className="block text-sm">
              Nombre
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="IBEX long paper"
              />
            </label>
            <label className="block text-sm">
              Modo
              <select
                value={mode}
                onChange={(e) => {
                  const next = e.target.value as ExecutionMode;
                  setMode(next);
                  if (defaultRequireValidatedBacktest(next)) {
                    setRequireValidatedBacktest(true);
                  }
                }}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                {MODE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {MODE_LABELS[option]}
                  </option>
                ))}
              </select>
            </label>
            {mode === 'paper_auto' && (
              <>
                <p className="rounded-md border border-amber-500/30 bg-amber-500/5 px-2.5 py-2 text-[11px] text-amber-100/90">
                  {PAPER_PATH_RADAR.warnLine}
                </p>
                <label className="block text-sm">
                  Cuenta paper
                  <select
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  >
                    <option value="">Selecciona cuenta…</option>
                    {paperAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} ({account.type})
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <fieldset className="space-y-1 text-sm">
              <legend className="text-sm">Señales</legend>
              <div className="flex flex-wrap gap-2">
                {KIND_OPTIONS.map((kind) => (
                  <label key={kind} className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      checked={signalKinds.includes(kind)}
                      onChange={() => toggleKind(kind)}
                    />
                    {SIGNAL_KIND_LABELS[kind]}
                  </label>
                ))}
              </div>
            </fieldset>
            {mode === 'alert' && (
              <>
                <fieldset className="space-y-1 text-sm">
                  <legend className="text-sm">Canales</legend>
                  <div className="flex flex-wrap gap-2">
                    {CHANNEL_OPTIONS.map((channel) => (
                      <label key={channel} className="flex items-center gap-1 text-xs">
                        <input
                          type="checkbox"
                          checked={channels.includes(channel)}
                          onChange={() => toggleChannel(channel)}
                        />
                        {ALERT_CHANNEL_LABELS[channel]}
                      </label>
                    ))}
                  </div>
                </fieldset>
                {channels.includes('webhook') && (
                  <label className="block text-sm">
                    Webhook URL
                    <input
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      placeholder="https://…"
                    />
                  </label>
                )}
                {channels.includes('email') && (
                  <label className="block text-sm">
                    Email
                    <input
                      value={emailTo}
                      onChange={(e) => setEmailTo(e.target.value)}
                      className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      placeholder="tu@email.com"
                    />
                  </label>
                )}
              </>
            )}
            <label className="flex flex-col gap-1 text-sm">
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={requireValidatedBacktest}
                  onChange={(e) => setRequireValidatedBacktest(e.target.checked)}
                />
                {mode === 'paper_auto'
                  ? PAPER_PATH_RADAR.requireValidatedLabel
                  : 'Requiere backtest validado'}
              </span>
              {mode === 'paper_auto' && !requireValidatedBacktest && (
                <span className="pl-6 text-[11px] text-muted-foreground">
                  {PAPER_PATH_RADAR.requireValidatedHint}
                </span>
              )}
            </label>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                disabled={!canCreate || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                {createMutation.isPending ? 'Creando…' : 'Crear política'}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setShowCreate(false)}>
                Cancelar
              </Button>
            </div>
            {createError && <p className="text-xs text-destructive">{createError}</p>}
          </div>
        )}

        {policiesQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Cargando políticas…</p>
        ) : policies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sin políticas. Crea una para ejecutar coincidencias desde resultados de rastreo.
          </p>
        ) : (
          <ul className="space-y-2">
            {policies.map((policy) => (
              <li
                key={policy.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border px-3 py-2"
              >
                <div>
                  <p className="font-medium text-sm">{policy.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {MODE_LABELS[policy.mode]} · {policy.signalKinds.length} señales
                    {policy.requireValidatedBacktest ? ' · backtest requerido' : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={toggleMutation.isPending}
                    onClick={() =>
                      toggleMutation.mutate({ id: policy.id, enabled: !policy.enabled })
                    }
                  >
                    {policy.enabled ? 'Activa' : 'Pausada'}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(policy.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
    </ScreenerPanelShell>
  );
}
