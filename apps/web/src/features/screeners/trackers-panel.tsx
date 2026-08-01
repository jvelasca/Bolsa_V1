import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Pause, Pencil, Play, Plus, Radar, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type {
  ExecutionPolicySummaryDto,
  TrackerScheduleKind,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';
import {
  buildCreateTrackerDto,
  buildUpdateTrackerDto,
  scanConfigFromTracker,
  trackerScheduleKindFromTracker,
  trackerScheduleLabel,
} from '@/features/screeners/tracker-helpers';
import {
  canRunScan,
  scanConfigFromStrategyDefinition,
  strategyUpsertFromScanConfig,
  type ScanRunnerConfig,
} from '@/features/screeners/scan-runner-form';
import { useScreenerPreferencesStore } from '@/stores/screener-preferences-store';

interface TrackersPanelProps {
  embedded?: boolean;
  config: ScanRunnerConfig;
  onLoadConfig: (
    config: ScanRunnerConfig,
    meta?: { defaultPolicyId?: string | null },
  ) => void;
  onScanResult: (result: import('@bolsa/shared').ScanRunResultDto) => void;
  executionPolicies: ExecutionPolicySummaryDto[];
  /** Deep-link desde Finalistas (`?trackerId=`). */
  initialTrackerId?: string | null;
}

export function TrackersPanel({
  embedded,
  config,
  onLoadConfig,
  onScanResult,
  executionPolicies,
  initialTrackerId = null,
}: TrackersPanelProps) {
  const queryClient = useQueryClient();
  const trackerSave = useScreenerPreferencesStore((state) => state.trackerSave);
  const patchTrackerSave = useScreenerPreferencesStore((state) => state.patchTrackerSave);
  const [showSave, setShowSave] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [activeTrackerId, setActiveTrackerId] = useState<string | null>(null);
  const [editingTrackerId, setEditingTrackerId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editScheduleKind, setEditScheduleKind] = useState<TrackerScheduleKind>('manual');
  const [editPolicyId, setEditPolicyId] = useState('');
  const [scheduleLabels, setScheduleLabels] = useState<Record<string, string>>({});
  const { scheduleKind, defaultPolicyId } = trackerSave;
  const fetchedLabelsRef = useRef(new Set<string>());
  const appliedInitialTrackerRef = useRef<string | null>(null);

  const trackersQuery = useQuery({
    queryKey: ['trackers'],
    queryFn: () => api.getTrackers(),
  });

  const trackers = trackersQuery.data?.data ?? [];

  useEffect(() => {
    if (!initialTrackerId) return;
    if (appliedInitialTrackerRef.current === initialTrackerId) return;
    if (!trackersQuery.isSuccess) return;
    const exists = trackers.some((t) => t.id === initialTrackerId);
    if (!exists) return;
    appliedInitialTrackerRef.current = initialTrackerId;
    setActiveTrackerId(initialTrackerId);
    void api.getTracker(initialTrackerId).then((response) => {
      const loaded = scanConfigFromTracker(response.data);
      onLoadConfig(loaded, {
        defaultPolicyId: response.data.definition.defaultExecutionPolicyId ?? null,
      });
      const label = trackerScheduleLabel(response.data);
      if (label) {
        setScheduleLabels((current) => ({ ...current, [initialTrackerId]: label }));
      }
    });
  }, [initialTrackerId, trackersQuery.isSuccess, trackers, onLoadConfig]);
  useEffect(() => {
    if (!trackersQuery.isSuccess || trackers.length === 0) return;
    for (const tracker of trackers) {
      if (fetchedLabelsRef.current.has(tracker.id)) continue;
      fetchedLabelsRef.current.add(tracker.id);
      void api.getTracker(tracker.id).then((response) => {
        const label = trackerScheduleLabel(response.data);
        if (label) {
          setScheduleLabels((current) => ({ ...current, [tracker.id]: label }));
        }
      });
    }
  }, [trackersQuery.isSuccess, trackers]);

  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.updateTracker(id, { enabled }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['trackers'] }),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      let strategyId = config.scanSource === 'saved' ? config.savedStrategyId : '';
      const hybridPayload = strategyUpsertFromScanConfig(config, saveName);
      if (hybridPayload) {
        const created = await api.createStrategy(hybridPayload);
        strategyId = created.data.id;
      } else if (config.scanSource === 'preset') {
        const created = await api.createStrategyFromPreset({
          name: `${saveName.trim()} · preset`,
          presetKey: config.presetKey,
          timeframe: config.timeframe,
        });
        strategyId = created.data.id;
      }
      if (!strategyId) throw new Error('Selecciona una estrategia guardada');
      return api.createTracker(
        buildCreateTrackerDto(config, {
          name: saveName.trim(),
          strategyDefinitionId: strategyId,
          scheduleKind,
          defaultExecutionPolicyId: defaultPolicyId || null,
        }),
      );
    },
    onSuccess: (response) => {
      setShowSave(false);
      setSaveName('');
      const label = trackerScheduleLabel(response.data);
      if (label) {
        setScheduleLabels((current) => ({ ...current, [response.data.id]: label }));
      }
      void queryClient.invalidateQueries({ queryKey: ['trackers'] });
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteTracker(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['trackers'] }),
  });

  const runMutation = useMutation({
    mutationFn: (trackerId: string) => api.runTrackerScan(trackerId),
    onSuccess: (response) => onScanResult(response.data),
  });

  const enqueueMutation = useMutation({
    mutationFn: (trackerId: string) => api.enqueueTrackerScanJob(trackerId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['scan-jobs'] }),
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      trackerId,
      useScanConfig,
    }: {
      trackerId: string;
      useScanConfig?: boolean;
    }) => {
      const detail = await api.getTracker(trackerId);
      const baseConfig =
        useScanConfig && activeTrackerId === trackerId && canRunScan(config)
          ? config
          : scanConfigFromTracker(detail.data);

      const name =
        editingTrackerId === trackerId && editName.trim()
          ? editName.trim()
          : detail.data.name;

      const schedule =
        editingTrackerId === trackerId
          ? editScheduleKind
          : trackerScheduleKindFromTracker(detail.data);

      const policyId =
        editingTrackerId === trackerId
          ? editPolicyId || null
          : detail.data.definition.defaultExecutionPolicyId ?? null;

      return api.updateTracker(
        trackerId,
        buildUpdateTrackerDto(baseConfig, {
          name,
          scheduleKind: schedule,
          defaultExecutionPolicyId: policyId,
        }),
      );
    },
    onSuccess: (response) => {
      setEditingTrackerId(null);
      const label = trackerScheduleLabel(response.data);
      if (label) {
        setScheduleLabels((current) => ({ ...current, [response.data.id]: label }));
      } else {
        setScheduleLabels((current) => {
          const next = { ...current };
          delete next[response.data.id];
          return next;
        });
      }
      void queryClient.invalidateQueries({ queryKey: ['trackers'] });
    },
  });

  const saveError =
    saveMutation.error instanceof ApiError
      ? saveMutation.error.message
      : saveMutation.error instanceof Error
        ? saveMutation.error.message
        : null;

  const updateError =
    updateMutation.error instanceof ApiError
      ? updateMutation.error.message
      : updateMutation.error instanceof Error
        ? updateMutation.error.message
        : null;

  function handleStartEdit(trackerId: string) {
    void api.getTracker(trackerId).then((response) => {
      const tracker = response.data;
      setEditingTrackerId(trackerId);
      setEditName(tracker.name);
      setEditScheduleKind(trackerScheduleKindFromTracker(tracker));
      setEditPolicyId(tracker.definition.defaultExecutionPolicyId ?? '');
      setActiveTrackerId(trackerId);
    });
  }

  function handleLoad(trackerId: string) {
    void api.getTracker(trackerId).then(async (response) => {
      const tracker = response.data;
      const strategyResponse = await api.getStrategy(tracker.strategyDefinitionId);
      onLoadConfig(
        scanConfigFromStrategyDefinition(strategyResponse.data, scanConfigFromTracker(tracker)),
        {
          defaultPolicyId: tracker.definition.defaultExecutionPolicyId ?? null,
        },
      );
      const label = trackerScheduleLabel(tracker);
      if (label) {
        setScheduleLabels((current) => ({ ...current, [trackerId]: label }));
      }
      setActiveTrackerId(trackerId);
    });
  }

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Rastreadores guardados"
      description={
        embedded ? undefined : 'Persistidos en BD — schedule automático vía worker P9 (API en marcha).'
      }
      icon={Radar}
    >
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canRunScan(config)}
            onClick={() => setShowSave((v) => !v)}
          >
            <Plus className="mr-1 h-3.5 w-3.5" />
            Guardar config actual
          </Button>
          {activeTrackerId && canRunScan(config) && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate({ trackerId: activeTrackerId, useScanConfig: true })}
            >
              {updateMutation.isPending ? 'Guardando…' : 'Sincronizar rastreo → rastreador'}
            </Button>
          )}
        </div>

        {showSave && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
            <label className="block text-sm">
              Nombre
              <input
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="IBEX SMA daily"
              />
            </label>
            <label className="block text-sm">
              Schedule
              <select
                value={scheduleKind}
                onChange={(e) =>
                  patchTrackerSave({ scheduleKind: e.target.value as TrackerScheduleKind })
                }
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="manual">Manual</option>
                <option value="on_bar_close">Automático · cierre de barra</option>
              </select>
            </label>
            {executionPolicies.length > 0 && (
              <label className="block text-sm">
                Política de ejecución (opcional)
                <span className="mt-0.5 block text-[11px] text-muted-foreground">
                  B1: modos «Solo informar» / «Alerta» se aplican solos tras cada scan. Paper auto no.
                </span>
                <select
                  value={defaultPolicyId}
                  onChange={(e) => patchTrackerSave({ defaultPolicyId: e.target.value })}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="">Ninguna</option>
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
                disabled={!saveName.trim() || saveMutation.isPending}
                onClick={() => saveMutation.mutate()}
              >
                {saveMutation.isPending ? 'Guardando…' : 'Crear rastreador'}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setShowSave(false)}>
                Cancelar
              </Button>
            </div>
            {saveError && <p className="text-xs text-destructive">{saveError}</p>}
          </div>
        )}

        {trackersQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Cargando rastreadores…</p>
        ) : trackers.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sin rastreadores. Configura un rastreo y guárdalo aquí.
          </p>
        ) : (
          <ul className="space-y-2">
            {trackers.map((tracker) => {
              const isActive = activeTrackerId === tracker.id;
              const isRunning =
                (runMutation.isPending && runMutation.variables === tracker.id) ||
                (enqueueMutation.isPending && enqueueMutation.variables === tracker.id);

              return (
                <li
                  key={tracker.id}
                  className={`rounded-lg border px-3 py-2 ${isActive ? 'border-primary/50 bg-primary/5' : 'border-border'}`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-sm">{tracker.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {tracker.timeframe} ·{' '}
                        <span className={tracker.enabled ? 'text-foreground' : 'text-amber-600'}>
                          {tracker.enabled ? 'activo' : 'pausado'}
                        </span>
                        {scheduleLabels[tracker.id] && <> · {scheduleLabels[tracker.id]}</>}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        title={tracker.enabled ? 'Pausar rastreador' : 'Activar rastreador'}
                        disabled={toggleEnabledMutation.isPending}
                        onClick={() =>
                          toggleEnabledMutation.mutate({
                            id: tracker.id,
                            enabled: !tracker.enabled,
                          })
                        }
                      >
                        {tracker.enabled ? (
                          <Pause className="h-3.5 w-3.5" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        title="Editar nombre, programación y política"
                        onClick={() => handleStartEdit(tracker.id)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => handleLoad(tracker.id)}
                      >
                        Cargar
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isRunning}
                        onClick={() => runMutation.mutate(tracker.id)}
                      >
                        {runMutation.isPending && runMutation.variables === tracker.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isRunning}
                        title="Encolar async"
                        onClick={() => enqueueMutation.mutate(tracker.id)}
                      >
                        Cola
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        disabled={deleteMutation.isPending}
                        onClick={() => deleteMutation.mutate(tracker.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>

                  {editingTrackerId === tracker.id && (
                    <div className="mt-3 space-y-3 border-t border-border pt-3">
                      <label className="block text-sm">
                        Nombre
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="block text-sm">
                        Schedule
                        <select
                          value={editScheduleKind}
                          onChange={(e) =>
                            setEditScheduleKind(e.target.value as TrackerScheduleKind)
                          }
                          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        >
                          <option value="manual">Manual</option>
                          <option value="on_bar_close">Automático · cierre de barra</option>
                        </select>
                      </label>
                      {executionPolicies.length > 0 && (
                        <label className="block text-sm">
                          Política de ejecución
                          <select
                            value={editPolicyId}
                            onChange={(e) => setEditPolicyId(e.target.value)}
                            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          >
                            <option value="">Ninguna</option>
                            {executionPolicies.map((policy) => (
                              <option key={policy.id} value={policy.id}>
                                {policy.name} ({policy.mode})
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          disabled={!editName.trim() || updateMutation.isPending}
                          onClick={() => updateMutation.mutate({ trackerId: tracker.id })}
                        >
                          {updateMutation.isPending ? 'Guardando…' : 'Guardar cambios'}
                        </Button>
                        {canRunScan(config) && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={updateMutation.isPending}
                            onClick={() =>
                              updateMutation.mutate({
                                trackerId: tracker.id,
                                useScanConfig: true,
                              })
                            }
                          >
                            + config rastreo actual
                          </Button>
                        )}
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditingTrackerId(null)}
                        >
                          Cancelar
                        </Button>
                      </div>
                      {updateError && editingTrackerId === tracker.id && (
                        <p className="text-xs text-destructive">{updateError}</p>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
    </ScreenerPanelShell>
  );
}
