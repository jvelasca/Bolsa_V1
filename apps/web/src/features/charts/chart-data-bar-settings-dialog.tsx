import { useEffect, useState } from "react";
import type {
  ChartToolbarChartOverrides,
  ChartToolbarGlobalConfig,
} from "@bolsa/shared";
import {
  CHART_TOOLBAR_CHART_VISIBILITY_LABELS,
  normalizeChartToolbarGlobalConfig,
  resolveChartToolbarForTab,
} from "@bolsa/shared";

import { Button } from "@/components/ui/button";
import { Dialog, FieldRow, checkboxClassName } from "@/components/ui/dialog";
import {
  ColorField,
  DataBarWorkspaceDefaultsSection,
  FavoritesWorkspaceSection,
} from "@/features/charts/chart-toolbar-settings-fields";
import { useUiStore } from "@/stores/ui-store";
import { useActiveChartTab, useWorkspaceStore } from "@/stores/workspace-store";

/** Configuración exclusiva de la barra de datos (Escala · Valor · Cursor · atajos). */
export function ChartDataBarSettingsDialog() {
  const open = useUiStore((s) => s.chartDataBarSettingsOpen);
  const close = useUiStore((s) => s.closeChartDataBarSettings);
  const globalRaw = useWorkspaceStore((s) => s.workspace.chartToolbarGlobal);
  const activeTab = useActiveChartTab();
  const updateGlobal = useWorkspaceStore((s) => s.updateChartToolbarGlobal);
  const updateChartToolbar = useWorkspaceStore(
    (s) => s.updateChartToolbarForChart,
  );
  const resetChartToolbar = useWorkspaceStore(
    (s) => s.resetChartToolbarForChart,
  );
  const save = useWorkspaceStore((s) => s.save);

  const [globalDraft, setGlobalDraft] = useState<ChartToolbarGlobalConfig>(() =>
    normalizeChartToolbarGlobalConfig(globalRaw),
  );
  const [chartDraft, setChartDraft] = useState<ChartToolbarChartOverrides>({});

  useEffect(() => {
    if (!open) return;
    setGlobalDraft(normalizeChartToolbarGlobalConfig(globalRaw));
    setChartDraft(activeTab?.toolbar ?? {});
  }, [open, globalRaw, activeTab?.toolbar, activeTab?.id]);

  const resolvedPreview = resolveChartToolbarForTab(
    globalDraft,
    chartDraft.useGlobalDefaults ? { useGlobalDefaults: true } : chartDraft,
  );

  function handleSave() {
    updateGlobal(globalDraft);
    if (activeTab) {
      if (chartDraft.useGlobalDefaults) {
        resetChartToolbar(activeTab.id);
      } else {
        updateChartToolbar(activeTab.id, chartDraft);
      }
    }
    save();
    close();
  }

  function handleResetWorkspaceDefaults() {
    const defaults = normalizeChartToolbarGlobalConfig();
    setGlobalDraft((prev) => ({
      ...prev,
      defaultTimeframe: defaults.defaultTimeframe,
      defaultSeriesType: defaults.defaultSeriesType,
      chartVisibilityDefaults: defaults.chartVisibilityDefaults,
      chartLayoutDefaults: defaults.chartLayoutDefaults,
      appearance: {
        ...prev.appearance,
        chartBarBackground: defaults.appearance.chartBarBackground,
      },
      timeframeFavorites: defaults.timeframeFavorites,
      seriesTypeFavorites: defaults.seriesTypeFavorites,
      instrumentFieldFavorites: defaults.instrumentFieldFavorites,
      cursorFieldFavorites: defaults.cursorFieldFavorites,
      inspectorBarShortcutFavorites: defaults.inspectorBarShortcutFavorites,
    }));
  }

  function handleResetChartOverrides() {
    setChartDraft({});
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Barra de datos del gráfico"
      description="Escala, Estilo, Valor, Cursor y apariencia de esta franja. Los atajos al inspector se fijan con estrella en Config."
      className="max-w-lg"
    >
      <DataBarWorkspaceDefaultsSection
        draft={globalDraft}
        onChange={setGlobalDraft}
      />

      {activeTab && (
        <section className="mb-4 mt-6 space-y-3 border-t border-border pt-4">
          <div>
            <p className="text-xs font-medium text-foreground">Este gráfico</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Personaliza solo la pestaña activa. Si usas los defaults del
              workspace, hereda la sección anterior.
            </p>
          </div>

          <label className="flex items-center gap-2 text-xs font-medium">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={chartDraft.useGlobalDefaults ?? false}
              onChange={(event) =>
                setChartDraft((prev) => ({
                  ...prev,
                  useGlobalDefaults: event.target.checked,
                }))
              }
            />
            Usar valores por defecto del workspace (sin personalizar este
            gráfico)
          </label>

          {!chartDraft.useGlobalDefaults && (
            <>
              <section className="space-y-2">
                <p className="text-xs font-medium text-foreground">
                  Elementos visibles
                </p>
                <div className="grid grid-cols-2 gap-1.5">
                  {(
                    Object.keys(CHART_TOOLBAR_CHART_VISIBILITY_LABELS) as Array<
                      keyof typeof CHART_TOOLBAR_CHART_VISIBILITY_LABELS
                    >
                  )
                    .filter(
                      (key) =>
                        key !== "settingsButton" && key !== "overlayIndicators",
                    )
                    .map((key) => (
                      <label
                        key={key}
                        className="flex items-center gap-2 text-xs"
                      >
                        <input
                          type="checkbox"
                          className={checkboxClassName}
                          checked={
                            chartDraft.visibility?.[key] ??
                            resolvedPreview.visibility[key]
                          }
                          onChange={() =>
                            setChartDraft((prev) => ({
                              ...prev,
                              visibility: {
                                ...globalDraft.chartVisibilityDefaults,
                                ...prev.visibility,
                                [key]: !(
                                  prev.visibility?.[key] ??
                                  resolvedPreview.visibility[key]
                                ),
                              },
                            }))
                          }
                        />
                        {CHART_TOOLBAR_CHART_VISIBILITY_LABELS[key]}
                      </label>
                    ))}
                </div>
              </section>

              <section className="space-y-2">
                <p className="text-xs font-medium text-foreground">
                  Distribución
                </p>
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    className={checkboxClassName}
                    checked={
                      chartDraft.layout?.wrapRows ??
                      resolvedPreview.layout.wrapRows
                    }
                    onChange={() =>
                      setChartDraft((prev) => ({
                        ...prev,
                        layout: {
                          ...globalDraft.chartLayoutDefaults,
                          ...prev.layout,
                          wrapRows: !(
                            prev.layout?.wrapRows ??
                            resolvedPreview.layout.wrapRows
                          ),
                        },
                      }))
                    }
                  />
                  Apilar zonas en varias filas si no caben (sin scroll
                  horizontal)
                </label>
              </section>

              <FieldRow label="Fondo de esta barra">
                <ColorField
                  value={
                    chartDraft.appearance?.chartBarBackground ??
                    globalDraft.appearance.chartBarBackground
                  }
                  onChange={(chartBarBackground) =>
                    setChartDraft((prev) => ({
                      ...prev,
                      appearance: { ...prev.appearance, chartBarBackground },
                    }))
                  }
                />
              </FieldRow>
            </>
          )}
        </section>
      )}

      <section className="mt-6 border-t border-border pt-4">
        <FavoritesWorkspaceSection
          draft={globalDraft}
          onChange={setGlobalDraft}
        />
      </section>

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={handleResetWorkspaceDefaults}
        >
          Restaurar defaults del workspace
        </Button>
        {activeTab && !chartDraft.useGlobalDefaults && (
          <Button
            type="button"
            variant="outline"
            onClick={handleResetChartOverrides}
          >
            Restaurar este gráfico
          </Button>
        )}
        <Button type="button" variant="outline" onClick={close}>
          Cancelar
        </Button>
        <Button type="button" onClick={handleSave}>
          Guardar
        </Button>
      </div>
    </Dialog>
  );
}
