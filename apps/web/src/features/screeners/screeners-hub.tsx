import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  CalendarClock,
  Filter,
  LayoutGrid,
  LogOut,
  Radar,
  Route,
  RefreshCw,
  Settings2,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ScanJobDto, ScanRunResultDto } from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { useMediaQuery } from '@/lib/use-media-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ScanRunnerForm,
  canRunScan,
  scanRequestFromConfig,
  type ScanRunnerConfig,
} from '@/features/screeners/scan-runner-form';
import { FundamentalScreenerPanel } from '@/features/screeners/fundamental-screener-panel';
import { FaWeeklyPipelinePanel } from '@/features/screeners/fa-weekly-pipeline-panel';
import { PaperDProposePanel } from '@/features/screeners/paper-d-propose-panel';
import { ScanResultsPanel } from '@/features/screeners/scan-results-panel';
import { TrackersPanel } from '@/features/screeners/trackers-panel';
import { ExecutionPoliciesPanel } from '@/features/screeners/execution-policies-panel';
import { PositionPoliciesPanel } from '@/features/screeners/position-policies-panel';
import { ScanJobsPanel } from '@/features/screeners/scan-jobs-panel';
import { PlatformEventsPanel } from '@/features/screeners/platform-events-panel';
import { ScreenerCollapsibleSection } from '@/features/screeners/screener-collapsible-section';
import { ScreenerMobileViewTabs } from '@/features/screeners/screener-mobile-view-tabs';
import { ScreenerPipelinePanel } from '@/features/screeners/screener-pipeline-panel';
import { SavedStrategiesPanel } from '@/features/screeners/saved-strategies-panel';
import { StrategyPromptAssistantPanel } from '@/features/screeners/strategy-prompt-assistant-panel';
import {
  ScreenerWorkflowSteps,
  resolveWorkflowStep,
} from '@/features/screeners/screener-workflow-steps';
import { ScreenerHubLayout } from '@/features/screeners/screener-hub-layout';
import {
  reconcileScanConfig,
  useScreenerPreferencesStore,
  type ScreenerPanelId,
} from '@/stores/screener-preferences-store';
import { useScreenerActivityStore } from '@/stores/screener-activity-store';

interface ScanHistoryEntry {
  runAt: string;
  config: ScanRunnerConfig;
  result: ScanRunResultDto;
}

function applyScanResult(
  result: ScanRunResultDto,
  config: ScanRunnerConfig,
  setLastResult: (value: ScanRunResultDto) => void,
  setHistory: React.Dispatch<React.SetStateAction<ScanHistoryEntry[]>>,
) {
  setLastResult(result);
  setHistory((current) => [
    { runAt: new Date().toISOString(), config: { ...config }, result },
    ...current.slice(0, 4),
  ]);
}

export function ScreenersHub() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const listIdFromUrl = searchParams.get('listId');
  const trackerIdFromUrl = searchParams.get('trackerId');
  const appliedListIdFromUrlRef = useRef(false);
  const isLargeScreen = useMediaQuery('(min-width: 1024px)');
  const config = useScreenerPreferencesStore((state) => state.scanConfig);
  const patchScanConfig = useScreenerPreferencesStore((state) => state.patchScanConfig);
  const setScanConfig = useScreenerPreferencesStore((state) => state.setScanConfig);
  const runInBackground = useScreenerPreferencesStore((state) => state.runInBackground);
  const setRunInBackground = useScreenerPreferencesStore((state) => state.setRunInBackground);
  const lastExecutionPolicyId = useScreenerPreferencesStore((state) => state.lastExecutionPolicyId);
  const setLastExecutionPolicyId = useScreenerPreferencesStore(
    (state) => state.setLastExecutionPolicyId,
  );
  const mobileView = useScreenerPreferencesStore((state) => state.layout.mobileView);
  const setMobileView = useScreenerPreferencesStore((state) => state.setMobileView);
  const panelOpenState = useScreenerPreferencesStore((state) => state.layout.panels);

  const [lastResult, setLastResult] = useState<ScanRunResultDto | null>(null);
  const [history, setHistory] = useState<ScanHistoryEntry[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [lastCompletedJobId, setLastCompletedJobId] = useState<string | null>(null);
  const [activeDefaultPolicyId, setActiveDefaultPolicyId] = useState<string | null>(null);
  const reconciledRef = useRef(false);
  const [jobMeta, setJobMeta] = useState<Pick<
    ScanJobDto,
    'cacheHits' | 'cacheMisses' | 'status'
  > | null>(null);

  const listsQuery = useQuery({
    queryKey: ['lists'],
    queryFn: api.getLists,
  });

  const strategiesQuery = useQuery({
    queryKey: ['strategies'],
    queryFn: api.getStrategies,
  });

  const executionPoliciesQuery = useQuery({
    queryKey: ['execution-policies'],
    queryFn: () => api.getExecutionPolicies(true),
  });

  const jobsQuery = useQuery({
    queryKey: ['scan-jobs'],
    queryFn: api.getScanJobs,
    refetchInterval: activeJobId ? 2000 : false,
  });

  const activeJobQuery = useQuery({
    queryKey: ['scan-job', activeJobId],
    queryFn: () => api.getScanJob(activeJobId!),
    enabled: Boolean(activeJobId),
    refetchInterval: 2000,
  });

  const lists = useMemo(() => listsQuery.data?.data ?? [], [listsQuery.data?.data]);
  const strategies = useMemo(() => strategiesQuery.data?.data ?? [], [strategiesQuery.data?.data]);
  const executionPolicies = executionPoliciesQuery.data?.data ?? [];
  const recentJobs = jobsQuery.data?.data ?? [];

  useEffect(() => {
    if (!listsQuery.isSuccess || !strategiesQuery.isSuccess || reconciledRef.current) return;
    reconciledRef.current = true;
    const stored = useScreenerPreferencesStore.getState().scanConfig;
    const next = reconcileScanConfig(stored, lists, strategies);
    if (JSON.stringify(next) !== JSON.stringify(stored)) {
      setScanConfig(next);
    }
  }, [listsQuery.isSuccess, strategiesQuery.isSuccess, lists, strategies, setScanConfig]);

  useEffect(() => {
    if (!listIdFromUrl || !listsQuery.isSuccess || appliedListIdFromUrlRef.current) return;
    if (!lists.some((list) => list.id === listIdFromUrl)) return;
    appliedListIdFromUrlRef.current = true;
    patchScanConfig({ listId: listIdFromUrl });
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('listId');
    setSearchParams(nextParams, { replace: true });
    if (!isLargeScreen) setMobileView('workflow');
  }, [
    listIdFromUrl,
    listsQuery.isSuccess,
    lists,
    patchScanConfig,
    searchParams,
    setSearchParams,
    isLargeScreen,
    setMobileView,
  ]);

  const scanMutation = useMutation({
    mutationFn: () => api.runScan(scanRequestFromConfig(config)),
    onSuccess: (response) => {
      applyScanResult(response.data, config, setLastResult, setHistory);
      setJobMeta(null);
      setLastCompletedJobId(null);
      void queryClient.invalidateQueries({ queryKey: ['platform-events'] });
    },
  });

  const enqueueMutation = useMutation({
    mutationFn: () => api.enqueueScanJob(scanRequestFromConfig(config)),
    onSuccess: (response) => {
      setActiveJobId(response.data.id);
      setJobMeta({ status: response.data.status, cacheHits: null, cacheMisses: null });
      void queryClient.invalidateQueries({ queryKey: ['scan-jobs'] });
      void queryClient.invalidateQueries({ queryKey: ['scan-jobs', 'nav-badge'] });
    },
  });

  useEffect(() => {
    const job = activeJobQuery.data?.data;
    if (!job || job.id !== activeJobId) return;

    setJobMeta({
      status: job.status,
      cacheHits: job.cacheHits,
      cacheMisses: job.cacheMisses,
    });

    if (job.status === 'completed' && job.result) {
      applyScanResult(job.result, config, setLastResult, setHistory);
      setLastCompletedJobId(job.id);
      setActiveJobId(null);
      void queryClient.invalidateQueries({ queryKey: ['scan-jobs'] });
      void queryClient.invalidateQueries({ queryKey: ['scan-jobs', 'nav-badge'] });
      void queryClient.invalidateQueries({ queryKey: ['platform-events'] });
    } else if (job.status === 'failed') {
      setActiveJobId(null);
      void queryClient.invalidateQueries({ queryKey: ['scan-jobs', 'nav-badge'] });
    }
  }, [activeJobQuery.data, activeJobId, config, queryClient]);

  const isRunning =
    scanMutation.isPending || enqueueMutation.isPending || activeJobId !== null;

  const setSyncScanActive = useScreenerActivityStore((state) => state.setSyncScanActive);
  useEffect(() => {
    setSyncScanActive(scanMutation.isPending || enqueueMutation.isPending);
  }, [scanMutation.isPending, enqueueMutation.isPending, setSyncScanActive]);

  const errorSource = enqueueMutation.error ?? scanMutation.error;
  const errorMessage =
    errorSource instanceof ApiError
      ? errorSource.message
      : errorSource instanceof Error
        ? errorSource.message
        : activeJobQuery.data?.data.status === 'failed'
          ? activeJobQuery.data.data.error ?? 'El job de rastreo falló'
          : null;

  const workflowStep = resolveWorkflowStep({
    isRunning,
    hasResults: Boolean(lastResult),
  });

  const showWorkflow = isLargeScreen || mobileView === 'workflow';
  const showTools = isLargeScreen || mobileView === 'tools';
  const isSplitViewport = isLargeScreen;

  function patchConfig(patch: Partial<ScanRunnerConfig>) {
    patchScanConfig(patch);
  }

  function restoreHistory(entry: ScanHistoryEntry) {
    setScanConfig(entry.config);
    setLastResult(entry.result);
  }

  function handleRunScan() {
    if (runInBackground) {
      enqueueMutation.mutate();
    } else {
      scanMutation.mutate();
    }
  }

  function handleTrackerScanResult(result: ScanRunResultDto) {
    applyScanResult(result, config, setLastResult, setHistory);
    setJobMeta(null);
    setActiveJobId(null);
    setLastCompletedJobId(null);
    void queryClient.invalidateQueries({ queryKey: ['platform-events'] });
  }

  function handleLoadJobResult(job: ScanJobDto) {
    if (!job.result) return;
    applyScanResult(job.result, config, setLastResult, setHistory);
    setLastCompletedJobId(job.id);
    setJobMeta({
      status: job.status,
      cacheHits: job.cacheHits,
      cacheMisses: job.cacheMisses,
    });
    if (!isLargeScreen) setMobileView('workflow');
  }

  function isPanelOpen(panelId: ScreenerPanelId, defaultOpen = true) {
    return panelOpenState[panelId] ?? defaultOpen;
  }

  function sidebarSection(
    panelId: ScreenerPanelId,
    title: string,
    icon: typeof Radar,
    content: React.ReactNode,
    options?: { defaultOpen?: boolean; badge?: React.ReactNode },
  ) {
    return {
      id: panelId,
      open: isPanelOpen(panelId, options?.defaultOpen ?? true),
      node: (
        <ScreenerCollapsibleSection
          panelId={panelId}
          title={title}
          icon={icon}
          badge={options?.badge}
          defaultOpen={options?.defaultOpen}
          splitMode={isSplitViewport}
        >
          {content}
        </ScreenerCollapsibleSection>
      ),
    };
  }

  const sidebarPanels = [
    sidebarSection('trackers', 'Rastreadores', Radar, (
      <TrackersPanel
        embedded
        config={config}
        initialTrackerId={trackerIdFromUrl}
        onLoadConfig={(loaded, meta) => {
          setScanConfig(loaded);
          const policyId = meta?.defaultPolicyId ?? null;
          setActiveDefaultPolicyId(policyId);
          if (policyId) setLastExecutionPolicyId(policyId);
          if (!isLargeScreen) setMobileView('workflow');
        }}
        onScanResult={(result) => {
          handleTrackerScanResult(result);
          if (!isLargeScreen) setMobileView('workflow');
        }}
        executionPolicies={executionPolicies}
      />
    ), { defaultOpen: true }),
    sidebarSection('fa-screener', 'Screener FA (F4)', Filter, (
      <FundamentalScreenerPanel
        listId={config.listId}
        lists={lists}
        onListIdChange={(id) => patchConfig({ listId: id })}
      />
    ), { defaultOpen: true }),
    sidebarSection('paper-d', 'Paper D (propose)', Route, (
      <PaperDProposePanel
        listId={config.listId}
        lists={lists}
        onListIdChange={(id) => patchConfig({ listId: id })}
      />
    ), { defaultOpen: false }),
    sidebarSection('fa-weekly', 'FA→D semanal', CalendarClock, (
      <FaWeeklyPipelinePanel
        listId={config.listId}
        lists={lists}
        onListIdChange={(id) => patchConfig({ listId: id })}
      />
    ), { defaultOpen: false }),
    sidebarSection('saved-strategies', 'Estrategias guardadas', Target, (
      <SavedStrategiesPanel
        embedded
        onLoadConfig={(loaded) => {
          setScanConfig(loaded);
          if (!isLargeScreen) setMobileView('workflow');
        }}
      />
    ), { defaultOpen: false }),
    sidebarSection('ai-assistant', 'Asistente IA', Sparkles, (
      <StrategyPromptAssistantPanel
        compact
        onApplyToScan={(loaded) => {
          setScanConfig(loaded);
          if (!isLargeScreen) setMobileView('workflow');
        }}
      />
    ), { defaultOpen: false }),
    sidebarSection('execution', 'Políticas de ejecución', Zap, (
      <ExecutionPoliciesPanel embedded />
    ), { defaultOpen: false }),
    sidebarSection('position', 'Políticas de posición', LogOut, (
      <PositionPoliciesPanel embedded />
    ), { defaultOpen: false }),
    sidebarSection('events', 'Bus de eventos', Activity, (
      <PlatformEventsPanel embedded />
    ), { defaultOpen: false }),
    sidebarSection('pipeline', 'Canal interno', Settings2, (
      <ScreenerPipelinePanel
        embedded
        executionPolicyCount={executionPolicies.length}
        jobMeta={jobMeta}
      />
    ), { defaultOpen: false }),
  ];

  const runnerPanel = (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader className="space-y-3 border-b border-border/60 bg-muted/20 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Radar className="h-5 w-5 shrink-0 text-primary" />
              Ejecutar rastreador
            </CardTitle>
            <CardDescription className="max-w-2xl">
              Escanea una lista en la última barra. Sync inmediato o cola async con cache de
              features.
            </CardDescription>
          </div>
          <ScreenerWorkflowSteps
            activeStep={workflowStep}
            hitCount={lastResult?.hitCount}
            isRunning={isRunning}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <ScanRunnerForm
          config={config}
          onChange={patchConfig}
          lists={lists}
          strategies={strategies}
          compact={!isLargeScreen}
        />
        <div className="flex flex-col gap-3 border-t border-border/60 pt-4 sm:flex-row sm:flex-wrap sm:items-center">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={runInBackground}
              onChange={(e) => setRunInBackground(e.target.checked)}
            />
            Ejecutar en segundo plano
          </label>
          <Button
            type="button"
            className="w-full sm:w-auto"
            disabled={!canRunScan(config) || isRunning}
            onClick={handleRunScan}
          >
            {isRunning ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                {activeJobId ? 'Procesando tarea…' : 'Escaneando…'}
              </>
            ) : runInBackground ? (
              'Encolar rastreo'
            ) : (
              'Ejecutar rastreo'
            )}
          </Button>
          {jobMeta && activeJobId && (
            <span className="text-xs text-muted-foreground">
              Tarea {activeJobId.slice(0, 8)}… · {jobMeta.status}
            </span>
          )}
        </div>
        {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
      </CardContent>
    </Card>
  );

  const resultsPanel = lastResult ? (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Resultados</CardTitle>
        <CardDescription>
          Señales en cierre de barra · TF {lastResult.timeframe} · {lastResult.hitCount}{' '}
          coincidencias
        </CardDescription>
      </CardHeader>
      <CardContent className="min-w-0">
        <ScanResultsPanel
          result={lastResult}
          scanConfig={config}
          full
          executionPolicies={executionPolicies}
          scanJobId={lastCompletedJobId}
          defaultPolicyId={activeDefaultPolicyId ?? lastExecutionPolicyId}
        />
      </CardContent>
    </Card>
  ) : (
    <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
      Ejecuta un rastreo para ver coincidencias. Clic en símbolo o «Gráfico» abre Trading con
      contexto de lista.
    </div>
  );

  const workflowFooter = (
    <>
      {recentJobs.length > 0 && (
        <ScreenerCollapsibleSection
          panelId="jobs"
          title="Tareas recientes"
          icon={LayoutGrid}
          badge={
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {recentJobs.length}
            </span>
          }
        >
          <ScanJobsPanel embedded jobs={recentJobs} onLoadResult={handleLoadJobResult} />
        </ScreenerCollapsibleSection>
      )}

      {history.length > 1 && (
        <ScreenerCollapsibleSection panelId="history" title="Sesión" defaultOpen={false}>
          <ul className="space-y-2 text-sm">
            {history.map((entry) => (
              <li
                key={`${entry.result.scanId}-${entry.runAt}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-border px-3 py-2"
              >
                <span className="text-muted-foreground">
                  {new Date(entry.runAt).toLocaleTimeString('es-ES')} · {entry.result.hitCount}{' '}
                  coincidencias
                </span>
                <Button type="button" size="sm" variant="ghost" onClick={() => restoreHistory(entry)}>
                  Restaurar
                </Button>
              </li>
            ))}
          </ul>
        </ScreenerCollapsibleSection>
      )}
    </>
  );

  const hasWorkflowFooter = recentJobs.length > 0 || history.length > 1;

  return (
    <div className="screener-hub-shell mx-auto flex h-full min-h-0 w-full max-w-[1600px] flex-col gap-3">
      <ScreenerMobileViewTabs view={mobileView} onChange={setMobileView} />
      {isSplitViewport && (
        <p className="hidden shrink-0 text-[10px] text-muted-foreground lg:block">
          Arrastra los separadores entre paneles para ajustar el layout. Se guarda automáticamente.
        </p>
      )}

      <ScreenerHubLayout
        className="min-h-0 flex-1"
        isSplitViewport={isSplitViewport}
        showWorkflow={showWorkflow}
        showTools={showTools}
        hasResults={Boolean(lastResult)}
        hasWorkflowFooter={hasWorkflowFooter}
        runner={runnerPanel}
        results={resultsPanel}
        workflowFooter={workflowFooter}
        sidebarPanels={sidebarPanels}
      />
    </div>
  );
}
