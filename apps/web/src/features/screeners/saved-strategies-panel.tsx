import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Copy,
  LineChart,
  Loader2,
  MoreHorizontal,
  Pencil,
  Play,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  BACKTEST_STRATEGIES,
  DEFAULT_HYBRID_MIN_SCORE,
  DEFAULT_HYBRID_MIN_DATA_QUALITY,
  HYBRID_GATE_PRESET_KEYS,
  canPublishStrategyScoreAsIndicator,
  presetFromStrategyScore,
  type BacktestStrategyType,
  type StrategyDefinitionSummaryDto,
  type StrategyDefinitionV1,
  type StrategyOrigin,
} from '@bolsa/shared';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { inputClassName } from '@/components/ui/dialog';
import {
  OpaqueMenuItem,
  OpaqueMenuLabel,
  OpaqueMenuPanel,
} from '@/components/ui/opaque-menu-panel';
import { ScreenerPanelShell } from '@/features/screeners/screener-panel-shell';
import {
  scanConfigFromStrategyDefinition,
  strategyUpsertFromScanConfig,
  type ScanRunnerConfig,
} from '@/features/screeners/scan-runner-form';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/ui-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

interface SavedStrategiesPanelProps {
  embedded?: boolean;
  onLoadConfig: (config: ScanRunnerConfig) => void;
}

type SortColumn = 'name' | 'kind' | 'timeframe' | 'origin' | 'updatedAt';
type SortDirection = 'asc' | 'desc';

const KIND_LABELS: Record<StrategyDefinitionV1['kind'], string> = {
  rule_based: 'Reglas',
  indicator_signals: 'Indicadores',
  ml_model: 'ML',
  hybrid: 'Híbrido',
};

const ORIGIN_LABELS: Record<StrategyOrigin, string> = {
  manual: 'Manual',
  assisted: 'Asistida',
  ai_generated: 'IA',
  imported: 'Importada',
  preset: 'Preset',
};

function formatUpdatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function duplicateName(base: string, existing: Set<string>): string {
  const trimmed = base.trim();
  let candidate = `${trimmed} (copia)`;
  let index = 2;
  while (existing.has(candidate.toLowerCase())) {
    candidate = `${trimmed} (copia ${index})`;
    index += 1;
  }
  return candidate;
}

function SortHeader({
  label,
  column,
  sortColumn,
  sortDirection,
  onSort,
}: {
  label: string;
  column: SortColumn;
  sortColumn: SortColumn;
  sortDirection: SortDirection;
  onSort: (column: SortColumn) => void;
}) {
  const active = sortColumn === column;
  return (
    <button
      type="button"
      className="flex items-center gap-0.5 hover:text-foreground"
      onClick={() => onSort(column)}
    >
      <span>{label}</span>
      {!active && <ArrowUpDown className="h-3 w-3 opacity-30" />}
      {active && sortDirection === 'asc' && <ArrowUp className="h-3 w-3 text-primary" />}
      {active && sortDirection === 'desc' && <ArrowDown className="h-3 w-3 text-primary" />}
    </button>
  );
}

function StrategyRowMenu({
  strategy,
  onLoad,
  onRename,
  onEdit,
  onDuplicate,
  onDelete,
  onPublishScore,
  busy,
}: {
  strategy: StrategyDefinitionSummaryDto;
  onLoad: () => void;
  onRename: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onPublishScore?: () => void;
  busy?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number } | null>(null);
  const buttonRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !buttonRef.current) return;

    function updatePosition() {
      const button = buttonRef.current;
      if (!button) return;
      const rect = button.getBoundingClientRect();
      const menuWidth = 220;
      const menuHeight = menuRef.current?.offsetHeight ?? 240;
      const margin = 8;

      let left = rect.right - menuWidth;
      left = Math.max(margin, Math.min(left, window.innerWidth - menuWidth - margin));

      let top = rect.bottom + 4;
      if (top + menuHeight > window.innerHeight - margin) {
        top = Math.max(margin, rect.top - menuHeight - 4);
      }

      setMenuStyle({ top, left });
    }

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        menuRef.current?.contains(target) ||
        buttonRef.current?.contains(target)
      ) {
        return;
      }
      setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  return (
    <>
      <div ref={buttonRef}>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 w-7 px-0"
          disabled={busy}
          onClick={() => setOpen((value) => !value)}
          title="Acciones"
          aria-expanded={open}
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </div>
      {open &&
        menuStyle &&
        createPortal(
          <OpaqueMenuPanel
            ref={menuRef}
            className="min-w-[220px]"
            style={{ position: 'fixed', top: menuStyle.top, left: menuStyle.left, zIndex: 200 }}
          >
            <OpaqueMenuLabel>{strategy.name}</OpaqueMenuLabel>
            <OpaqueMenuItem
              onClick={() => {
                setOpen(false);
                onLoad();
              }}
            >
              <Play className="h-3.5 w-3.5" />
              Cargar en laboratorio
            </OpaqueMenuItem>
            <OpaqueMenuItem
              onClick={() => {
                setOpen(false);
                onRename();
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
              Renombrar
            </OpaqueMenuItem>
            <OpaqueMenuItem
              onClick={() => {
                setOpen(false);
                onEdit();
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
              Editar parámetros
            </OpaqueMenuItem>
            {onPublishScore && (
              <OpaqueMenuItem
                onClick={() => {
                  setOpen(false);
                  onPublishScore();
                }}
              >
                <LineChart className="h-3.5 w-3.5" />
                Publicar score en gráfico
              </OpaqueMenuItem>
            )}
            <OpaqueMenuItem
              onClick={() => {
                setOpen(false);
                onDuplicate();
              }}
            >
              <Copy className="h-3.5 w-3.5" />
              Duplicar
            </OpaqueMenuItem>
            <OpaqueMenuItem
              destructive
              onClick={() => {
                setOpen(false);
                onDelete();
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              Eliminar
            </OpaqueMenuItem>
          </OpaqueMenuPanel>,
          document.body,
        )}
    </>
  );
}

function canShowPublishScoreAction(strategy: StrategyDefinitionSummaryDto): boolean {
  if (strategy.kind === 'hybrid') return true;
  if (strategy.kind === 'indicator_signals' && strategy.presetKey) return true;
  if (strategy.kind === 'rule_based') return true;
  return false;
}

export function SavedStrategiesPanel({ embedded, onLoadConfig }: SavedStrategiesPanelProps) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [sortColumn, setSortColumn] = useState<SortColumn>('updatedAt');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [editGatePreset, setEditGatePreset] = useState<BacktestStrategyType>('price_above_sma200');
  const [editMinScore, setEditMinScore] = useState(DEFAULT_HYBRID_MIN_SCORE);
  const [editMinDataQuality, setEditMinDataQuality] = useState(DEFAULT_HYBRID_MIN_DATA_QUALITY);
  const [editMaxPe, setEditMaxPe] = useState('');
  const [editMinCap, setEditMinCap] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const addIndicatorPresetFromDraft = useWorkspaceStore((state) => state.addIndicatorPresetFromDraft);
  const saveWorkspace = useWorkspaceStore((state) => state.save);
  const openIndicatorsCatalog = useUiStore((state) => state.openIndicatorsCatalog);

  const strategiesQuery = useQuery({
    queryKey: ['strategies'],
    queryFn: api.getStrategies,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      name,
      config,
    }: {
      id: string;
      name: string;
      config?: ScanRunnerConfig;
    }) => {
      if (config) {
        const hybridPayload = strategyUpsertFromScanConfig(config, name);
        if (hybridPayload) return api.updateStrategy(id, hybridPayload);
      }
      return api.updateStrategy(id, { name });
    },
    onSuccess: () => {
      setEditingId(null);
      setRenamingId(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : 'No se pudo guardar');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteStrategy(id),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
      void queryClient.invalidateQueries({ queryKey: ['trackers'] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : 'No se pudo eliminar');
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: async (strategyId: string) => {
      const response = await api.getStrategy(strategyId);
      const detail = response.data;
      const existingNames = new Set(
        (strategiesQuery.data?.data ?? []).map((item) => item.name.trim().toLowerCase()),
      );
      const name = duplicateName(detail.name, existingNames);
      return api.createStrategy({ name, definition: detail.definition });
    },
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : 'No se pudo duplicar');
    },
  });

  const strategies = strategiesQuery.data?.data ?? [];
  const fieldClass =
    'mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm';
  const busy =
    updateMutation.isPending || deleteMutation.isPending || duplicateMutation.isPending;

  const filteredStrategies = useMemo(() => {
    const query = search.trim().toLowerCase();
    const rows = query
      ? strategies.filter((strategy) => {
          const haystack = [
            strategy.name,
            strategy.timeframe,
            KIND_LABELS[strategy.kind],
            ORIGIN_LABELS[strategy.origin],
          ]
            .join(' ')
            .toLowerCase();
          return haystack.includes(query);
        })
      : strategies;

    return [...rows].sort((left, right) => {
      let cmp = 0;
      switch (sortColumn) {
        case 'name':
          cmp = left.name.localeCompare(right.name, 'es');
          break;
        case 'kind':
          cmp = KIND_LABELS[left.kind].localeCompare(KIND_LABELS[right.kind], 'es');
          break;
        case 'timeframe':
          cmp = left.timeframe.localeCompare(right.timeframe, 'es');
          break;
        case 'origin':
          cmp = ORIGIN_LABELS[left.origin].localeCompare(ORIGIN_LABELS[right.origin], 'es');
          break;
        case 'updatedAt':
          cmp = left.updatedAt.localeCompare(right.updatedAt);
          break;
      }
      return sortDirection === 'asc' ? cmp : -cmp;
    });
  }, [search, sortColumn, sortDirection, strategies]);

  function handleSort(column: SortColumn) {
    if (sortColumn === column) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === 'name' ? 'asc' : 'desc');
  }

  async function handleStartEdit(strategyId: string) {
    const response = await api.getStrategy(strategyId);
    const strategy = response.data;
    const config = scanConfigFromStrategyDefinition(strategy);
    setEditingId(strategyId);
    setRenamingId(null);
    setEditName(strategy.name);
    if (strategy.kind === 'hybrid') {
      setEditGatePreset(config.hybridGatePresetKey);
      setEditMinScore(config.hybridMinScore);
      setEditMinDataQuality(config.hybridMinDataQuality);
      setEditMaxPe(
        config.hybridMaxTrailingPe != null ? String(config.hybridMaxTrailingPe) : '',
      );
      setEditMinCap(
        config.hybridMinMarketCapMillions != null
          ? String(config.hybridMinMarketCapMillions)
          : '',
      );
    }
  }

  function handleStartRename(strategy: StrategyDefinitionSummaryDto) {
    setRenamingId(strategy.id);
    setEditingId(null);
    setRenameValue(strategy.name);
  }

  function buildEditConfig(base: ScanRunnerConfig): ScanRunnerConfig {
    if (base.scanMode !== 'hybrid') return base;
    return {
      ...base,
      hybridGatePresetKey: editGatePreset,
      hybridMinScore: editMinScore,
      hybridMinDataQuality: editMinDataQuality,
      hybridMaxTrailingPe: editMaxPe ? Number(editMaxPe) : null,
      hybridMinMarketCapMillions: editMinCap ? Number(editMinCap) : null,
    };
  }

  async function handleLoad(strategyId: string) {
    const response = await api.getStrategy(strategyId);
    onLoadConfig(scanConfigFromStrategyDefinition(response.data));
  }

  async function handlePublishScoreToChart(strategyId: string) {
    setActionError(null);
    try {
      const response = await api.getStrategy(strategyId);
      if (!canPublishStrategyScoreAsIndicator(response.data)) {
        setActionError('Solo estrategias con rating técnico o preset ejecutable admiten score en gráfico.');
        return;
      }
      const preset = presetFromStrategyScore(response.data);
      if (!preset) {
        setActionError('No se pudo crear el preset de score.');
        return;
      }
      const presetId = addIndicatorPresetFromDraft(preset);
      if (!presetId) {
        setActionError('No se pudo guardar el preset en el workspace.');
        return;
      }
      saveWorkspace();
      openIndicatorsCatalog();
      setActionError(
        `Indicador «${preset.name}» guardado en catálogo IA. En Trading → Indicadores → IA, añádelo con ★.`,
      );
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : 'Error al publicar score');
    }
  }

  function handleDelete(strategy: StrategyDefinitionSummaryDto) {
    if (!window.confirm(`¿Eliminar la estrategia «${strategy.name}»? Esta acción no se puede deshacer.`)) {
      return;
    }
    deleteMutation.mutate(strategy.id);
  }

  function handleSaveRename(strategyId: string) {
    const name = renameValue.trim();
    if (!name) return;
    updateMutation.mutate({ id: strategyId, name });
  }

  return (
    <ScreenerPanelShell
      embedded={embedded}
      title="Estrategias guardadas"
      description={embedded ? undefined : 'Gestión estándar: renombrar, editar, duplicar y eliminar'}
    >
      {strategiesQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando estrategias…</p>
      ) : strategies.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin estrategias guardadas.</p>
      ) : (
        <div className="space-y-2">
          <input
            type="search"
            className={inputClassName}
            placeholder="Buscar por nombre, tipo, timeframe…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-card text-left text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">
                    <SortHeader
                      label="Nombre"
                      column="name"
                      sortColumn={sortColumn}
                      sortDirection={sortDirection}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-3 py-2">
                    <SortHeader
                      label="Tipo"
                      column="kind"
                      sortColumn={sortColumn}
                      sortDirection={sortDirection}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-3 py-2">
                    <SortHeader
                      label="Timeframe"
                      column="timeframe"
                      sortColumn={sortColumn}
                      sortDirection={sortDirection}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-3 py-2">
                    <SortHeader
                      label="Origen"
                      column="origin"
                      sortColumn={sortColumn}
                      sortDirection={sortDirection}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-3 py-2">
                    <SortHeader
                      label="Actualizada"
                      column="updatedAt"
                      sortColumn={sortColumn}
                      sortDirection={sortDirection}
                      onSort={handleSort}
                    />
                  </th>
                  <th className="px-3 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredStrategies.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-4 text-sm text-muted-foreground">
                      Ninguna estrategia coincide con la búsqueda.
                    </td>
                  </tr>
                )}
                {filteredStrategies.map((strategy) => {
                  const isRenaming = renamingId === strategy.id;
                  const isHybrid = strategy.kind === 'hybrid';

                  return (
                    <tr key={strategy.id} className="hover:bg-muted/20">
                      <td className="px-3 py-2">
                        {isRenaming ? (
                          <div className="flex min-w-[180px] items-center gap-1">
                            <input
                              autoFocus
                              value={renameValue}
                              onChange={(event) => setRenameValue(event.target.value)}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') handleSaveRename(strategy.id);
                                if (event.key === 'Escape') setRenamingId(null);
                              }}
                              className={cn(inputClassName, 'h-8 py-1 text-sm')}
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-8 px-2"
                              disabled={!renameValue.trim() || updateMutation.isPending}
                              onClick={() => handleSaveRename(strategy.id)}
                            >
                              <Save className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-8 px-2"
                              onClick={() => setRenamingId(null)}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ) : (
                          <span className="font-medium">{strategy.name}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            'rounded px-1.5 py-0.5 text-[10px] font-medium',
                            isHybrid
                              ? 'bg-violet-500/15 text-violet-700 dark:text-violet-300'
                              : 'bg-muted text-muted-foreground',
                          )}
                        >
                          {KIND_LABELS[strategy.kind]}
                        </span>
                      </td>
                      <td className="px-3 py-2 tabular-nums">{strategy.timeframe}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {ORIGIN_LABELS[strategy.origin]}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">
                        {formatUpdatedAt(strategy.updatedAt)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <StrategyRowMenu
                          strategy={strategy}
                          busy={busy}
                          onLoad={() => void handleLoad(strategy.id)}
                          onRename={() => handleStartRename(strategy)}
                          onEdit={() => void handleStartEdit(strategy.id)}
                          onDuplicate={() => duplicateMutation.mutate(strategy.id)}
                          onDelete={() => handleDelete(strategy)}
                          onPublishScore={
                            canShowPublishScoreAction(strategy)
                              ? () => void handlePublishScoreToChart(strategy.id)
                              : undefined
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {filteredStrategies.map((strategy) => {
            if (editingId !== strategy.id) return null;
            const isHybrid = strategy.kind === 'hybrid';

            return (
              <section
                key={`edit-${strategy.id}`}
                className="space-y-2 rounded-lg border border-border bg-card p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium">Editar «{strategy.name}»</p>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                    Cerrar
                  </Button>
                </div>
                <label className="block text-xs">
                  Nombre
                  <input
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    className={fieldClass}
                  />
                </label>
                {isHybrid && (
                  <>
                    <label className="block text-xs">
                      Gate preset
                      <select
                        value={editGatePreset}
                        onChange={(event) =>
                          setEditGatePreset(event.target.value as BacktestStrategyType)
                        }
                        className={fieldClass}
                      >
                        {HYBRID_GATE_PRESET_KEYS.map((key) => (
                          <option key={key} value={key}>
                            {BACKTEST_STRATEGIES[key].label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-xs">
                      Rating mínimo
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={editMinScore}
                        onChange={(event) => setEditMinScore(Number(event.target.value) || 0)}
                        className={fieldClass}
                      />
                    </label>
                    <label className="block text-xs">
                      Calidad datos mínima
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={editMinDataQuality}
                        onChange={(event) =>
                          setEditMinDataQuality(Number(event.target.value) || 0)
                        }
                        className={fieldClass}
                      />
                    </label>
                    <label className="block text-xs">
                      PER máx. (opcional)
                      <input
                        type="number"
                        min={0}
                        value={editMaxPe}
                        onChange={(event) => setEditMaxPe(event.target.value)}
                        className={fieldClass}
                      />
                    </label>
                    <label className="block text-xs">
                      Cap. mínima (M€, opcional)
                      <input
                        type="number"
                        min={0}
                        value={editMinCap}
                        onChange={(event) => setEditMinCap(event.target.value)}
                        className={fieldClass}
                      />
                    </label>
                  </>
                )}
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={!editName.trim() || updateMutation.isPending}
                    onClick={() => {
                      void api.getStrategy(strategy.id).then((response) => {
                        const config = buildEditConfig(
                          scanConfigFromStrategyDefinition(response.data),
                        );
                        updateMutation.mutate({
                          id: strategy.id,
                          name: editName.trim(),
                          config,
                        });
                      });
                    }}
                  >
                    {updateMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>
                        <Save className="mr-1 h-3.5 w-3.5" />
                        Guardar cambios
                      </>
                    )}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                    Cancelar
                  </Button>
                </div>
              </section>
            );
          })}

          {actionError && <p className="text-xs text-destructive">{actionError}</p>}
        </div>
      )}
    </ScreenerPanelShell>
  );
}
