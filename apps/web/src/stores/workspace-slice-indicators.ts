import {
  findIndicatorDefinition,
  normalizeParameters,
  hasDuplicateInstance,
  newIndicatorInstanceId,
  instanceSpecKey,
  dataParametersKey,
  mergeDisplayFromInstances,
  seedIndicatorInstancesFromDisplay,
  isSubPanelInstance,
  assignSubPanelWeightOnAdd,
  adjustSubPanelWeightsAfterVisibilityChange,
  redistributeSubPanelWeightAfterRemove,
  visibleSubPanelInstances,
  displayPatchForInstance,
  findInstanceBySpec,
  findInstanceByPreset,
  findIndicatorPreset,
  instanceFromPreset,
  forkIndicatorPreset,
  duplicateIndicatorPreset,
  newIndicatorPresetId,
  presetFromInstance,
  togglePresetInTemplate,
  templateHasIndicators,
  instancesFromTemplate,
  rebalanceSubPanelWeights,
  indicatorTemplateFromInstances,
  createBlankIndicatorTemplate,
  newIndicatorTemplateId,
  createAiIndicatorVariantPreset,
  DEFAULT_INDICATOR_TEMPLATES,
  DEFAULT_SYSTEM_PRESETS,
  DEFAULT_INDICATOR_FAVORITES,
  favoriteRefKey,
  findInstanceByRef,
  DEFAULT_CHART_CONFIG,
  type ChartIndicatorInstance,
  type IndicatorPreset,
  type IndicatorTemplate,
} from "@bolsa/shared";
import {
  type WorkspaceSlice,
  finalizeChartWorkspace,
  mapTabIndicators,
  getListIndicatorFavorites,
  appendPresetToPersonalTemplate,
  cloneChartConfig,
  flushDrawingAutoSave,
} from "./workspace-store-core";

export const indicatorsSlice: WorkspaceSlice = (get, set) => ({
  addIndicatorInstance: (definitionId, parameters, chartId) => {
    const definition = findIndicatorDefinition(definitionId);
    if (!definition) return false;
    const params = normalizeParameters(definition, parameters ?? {});
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return false;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (
      !tab ||
      hasDuplicateInstance(tab.indicatorInstances, definitionId, params)
    ) {
      return false;
    }
    set((state) => ({
      workspace: finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((item) => {
          if (item.id !== targetId) return item;
          const instance: ChartIndicatorInstance = {
            instanceId: newIndicatorInstanceId(definitionId, params),
            definitionId,
            parameters: params,
            visible: true,
          };
          const indicatorInstances = assignSubPanelWeightOnAdd(
            [...item.indicatorInstances, instance],
            instance.instanceId,
          );
          return {
            ...item,
            activeIndicatorTemplateId: null,
            indicatorInstances,
            chart: {
              ...item.chart,
              display: mergeDisplayFromInstances(
                item.chart.display,
                indicatorInstances,
              ),
            },
          };
        }),
      }),
      isDirty: true,
    }));
    return true;
  },
  setShowFinalistTop1Indicators: (enabled, specs, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return;
    set((state) => {
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      if (!tab) return state;

      const desired = specs ?? [];
      const desiredKeys = new Set<string>();
      const toAdd: ChartIndicatorInstance[] = [];
      for (const spec of desired) {
        const definition = findIndicatorDefinition(spec.definitionId);
        if (!definition) continue;
        const params = normalizeParameters(definition, spec.parameters ?? {});
        const key = instanceSpecKey(definition.id, params);
        desiredKeys.add(key);
        toAdd.push({
          instanceId: newIndicatorInstanceId(spec.definitionId, params),
          definitionId: spec.definitionId,
          parameters: params,
          visible: true,
          origin: "finalist-top1",
        });
      }

      const existingTop = tab.indicatorInstances.filter(
        (inst) => inst.origin === "finalist-top1",
      );
      const existingKeys = new Set(
        existingTop.map((inst) =>
          instanceSpecKey(inst.definitionId, inst.parameters),
        ),
      );
      const sameSpecs =
        desiredKeys.size === existingKeys.size &&
        [...desiredKeys].every((k) => existingKeys.has(k));
      if (
        tab.showFinalistTop1Indicators === enabled &&
        (!enabled || sameSpecs)
      ) {
        return state;
      }

      let indicatorInstances = tab.indicatorInstances.filter(
        (inst) => inst.origin !== "finalist-top1",
      );
      if (enabled) {
        for (const instance of toAdd) {
          if (
            hasDuplicateInstance(
              indicatorInstances,
              instance.definitionId,
              instance.parameters,
            )
          ) {
            continue;
          }
          indicatorInstances = assignSubPanelWeightOnAdd(
            [...indicatorInstances, instance],
            instance.instanceId,
          );
        }
      }
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((item) =>
            item.id !== targetId
              ? item
              : {
                  ...mapTabIndicators(
                    item,
                    indicatorInstances,
                    item.activeIndicatorTemplateId,
                  ),
                  showFinalistTop1Indicators: enabled,
                },
          ),
        }),
        isDirty: true,
      };
    });
  },
  syncFinalistTop1Indicators: (specs, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (!tab?.showFinalistTop1Indicators) return;
    get().setShowFinalistTop1Indicators(true, specs, targetId);
  },
  setFinalistTop1DefaultForAll: (enabled) => {
    set((state) => {
      const prevDefault = Boolean(
        state.workspace.preferences.finalistTop1DefaultOn,
      );
      const chartsUnchanged =
        prevDefault === enabled &&
        state.workspace.charts.every(
          (tab) => Boolean(tab.showFinalistTop1Indicators) === enabled,
        );
      if (chartsUnchanged) return state;

      const charts = state.workspace.charts.map((tab) => {
        if (enabled) {
          if (tab.showFinalistTop1Indicators) return tab;
          return { ...tab, showFinalistTop1Indicators: true };
        }
        if (!tab.showFinalistTop1Indicators) {
          const hasTop = tab.indicatorInstances.some(
            (inst) => inst.origin === "finalist-top1",
          );
          if (!hasTop) return tab;
        }
        const indicatorInstances = tab.indicatorInstances.filter(
          (inst) => inst.origin !== "finalist-top1",
        );
        return {
          ...mapTabIndicators(
            tab,
            indicatorInstances,
            tab.activeIndicatorTemplateId,
          ),
          showFinalistTop1Indicators: false,
        };
      });

      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          preferences: {
            ...state.workspace.preferences,
            finalistTop1DefaultOn: enabled,
          },
          charts,
        }),
        isDirty: true,
      };
    });
  },
  toggleIndicatorOnChart: (definitionId, parameters, chartId) => {
    const definition = findIndicatorDefinition(definitionId);
    if (!definition) return "failed";
    const params = normalizeParameters(definition, parameters ?? {});
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return "failed";
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (!tab) return "failed";
    const existing = findInstanceBySpec(
      tab.indicatorInstances,
      definitionId,
      params,
    );
    if (existing) {
      get().removeIndicatorInstance(existing.instanceId, targetId);
      return "removed";
    }
    return get().addIndicatorInstance(definitionId, params, targetId)
      ? "added"
      : "failed";
  },
  setIndicatorInstanceParameters: (instanceId, parameters, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return false;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (!tab) return false;
    const current = tab.indicatorInstances.find(
      (item) => item.instanceId === instanceId,
    );
    if (!current) return false;
    const definition = findIndicatorDefinition(current.definitionId);
    if (!definition) return false;
    const params = normalizeParameters(definition, parameters);
    const others = tab.indicatorInstances.filter(
      (item) => item.instanceId !== instanceId,
    );
    if (hasDuplicateInstance(others, current.definitionId, params))
      return false;
    set((state) => ({
      workspace: finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((chartTab) => {
          if (chartTab.id !== targetId) return chartTab;
          const indicatorInstances = chartTab.indicatorInstances.map(
            (instance) => {
              if (instance.instanceId !== instanceId) return instance;
              return {
                ...instance,
                instanceId: newIndicatorInstanceId(
                  instance.definitionId,
                  params,
                ),
                parameters: params,
              };
            },
          );
          return {
            ...chartTab,
            activeIndicatorTemplateId: null,
            indicatorInstances,
            chart: {
              ...chartTab.chart,
              display: mergeDisplayFromInstances(
                chartTab.chart.display,
                indicatorInstances,
              ),
            },
          };
        }),
      }),
      isDirty: true,
    }));
    return true;
  },
  updateIndicatorInstance: (instanceId, patch, chartId) => {
    let resultId: string | null = null;
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      if (!tab) return state;
      const current = tab.indicatorInstances.find(
        (item) => item.instanceId === instanceId,
      );
      if (!current) return state;
      if (patch.parameters) {
        const definition = findIndicatorDefinition(current.definitionId);
        if (!definition) return state;
        const params = normalizeParameters(definition, patch.parameters);
        const others = tab.indicatorInstances.filter(
          (item) => item.instanceId !== instanceId,
        );
        if (hasDuplicateInstance(others, current.definitionId, params))
          return state;
      }
      const nextScaleZoom =
        patch.scaleZoom != null
          ? Math.min(3, Math.max(0.5, patch.scaleZoom))
          : undefined;
      const definition = findIndicatorDefinition(current.definitionId);
      if (!definition) return state;

      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((chartTab) => {
            if (chartTab.id !== targetId) return chartTab;
            const indicatorInstances = chartTab.indicatorInstances.map(
              (instance) => {
                if (instance.instanceId !== instanceId) return instance;
                const nextParams = patch.parameters
                  ? normalizeParameters(definition, patch.parameters)
                  : instance.parameters;
                const dataChanged =
                  patch.parameters != null &&
                  dataParametersKey(instance.parameters) !==
                    dataParametersKey(nextParams);
                const nextInstanceId = dataChanged
                  ? newIndicatorInstanceId(instance.definitionId, nextParams)
                  : instance.instanceId;
                const next = {
                  ...instance,
                  ...patch,
                  ...(nextScaleZoom != null
                    ? { scaleZoom: nextScaleZoom }
                    : {}),
                  parameters: nextParams,
                  instanceId: nextInstanceId,
                };
                resultId = next.instanceId;
                return next;
              },
            );
            const rebalanced =
              patch.visible !== undefined && isSubPanelInstance(current)
                ? adjustSubPanelWeightsAfterVisibilityChange(
                    indicatorInstances,
                    instanceId,
                    patch.visible,
                  )
                : indicatorInstances;
            return {
              ...chartTab,
              activeIndicatorTemplateId: null,
              indicatorInstances: rebalanced,
              chart: {
                ...chartTab.chart,
                display: mergeDisplayFromInstances(
                  chartTab.chart.display,
                  rebalanced,
                ),
              },
            };
          }),
        }),
        isDirty: true,
      };
    });
    return resultId;
  },
  duplicateIndicatorInstance: (instanceId, chartId) => {
    let newId: string | null = null;
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      if (!tab) return state;
      const index = tab.indicatorInstances.findIndex(
        (item) => item.instanceId === instanceId,
      );
      if (index < 0) return state;
      const source = tab.indicatorInstances[index]!;
      const clone: ChartIndicatorInstance = {
        ...source,
        instanceId: newIndicatorInstanceId(
          source.definitionId,
          source.parameters,
        ),
        visible: source.visible,
      };
      newId = clone.instanceId;
      let indicatorInstances = [...tab.indicatorInstances];
      indicatorInstances.splice(index + 1, 0, clone);
      if (isSubPanelInstance(clone)) {
        indicatorInstances = assignSubPanelWeightOnAdd(
          indicatorInstances,
          clone.instanceId,
        );
      }
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((chartTab) => {
            if (chartTab.id !== targetId) return chartTab;
            return {
              ...chartTab,
              activeIndicatorTemplateId: null,
              indicatorInstances,
              chart: {
                ...chartTab.chart,
                display: mergeDisplayFromInstances(
                  chartTab.chart.display,
                  indicatorInstances,
                ),
              },
            };
          }),
        }),
        isDirty: true,
      };
    });
    return newId;
  },
  togglePresetOnChart: (presetId, chartId) => {
    const presets = get().workspace.indicatorPresets ?? [];
    const preset = findIndicatorPreset(presets, presetId);
    if (!preset) return "failed";
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return "failed";
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (!tab) return "failed";
    const existing = findInstanceByPreset(tab.indicatorInstances, presetId);
    if (existing) {
      get().removeIndicatorInstance(existing.instanceId, targetId);
      return "removed";
    }
    const instance = instanceFromPreset(preset);
    set((state) => ({
      workspace: finalizeChartWorkspace({
        ...state.workspace,
        charts: state.workspace.charts.map((chartTab) => {
          if (chartTab.id !== targetId) return chartTab;
          const indicatorInstances = [...chartTab.indicatorInstances, instance];
          return {
            ...chartTab,
            activeIndicatorTemplateId: null,
            indicatorInstances,
            chart: {
              ...chartTab.chart,
              display: mergeDisplayFromInstances(
                chartTab.chart.display,
                indicatorInstances,
              ),
            },
          };
        }),
      }),
      isDirty: true,
    }));
    return "added";
  },
  togglePresetVisibilityOnChart: (presetId, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return false;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    const existing = tab
      ? findInstanceByPreset(tab.indicatorInstances, presetId)
      : undefined;
    if (!existing) return false;
    const nextId = get().updateIndicatorInstance(
      existing.instanceId,
      { visible: !existing.visible },
      targetId,
    );
    return Boolean(nextId);
  },
  togglePresetInTemplate: (templateId, presetId) =>
    set((state) => {
      const templates = state.workspace.indicatorTemplates ?? [];
      const template = templates.find((item) => item.id === templateId);
      if (!template) return state;
      const next = togglePresetInTemplate(template, presetId);
      return {
        workspace: {
          ...state.workspace,
          indicatorTemplates: templates.map((item) =>
            item.id === templateId ? next : item,
          ),
        },
        isDirty: true,
      };
    }),
  forkPresetToPersonal: (sourcePresetId, name, patch) => {
    const presets = get().workspace.indicatorPresets ?? [];
    const source = findIndicatorPreset(presets, sourcePresetId);
    if (!source) return null;
    const forked = forkIndicatorPreset(source, {
      name,
      parameters: patch?.parameters,
      lineWidth: patch?.lineWidth,
      showLastValue: patch?.showLastValue,
    });
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorPresets: [...(state.workspace.indicatorPresets ?? []), forked],
        indicatorTemplates: appendPresetToPersonalTemplate(
          state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
          forked.id,
        ),
      },
      isDirty: true,
    }));
    return forked.id;
  },
  createAiIndicatorVariant: (options) => {
    const preset = createAiIndicatorVariantPreset(options);
    if (!preset) return null;
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorPresets: [...(state.workspace.indicatorPresets ?? []), preset],
        indicatorTemplates: appendPresetToPersonalTemplate(
          state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
          preset.id,
        ),
      },
      isDirty: true,
    }));
    return preset.id;
  },
  addIndicatorPresetFromDraft: (preset, name) => {
    const nextPreset: IndicatorPreset = {
      ...preset,
      id: preset.id.startsWith("draft-") ? newIndicatorPresetId() : preset.id,
      name: name?.trim() || preset.name,
      locked: false,
    };
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorPresets: [
          ...(state.workspace.indicatorPresets ?? []),
          nextPreset,
        ],
        indicatorTemplates: appendPresetToPersonalTemplate(
          state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
          nextPreset.id,
        ),
      },
      isDirty: true,
    }));
    return nextPreset.id;
  },
  forkInstanceToPersonalPreset: (instanceId, name, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return null;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    const instance = tab?.indicatorInstances.find(
      (item) => item.instanceId === instanceId,
    );
    if (!instance) return null;
    const preset = presetFromInstance(instance, name, {
      derivedFromPresetId: instance.presetId,
    });
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorPresets: [...(state.workspace.indicatorPresets ?? []), preset],
        indicatorTemplates: appendPresetToPersonalTemplate(
          state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
          preset.id,
        ),
      },
      isDirty: true,
    }));
    return preset.id;
  },
  removeIndicatorPreset: (presetId) =>
    set((state) => {
      const preset = findIndicatorPreset(
        state.workspace.indicatorPresets ?? [],
        presetId,
      );
      if (!preset || preset.locked) return state;
      return {
        workspace: {
          ...state.workspace,
          indicatorPresets: (state.workspace.indicatorPresets ?? []).filter(
            (item) => item.id !== presetId,
          ),
          indicatorTemplates: (state.workspace.indicatorTemplates ?? []).map(
            (template) => ({
              ...template,
              presetIds: (template.presetIds ?? []).filter(
                (id) => id !== presetId,
              ),
            }),
          ),
        },
        isDirty: true,
      };
    }),
  updateIndicatorPreset: (presetId, patch) =>
    set((state) => {
      const current = findIndicatorPreset(
        state.workspace.indicatorPresets ?? [],
        presetId,
      );
      if (!current || current.locked) return state;
      const definition = findIndicatorDefinition(current.definitionId);
      const parameters =
        patch.parameters && definition
          ? normalizeParameters(definition, {
              ...current.parameters,
              ...patch.parameters,
            })
          : patch.parameters
            ? { ...current.parameters, ...patch.parameters }
            : current.parameters;
      const nextPreset = {
        ...current,
        ...patch,
        parameters,
      };
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          indicatorPresets: (state.workspace.indicatorPresets ?? []).map(
            (preset) => (preset.id === presetId ? nextPreset : preset),
          ),
          charts: state.workspace.charts.map((tab) => ({
            ...tab,
            indicatorInstances: tab.indicatorInstances.map((instance) => {
              if (instance.presetId !== presetId) return instance;
              return {
                ...instance,
                parameters: { ...nextPreset.parameters },
                lineWidth: nextPreset.lineWidth ?? instance.lineWidth,
                showLastValue:
                  nextPreset.showLastValue ?? instance.showLastValue,
              };
            }),
          })),
        }),
        isDirty: true,
      };
    }),
  duplicateUserIndicatorPreset: (presetId, name) => {
    const presets = get().workspace.indicatorPresets ?? [];
    const source = findIndicatorPreset(presets, presetId);
    if (!source) return null;
    const copy = duplicateIndicatorPreset(source, name);
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorPresets: [...(state.workspace.indicatorPresets ?? []), copy],
        indicatorTemplates: appendPresetToPersonalTemplate(
          state.workspace.indicatorTemplates ?? DEFAULT_INDICATOR_TEMPLATES,
          copy.id,
        ),
      },
      isDirty: true,
    }));
    return copy.id;
  },
  swapChartInstanceToPreset: (instanceId, presetId, chartId) => {
    const presets = get().workspace.indicatorPresets ?? [];
    const preset = findIndicatorPreset(presets, presetId);
    if (!preset) return null;
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return null;
    let resultId: string | null = null;
    set((state) => {
      const tab = state.workspace.charts.find((item) => item.id === targetId);
      if (!tab) return state;
      const nextInstance = instanceFromPreset(preset);
      resultId = nextInstance.instanceId;
      const indicatorInstances = [
        ...tab.indicatorInstances.filter(
          (item) => item.instanceId !== instanceId,
        ),
        nextInstance,
      ];
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((chartTab) => {
            if (chartTab.id !== targetId) return chartTab;
            return {
              ...chartTab,
              activeIndicatorTemplateId: null,
              indicatorInstances,
              chart: {
                ...chartTab.chart,
                display: mergeDisplayFromInstances(
                  chartTab.chart.display,
                  indicatorInstances,
                ),
              },
            };
          }),
        }),
        isDirty: true,
      };
    });
    return resultId;
  },
  setDefaultIndicatorTemplate: (templateId) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        defaultIndicatorTemplateId: templateId,
      },
      isDirty: true,
    })),
  removeIndicatorInstance: (instanceId, chartId) =>
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) => {
            if (tab.id !== targetId) return tab;
            const removed = tab.indicatorInstances.find(
              (item) => item.instanceId === instanceId,
            );
            let indicatorInstances = tab.indicatorInstances.filter(
              (item) => item.instanceId !== instanceId,
            );
            if (removed && isSubPanelInstance(removed) && removed.visible) {
              const remainingCount =
                visibleSubPanelInstances(indicatorInstances).length;
              const removedWeight =
                removed.subPanelWeight ??
                (remainingCount > 0 ? 100 / (remainingCount + 1) : 100);
              indicatorInstances = redistributeSubPanelWeightAfterRemove(
                indicatorInstances,
                removedWeight,
              );
            }
            let nextDisplay = tab.chart.display;
            if (removed) {
              const offPatch = displayPatchForInstance(
                removed.definitionId,
                removed.parameters,
                false,
              );
              nextDisplay = { ...nextDisplay, ...offPatch };
            }
            return {
              ...tab,
              activeIndicatorTemplateId: null,
              indicatorInstances,
              chart: {
                ...tab.chart,
                display: mergeDisplayFromInstances(
                  nextDisplay,
                  indicatorInstances,
                ),
              },
            };
          }),
        }),
        isDirty: true,
      };
    }),
  reorderIndicatorInstances: (fromInstanceId, toInstanceId, chartId) =>
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) => {
            if (tab.id !== targetId) return tab;
            const instances = [...tab.indicatorInstances];
            const from = instances.findIndex(
              (item) => item.instanceId === fromInstanceId,
            );
            const to = instances.findIndex(
              (item) => item.instanceId === toInstanceId,
            );
            if (from < 0 || to < 0 || from === to) return tab;
            const [moved] = instances.splice(from, 1);
            instances.splice(to, 0, moved!);
            return {
              ...tab,
              activeIndicatorTemplateId: null,
              indicatorInstances: instances,
              chart: {
                ...tab.chart,
                display: mergeDisplayFromInstances(
                  tab.chart.display,
                  instances,
                ),
              },
            };
          }),
        }),
        isDirty: true,
      };
    }),
  resetChartConfig: (chartId) =>
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) => {
            if (tab.id !== targetId) return tab;
            const chart = cloneChartConfig(DEFAULT_CHART_CONFIG);
            return {
              ...tab,
              chart,
              indicatorInstances: seedIndicatorInstancesFromDisplay(
                chart.display,
              ),
            };
          }),
        }),
        isDirty: true,
      };
    }),
  getIndicatorFavoritesForList: (listId) =>
    getListIndicatorFavorites(get().workspace, listId),
  toggleIndicatorFavorite: (listId, ref) =>
    set((state) => {
      const current = getListIndicatorFavorites(state.workspace, listId);
      const key = favoriteRefKey(ref);
      const exists = current.some((item) => favoriteRefKey(item) === key);
      const next = exists
        ? current.filter((item) => favoriteRefKey(item) !== key)
        : [
            ...current,
            {
              definitionId: ref.definitionId,
              parameters: { ...ref.parameters },
              ...(ref.shortLabel ? { shortLabel: ref.shortLabel } : {}),
            },
          ];
      const favorites =
        next.length > 0
          ? next
          : DEFAULT_INDICATOR_FAVORITES.map((item) => ({
              definitionId: item.definitionId,
              parameters: { ...item.parameters },
            }));
      return {
        workspace: {
          ...state.workspace,
          indicatorFavoritesByListId: {
            ...(state.workspace.indicatorFavoritesByListId ?? {}),
            [listId]: favorites,
          },
          updatedAt: new Date().toISOString(),
        },
        isDirty: !state.workspace.preferences.autoSave,
      };
    }),
  toggleIndicatorByFavorite: (_listId, ref, chartId) => {
    const targetId = chartId ?? get().workspace.activeChartId;
    if (!targetId) return;
    const tab = get().workspace.charts.find((item) => item.id === targetId);
    if (!tab) return;
    const existing = findInstanceByRef(tab.indicatorInstances, ref);
    if (existing) {
      get().updateIndicatorInstance(
        existing.instanceId,
        { visible: !existing.visible },
        targetId,
      );
      return;
    }
    get().addIndicatorInstance(ref.definitionId, ref.parameters, targetId);
  },
  addIndicatorTemplate: () => {
    const template = createBlankIndicatorTemplate();
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorTemplates: [
          ...(state.workspace.indicatorTemplates ?? []),
          template,
        ],
      },
      isDirty: true,
    }));
    return template;
  },
  updateIndicatorTemplate: (templateId, patch) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorTemplates: (state.workspace.indicatorTemplates ?? []).map(
          (template) => {
            if (template.id !== templateId) return template;
            return {
              ...template,
              ...patch,
              items: patch.items
                ? patch.items.map((item) => ({
                    ...item,
                    parameters: { ...item.parameters },
                  }))
                : template.items,
            };
          },
        ),
      },
      isDirty: true,
    })),
  removeIndicatorTemplate: (templateId) =>
    set((state) => {
      const target = state.workspace.indicatorTemplates?.find(
        (t) => t.id === templateId,
      );
      if (!target || target.locked || target.builtin) return state;
      return {
        workspace: {
          ...state.workspace,
          indicatorTemplates: (state.workspace.indicatorTemplates ?? []).filter(
            (t) => t.id !== templateId,
          ),
          charts: state.workspace.charts.map((tab) =>
            tab.activeIndicatorTemplateId === templateId
              ? { ...tab, activeIndicatorTemplateId: null }
              : tab,
          ),
        },
        isDirty: true,
      };
    }),
  duplicateIndicatorTemplate: (templateId) => {
    const source = get().workspace.indicatorTemplates?.find(
      (t) => t.id === templateId,
    );
    if (!source) return null;
    const copy: IndicatorTemplate = {
      ...source,
      id: newIndicatorTemplateId(),
      name: `${source.name} (copia)`,
      locked: false,
      builtin: false,
      source: "custom",
      presetIds: [...(source.presetIds ?? [])],
      items: source.items?.map((item) => ({
        ...item,
        parameters: { ...item.parameters },
      })),
    };
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorTemplates: [
          ...(state.workspace.indicatorTemplates ?? []),
          copy,
        ],
      },
      isDirty: true,
    }));
    return copy;
  },
  applyIndicatorTemplate: (templateId, chartId) => {
    set((state) => {
      const targetId = chartId ?? state.workspace.activeChartId;
      if (!targetId) return state;
      const template = (state.workspace.indicatorTemplates ?? []).find(
        (item) => item.id === templateId,
      );
      if (!template) return state;
      if (!templateHasIndicators(template)) return state;
      const instances = rebalanceSubPanelWeights(
        instancesFromTemplate(
          template,
          state.workspace.indicatorPresets ?? DEFAULT_SYSTEM_PRESETS,
        ),
      );
      return {
        workspace: finalizeChartWorkspace({
          ...state.workspace,
          charts: state.workspace.charts.map((tab) =>
            tab.id !== targetId
              ? tab
              : {
                  ...mapTabIndicators(tab, instances, template.id),
                  showFinalistTop1Indicators: false,
                },
          ),
        }),
        isDirty: !state.workspace.preferences.autoSave,
      };
    });
    flushDrawingAutoSave(get, true);
  },
  createIndicatorTemplateFromChart: (chartId, name) => {
    const tab = get().workspace.charts.find((item) => item.id === chartId);
    const instances = tab?.indicatorInstances ?? [];
    const presets = get().workspace.indicatorPresets ?? DEFAULT_SYSTEM_PRESETS;
    const template = indicatorTemplateFromInstances(
      instances,
      name?.trim() || "Plantilla del gráfico",
      presets,
    );
    set((state) => ({
      workspace: {
        ...state.workspace,
        indicatorTemplates: [
          ...(state.workspace.indicatorTemplates ?? []),
          template,
        ],
      },
      isDirty: true,
    }));
    return template;
  },
});
