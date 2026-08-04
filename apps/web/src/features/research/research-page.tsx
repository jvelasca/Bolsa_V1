import { useQuery } from '@tanstack/react-query';
import { useMemo, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { ResearchTrialDto, ResearchTrialSort } from '@bolsa/shared';
import { api } from '@/lib/api';
import { formatPct } from '@/features/charts/chart-utils';
import { ResearchLabEvidenceSummary } from '@/features/research/research-lab-evidence-summary';
import { ResearchTrialResultBlock } from '@/features/research/research-trial-result-block';
import { AsesorOpinionesPanel } from '@/features/research/asesor-opiniones-panel';
import { AsesorDailyOpsPanel } from '@/features/research/asesor-daily-ops-panel';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

type HubTab = 'dashboard' | 'diario' | 'history' | 'opiniones';

function parseTab(raw: string | null): HubTab {
  if (raw === 'history') return 'history';
  if (raw === 'opiniones') return 'opiniones';
  if (raw === 'diario') return 'diario';
  return 'dashboard';
}

function metricNum(m: Record<string, number | string | null>, key: string): number | null {
  const v = m[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function formatShortDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function ResearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get('tab'));
  const selectedTrialId = searchParams.get('trialId');

  const [instrumentId, setInstrumentId] = useState(searchParams.get('instrumentId') ?? '');
  const [proposedBy, setProposedBy] = useState(searchParams.get('proposedBy') ?? '');
  const [presetKey, setPresetKey] = useState(searchParams.get('presetKey') ?? '');
  const [sort, setSort] = useState<ResearchTrialSort>('created_at');
  const [page, setPage] = useState(0);
  const pageSize = 30;

  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
  });

  const summaryQuery = useQuery({
    queryKey: ['research', 'summary'],
    queryFn: api.getLaboratoryResearchSummary,
  });

  const labHealthQuery = useQuery({
    queryKey: ['research', 'lab-health'],
    queryFn: api.getLabHealth,
  });

  const trialsQuery = useQuery({
    queryKey: [
      'research',
      'trials',
      instrumentId,
      proposedBy,
      presetKey,
      sort,
      page,
    ],
    queryFn: () =>
      api.getResearchTrials({
        instrumentId: instrumentId || undefined,
        proposedBy: proposedBy || undefined,
        presetKey: presetKey || undefined,
        sort,
        sortDir: 'desc',
        limit: pageSize,
        offset: page * pageSize,
      }),
    enabled: tab === 'history',
  });

  const trialDetailQuery = useQuery({
    queryKey: ['research', 'trial', selectedTrialId],
    queryFn: () => api.getResearchTrial(selectedTrialId!),
    enabled: Boolean(selectedTrialId),
  });

  const symbolById = useMemo(() => {
    const map = new Map<string, string>();
    for (const inst of instrumentsQuery.data?.data ?? []) {
      map.set(inst.id, inst.symbol);
    }
    return map;
  }, [instrumentsQuery.data]);

  function setTab(next: HubTab) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('tab', next);
    if (next === 'dashboard') nextParams.delete('trialId');
    setSearchParams(nextParams);
  }

  function selectTrial(id: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('tab', 'history');
    nextParams.set('trialId', id);
    setSearchParams(nextParams);
  }

  function patchHistoryFilters(patch: {
    instrumentId?: string;
    proposedBy?: string;
    presetKey?: string;
  }) {
    const nextInstrumentId = patch.instrumentId !== undefined ? patch.instrumentId : instrumentId;
    const nextProposedBy = patch.proposedBy !== undefined ? patch.proposedBy : proposedBy;
    const nextPresetKey = patch.presetKey !== undefined ? patch.presetKey : presetKey;
    if (patch.instrumentId !== undefined) setInstrumentId(patch.instrumentId);
    if (patch.proposedBy !== undefined) setProposedBy(patch.proposedBy);
    if (patch.presetKey !== undefined) setPresetKey(patch.presetKey);
    setPage(0);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('tab', 'history');
    if (nextInstrumentId) nextParams.set('instrumentId', nextInstrumentId);
    else nextParams.delete('instrumentId');
    if (nextProposedBy) nextParams.set('proposedBy', nextProposedBy);
    else nextParams.delete('proposedBy');
    if (nextPresetKey) nextParams.set('presetKey', nextPresetKey);
    else nextParams.delete('presetKey');
    setSearchParams(nextParams, { replace: true });
  }

  const summary = summaryQuery.data?.data;
  const labHealth = labHealthQuery.data?.data;
  const trials = trialsQuery.data?.data ?? [];
  const total = trialsQuery.data?.total ?? 0;
  const selected: ResearchTrialDto | undefined = trialDetailQuery.data?.data;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Asesor</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Observatorio del laboratorio y dictámenes del Estudio. Ruta{' '}
          <code className="text-xs">/research</code> (API sin cambios). Sin Belief ni Discovery
          Score.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <HubTabButton active={tab === 'dashboard'} onClick={() => setTab('dashboard')}>
          Resumen
        </HubTabButton>
        <HubTabButton active={tab === 'diario'} onClick={() => setTab('diario')}>
          Diario
        </HubTabButton>
        <HubTabButton active={tab === 'history'} onClick={() => setTab('history')}>
          Historial
        </HubTabButton>
        <HubTabButton active={tab === 'opiniones'} onClick={() => setTab('opiniones')}>
          Opiniones
        </HubTabButton>
      </div>

      {tab === 'diario' && <AsesorDailyOpsPanel />}

      {tab === 'opiniones' && <AsesorOpinionesPanel />}

      {tab === 'dashboard' && (
        <div className="space-y-4">
          {summaryQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Cargando resumen del laboratorio…</p>
          )}
          {summaryQuery.isError && (
            <p className="text-sm text-destructive">
              No se pudo cargar el resumen del laboratorio. Revisa la API e inténtalo de nuevo.
            </p>
          )}
          {summary && summary.totalTrials === 0 && (
            <Card>
              <CardContent className="space-y-2 py-4">
                <p className="text-sm text-muted-foreground">
                  Aún no hay trials en el ledger. Lanza una prueba en Backtesting para llenar el
                  Observatory.
                </p>
                <Link
                  to="/backtests?tab=run"
                  className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
                >
                  Ir a Probar estrategia
                </Link>
              </CardContent>
            </Card>
          )}
          {summary && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Total trials" value={String(summary.totalTrials)} />
                <Stat label="K consumido" value={String(summary.totalK)} />
                <Stat label="Instrumentos" value={String(summary.activeInstruments)} />
                <Stat
                  label="Sharpe medio"
                  value={summary.avgSharpe == null ? '—' : summary.avgSharpe.toFixed(2)}
                />
              </div>

              {labHealthQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Cargando Lab Health…</p>
              )}
              {labHealth && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Lab Health</CardTitle>
                    <CardDescription>
                      Cobertura de métricas IS, zero-trades y campañas (Q0.1)
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Stat
                        label="Sharpe presente"
                        value={`${labHealth.coverage.sharpeRatio.pct.toFixed(1)}%`}
                      />
                      <Stat
                        label="Sortino presente"
                        value={`${labHealth.coverage.sortinoRatio.pct.toFixed(1)}%`}
                      />
                      <Stat
                        label="Calmar presente"
                        value={`${labHealth.coverage.calmarRatio.pct.toFixed(1)}%`}
                      />
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Stat
                        label="tradeCount=0"
                        value={`${labHealth.zeroTradePct.toFixed(1)}% (${labHealth.zeroTradeCount})`}
                      />
                      <Stat label="Campañas" value={String(labHealth.campaignCount)} />
                      <Stat
                        label="Sin trials"
                        value={`${labHealth.instrumentsWithoutTrials} / ${labHealth.activeInstruments}`}
                      />
                    </div>
                    {labHealth.campaigns.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        Top campañas:{' '}
                        {labHealth.campaigns
                          .slice(0, 5)
                          .map((c) => `${c.campaignId} (${c.trials})`)
                          .join(' · ')}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">{labHealth.caveat}</p>
                  </CardContent>
                </Card>
              )}

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Por instrumento</CardTitle>
                    <CardDescription>Trials, K y Sharpe medio</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {summary.byInstrument.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aún no hay trials.</p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {summary.byInstrument.map((row) => (
                          <li
                            key={row.instrumentId}
                            className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-2 last:border-0"
                          >
                            <button
                              type="button"
                              className="font-medium text-primary hover:underline"
                              onClick={() => {
                                patchHistoryFilters({ instrumentId: row.instrumentId });
                              }}
                            >
                              {row.symbol}
                            </button>
                            <span className="text-muted-foreground tabular-nums">
                              {row.trials} tri · K:{row.kConsumed} · S:
                              {row.avgSharpe == null ? '—' : row.avgSharpe.toFixed(2)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Por origen</CardTitle>
                    <CardDescription>human / grid / optuna / …</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {summary.byOrigin.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Sin datos.</p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {summary.byOrigin.map((row) => (
                          <li
                            key={row.proposedBy}
                            className="flex justify-between gap-2 border-b border-border/60 pb-2 last:border-0"
                          >
                            <span className="font-medium">{row.proposedBy}</span>
                            <span className="text-muted-foreground tabular-nums">
                              {row.trials} tri · K:{row.kConsumed}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Por preset</CardTitle>
                </CardHeader>
                <CardContent>
                  {summary.byPreset.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Sin datos.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {summary.byPreset.map((row) => (
                        <button
                          key={row.presetKey}
                          type="button"
                          className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-accent"
                          onClick={() => {
                            patchHistoryFilters({
                              presetKey: row.presetKey === 'unknown' ? '' : row.presetKey,
                            });
                          }}
                        >
                          {row.presetKey} · {row.trials}
                        </button>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {summary.lastTrialAt && (
                <p className="text-xs text-muted-foreground">
                  Último trial: {formatShortDate(summary.lastTrialAt)}
                  {summary.avgProfitFactor != null &&
                    ` · PF medio ${summary.avgProfitFactor.toFixed(2)}`}
                  {summary.avgMaxDD != null && ` · MaxDD medio ${formatPct(summary.avgMaxDD)}`}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="grid gap-4 lg:grid-cols-5">
          <Card className="lg:col-span-3">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Historial de trials</CardTitle>
              <CardDescription>Cada fila es un experimento del ledger K</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <select
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={instrumentId}
                  onChange={(e) => {
                    patchHistoryFilters({ instrumentId: e.target.value });
                  }}
                >
                  <option value="">Todos los instrumentos</option>
                  {(instrumentsQuery.data?.data ?? []).map((inst) => (
                    <option key={inst.id} value={inst.id}>
                      {inst.symbol}
                    </option>
                  ))}
                </select>
                <select
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={proposedBy}
                  onChange={(e) => {
                    patchHistoryFilters({ proposedBy: e.target.value });
                  }}
                >
                  <option value="">Cualquier origen</option>
                  <option value="human">human</option>
                  <option value="grid">grid</option>
                  <option value="optuna">optuna</option>
                  <option value="ai">ai</option>
                  <option value="system">system</option>
                </select>
                <input
                  className="h-9 w-40 rounded-md border border-input bg-background px-2 text-sm"
                  placeholder="preset key"
                  value={presetKey}
                  onChange={(e) => {
                    patchHistoryFilters({ presetKey: e.target.value });
                  }}
                />
                <select
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as ResearchTrialSort)}
                >
                  <option value="created_at">Fecha</option>
                  <option value="sharpe">Sharpe</option>
                  <option value="pnl">PnL</option>
                  <option value="commission">Comisión</option>
                  <option value="k_contribution">K</option>
                </select>
              </div>

              {trialsQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Cargando trials…</p>
              )}
              {trialsQuery.isError && (
                <p className="text-sm text-destructive">
                  No se pudo cargar el historial. Revisa la API e inténtalo de nuevo.
                </p>
              )}

              <div className="max-h-[28rem] overflow-auto rounded-md border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-muted/80 text-muted-foreground">
                    <tr>
                      <th className="px-2 py-2 font-medium">Fecha</th>
                      <th className="px-2 py-2 font-medium">Inst</th>
                      <th className="px-2 py-2 font-medium">Preset</th>
                      <th className="px-2 py-2 font-medium">Origen</th>
                      <th className="px-2 py-2 font-medium">PnL</th>
                      <th className="px-2 py-2 font-medium">Sharpe</th>
                      <th className="px-2 py-2 font-medium">Lab</th>
                      <th className="px-2 py-2 font-medium">K</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trials.map((trial) => {
                      const pnl = metricNum(trial.isMetrics, 'totalReturnPct');
                      const sharpe = metricNum(trial.isMetrics, 'sharpeRatio');
                      const active = trial.id === selectedTrialId;
                      return (
                        <tr
                          key={trial.id}
                          className={cn(
                            'cursor-pointer border-t border-border/60 hover:bg-accent/40',
                            active && 'bg-accent/60',
                          )}
                          onClick={() => selectTrial(trial.id)}
                        >
                          <td className="px-2 py-1.5 whitespace-nowrap">
                            {formatShortDate(trial.createdAt)}
                          </td>
                          <td className="px-2 py-1.5 font-medium">
                            {symbolById.get(trial.instrumentId) ?? trial.instrumentId.slice(0, 6)}
                          </td>
                          <td className="px-2 py-1.5">{trial.presetKey ?? '—'}</td>
                          <td className="px-2 py-1.5">{trial.proposedBy}</td>
                          <td className="px-2 py-1.5 tabular-nums">
                            {pnl == null ? '—' : formatPct(pnl)}
                          </td>
                          <td className="px-2 py-1.5 tabular-nums">
                            {sharpe == null ? '—' : sharpe.toFixed(2)}
                          </td>
                          <td className="max-w-[14rem] truncate px-2 py-1.5">
                            <ResearchLabEvidenceSummary trial={trial} variant="cell" />
                          </td>
                          <td className="px-2 py-1.5 tabular-nums">{trial.kContribution}</td>
                        </tr>
                      );
                    })}
                    {trials.length === 0 && !trialsQuery.isLoading && !trialsQuery.isError && (
                      <tr>
                        <td colSpan={8} className="px-2 py-6 text-center text-muted-foreground">
                          <p>No hay trials con estos filtros.</p>
                          <Link
                            to="/backtests?tab=run"
                            className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
                          >
                            Ir a Probar estrategia
                          </Link>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  {total} trial{total === 1 ? '' : 's'} · página {page + 1}
                </span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Anterior
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={(page + 1) * pageSize >= total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Detalle</CardTitle>
              <CardDescription>Asiento inmutable del ledger</CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedTrialId && (
                <p className="text-sm text-muted-foreground">Selecciona un trial en la tabla.</p>
              )}
              {selectedTrialId && trialDetailQuery.isLoading && (
                <p className="text-sm text-muted-foreground">Cargando…</p>
              )}
              {selected && (
                <div className="space-y-3">
                  <ResearchTrialResultBlock trial={selected} />
                  {selected.backtestRunId && (
                    <Link
                      to={`/backtests?tab=run&runId=${encodeURIComponent(selected.backtestRunId)}`}
                      className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
                    >
                      Abrir backtest (equity / trades / replay)
                    </Link>
                  )}
                  {!selected.backtestRunId && selected.optimizationRunId && (
                    <p className="text-xs text-muted-foreground">
                      Origen grid / optimize — sin backtest_run H0 vinculado (solo asiento ledger).
                    </p>
                  )}
                  <div className="rounded-md border border-border bg-muted/30 p-2">
                    <p className="text-[10px] font-medium uppercase text-muted-foreground">Params</p>
                    <pre className="mt-1 max-h-40 overflow-auto text-[10px] text-muted-foreground">
                      {JSON.stringify(selected.params, null, 2)}
                    </pre>
                  </div>
                  {selected.manifestRef && (
                    <div className="rounded-md border border-border bg-muted/30 p-2">
                      <p className="text-[10px] font-medium uppercase text-muted-foreground">
                        Manifest ref
                      </p>
                      <pre className="mt-1 max-h-32 overflow-auto text-[10px] text-muted-foreground">
                        {JSON.stringify(selected.manifestRef, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function HubTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md px-3 py-1.5 text-sm font-medium',
        active ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-accent/50',
      )}
    >
      {children}
    </button>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}
