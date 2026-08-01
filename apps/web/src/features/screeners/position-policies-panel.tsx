import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LogOut, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type {
  PositionExecutionMode,
  PositionExitEvalResultDto,
  PositionExitEvalStatus,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { useActiveAccountQueryKey } from '@/stores/active-account-store';
import { useScreenerPreferencesStore } from '@/stores/screener-preferences-store';
import { Button } from '@/components/ui/button';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';

const MODE_LABELS: Record<PositionExecutionMode, string> = {
  manual: 'Manual',
  exit_strategy: 'Salida por estrategia',
  full_auto: 'Auto (política de ejecución)',
};

const MODE_OPTIONS: PositionExecutionMode[] = ['manual', 'exit_strategy', 'full_auto'];

const EXIT_STATUS_LABELS: Record<PositionExitEvalStatus, string> = {
  no_policy: 'Sin política',
  manual: 'Manual',
  no_exit_strategy: 'Sin estrategia salida',
  no_bars: 'Sin barras',
  no_signal: 'Sin señal',
  exit_signal: 'Señal de salida',
  executed: 'Ejecutado',
  skipped: 'Omitido',
  error: 'Error',
};

export function PositionPoliciesPanel({ embedded }: { embedded?: boolean } = {}) {
  const queryClient = useQueryClient();
  const accountId = useActiveAccountQueryKey();
  const accountScope = accountId;
  const positionPanel = useScreenerPreferencesStore((state) => state.positionPanel);
  const patchPositionPanel = useScreenerPreferencesStore((state) => state.patchPositionPanel);

  const [showCreate, setShowCreate] = useState(false);
  const [instrumentId, setInstrumentId] = useState('');
  const [lastEvalResults, setLastEvalResults] = useState<PositionExitEvalResultDto[]>([]);
  const { mode, executeTrades, exitStrategyId, executionPolicyId } = positionPanel;

  const portfolioQuery = useQuery({
    queryKey: ['portfolio', accountScope],
    queryFn: api.getPortfolio,
    enabled: Boolean(accountId),
  });

  const policiesQuery = useQuery({
    queryKey: ['position-policies', accountScope],
    queryFn: () => api.getPositionPolicies(accountId!),
    enabled: Boolean(accountId),
  });

  const strategiesQuery = useQuery({
    queryKey: ['strategies'],
    queryFn: api.getStrategies,
  });

  const executionPoliciesQuery = useQuery({
    queryKey: ['execution-policies'],
    queryFn: () => api.getExecutionPolicies(true),
  });

  const positions = portfolioQuery.data?.data.positions ?? [];
  const policies = policiesQuery.data?.data ?? [];
  const strategies = strategiesQuery.data?.data ?? [];
  const executionPolicies = executionPoliciesQuery.data?.data ?? [];

  const policyInstrumentIds = new Set(policies.map((p) => p.instrumentId));
  const availablePositions = positions.filter((p) => !policyInstrumentIds.has(p.instrumentId));

  const symbolByInstrumentId = Object.fromEntries(
    positions.map((p) => [p.instrumentId, p.symbol]),
  );

  const createMutation = useMutation({
    mutationFn: () =>
      api.createPositionPolicy({
        accountId: accountId!,
        instrumentId,
        mode,
        exitStrategyDefinitionId:
          mode === 'exit_strategy' ? exitStrategyId || null : null,
        executionPolicyId: mode === 'full_auto' ? executionPolicyId || null : null,
      }),
    onSuccess: () => {
      setShowCreate(false);
      setInstrumentId('');
      patchPositionPanel({ exitStrategyId: '', executionPolicyId: '' });
      void queryClient.invalidateQueries({ queryKey: ['position-policies', accountScope] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deletePositionPolicy(id),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['position-policies', accountScope] }),
  });

  const evaluateMutation = useMutation({
    mutationFn: () =>
      api.evaluatePositionExits(accountId!, { executeTrades, timeframe: '1d' }),
    onSuccess: (response) => {
      setLastEvalResults(response.data.results);
      void queryClient.invalidateQueries({ queryKey: ['portfolio', accountScope] });
    },
  });

  const createError =
    createMutation.error instanceof ApiError
      ? createMutation.error.message
      : createMutation.error instanceof Error
        ? createMutation.error.message
        : null;

  const canCreate =
    Boolean(instrumentId) &&
    (mode === 'manual' ||
      (mode === 'exit_strategy' && exitStrategyId) ||
      (mode === 'full_auto' && executionPolicyId));

  if (!accountId) {
    return (
      <ScreenerPanelShell embedded={embedded} title="Políticas de posición" icon={LogOut}>
        <p className="text-sm text-muted-foreground">
          Selecciona una cuenta activa para gestionar políticas de salida (P6/P7).
        </p>
      </ScreenerPanelShell>
    );
  }

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Políticas de posición"
      description={
        embedded ? undefined : 'Política por posición abierta — evaluar salidas con rules engine P7.'
      }
      icon={LogOut}
    >
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={availablePositions.length === 0}
            onClick={() => setShowCreate((v) => !v)}
          >
            <Plus className="mr-1 h-3.5 w-3.5" />
            Nueva política
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={evaluateMutation.isPending || policies.length === 0}
            onClick={() => evaluateMutation.mutate()}
          >
            {evaluateMutation.isPending ? 'Evaluando…' : 'Evaluar salidas'}
          </Button>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={executeTrades}
              onChange={(e) => patchPositionPanel({ executeTrades: e.target.checked })}
            />
            Ejecutar trades
          </label>
        </div>

        {showCreate && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
            <label className="block text-sm">
              Posición
              <select
                value={instrumentId}
                onChange={(e) => setInstrumentId(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Selecciona…</option>
                {availablePositions.map((pos) => (
                  <option key={pos.instrumentId} value={pos.instrumentId}>
                    {pos.symbol} · {pos.quantity} uds
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Modo
              <select
                value={mode}
                onChange={(e) =>
                  patchPositionPanel({ mode: e.target.value as PositionExecutionMode })
                }
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                {MODE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {MODE_LABELS[option]}
                  </option>
                ))}
              </select>
            </label>
            {mode === 'exit_strategy' && (
              <label className="block text-sm">
                Estrategia de salida
                <select
                  value={exitStrategyId}
                  onChange={(e) => patchPositionPanel({ exitStrategyId: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Selecciona…</option>
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {mode === 'full_auto' && (
              <label className="block text-sm">
                Política de ejecución
                <select
                  value={executionPolicyId}
                  onChange={(e) => patchPositionPanel({ executionPolicyId: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Selecciona…</option>
                  {executionPolicies.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name} ({policy.mode})
                    </option>
                  ))}
                </select>
              </label>
            )}
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
            Sin políticas. Crea una para posiciones abiertas con salida automática.
          </p>
        ) : (
          <ul className="space-y-2">
            {policies.map((policy) => (
              <li
                key={policy.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border px-3 py-2"
              >
                <div>
                  <p className="font-medium text-sm">
                    {symbolByInstrumentId[policy.instrumentId] ?? policy.instrumentId.slice(0, 8)}
                  </p>
                  <p className="text-xs text-muted-foreground">{MODE_LABELS[policy.mode]}</p>
                </div>
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
              </li>
            ))}
          </ul>
        )}

        {lastEvalResults.length > 0 && (
          <div className="space-y-2 border-t border-border pt-3">
            <p className="text-xs font-medium text-muted-foreground">Última evaluación</p>
            <ul className="space-y-1 text-xs">
              {lastEvalResults.map((item) => (
                <li
                  key={item.instrumentId}
                  className="flex flex-wrap justify-between gap-2 rounded border border-border px-2 py-1.5"
                >
                  <span className="font-medium">{item.symbol}</span>
                  <span className="text-muted-foreground">
                    {EXIT_STATUS_LABELS[item.status] ?? item.status}
                    {item.reason ? ` · ${item.reason}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {evaluateMutation.error instanceof ApiError && (
          <p className="text-xs text-destructive">{evaluateMutation.error.message}</p>
        )}
    </ScreenerPanelShell>
  );
}
