import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  EyeOff,
  Save,
  Trash2,
} from "lucide-react";
import type { ChartIndicatorInstance } from "@bolsa/shared";
import {
  colorForInstance,
  findIndicatorDefinition,
  instanceLabel,
  normalizeParameters,
} from "@bolsa/shared";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTabs,
  FieldRow,
  checkboxClassName,
  inputClassName,
} from "@/components/ui/dialog";
import { IndicatorParametersForm } from "@/features/charts/indicator-parameters-form";
import { subPanelInstancesAll } from "@/features/charts/indicator-compute";
import { requestChartReflow } from "@/features/charts/chart-utils";
import { useUiStore } from "@/stores/ui-store";
import { useActiveChartTab, useWorkspaceStore } from "@/stores/workspace-store";

type ConfigTab = "data" | "style" | "visibility";

const TABS: { id: ConfigTab; label: string }[] = [
  { id: "data", label: "Entrada de datos" },
  { id: "style", label: "Estilo" },
  { id: "visibility", label: "Visibilidad" },
];

export function IndicatorInstanceConfigDialog() {
  const target = useUiStore((s) => s.indicatorConfigTarget);
  const close = useUiStore((s) => s.closeIndicatorConfig);
  const openIndicatorConfig = useUiStore((s) => s.openIndicatorConfig);
  const setSelectedIndicator = useUiStore(
    (s) => s.setSelectedIndicatorInstanceId,
  );
  const activeTab = useActiveChartTab();
  const updateInstance = useWorkspaceStore((s) => s.updateIndicatorInstance);
  const duplicateInstance = useWorkspaceStore(
    (s) => s.duplicateIndicatorInstance,
  );
  const forkInstanceToPersonalPreset = useWorkspaceStore(
    (s) => s.forkInstanceToPersonalPreset,
  );
  const forkPresetToPersonal = useWorkspaceStore((s) => s.forkPresetToPersonal);
  const swapChartInstanceToPreset = useWorkspaceStore(
    (s) => s.swapChartInstanceToPreset,
  );
  const removeInstance = useWorkspaceStore((s) => s.removeIndicatorInstance);
  const reorderInstances = useWorkspaceStore(
    (s) => s.reorderIndicatorInstances,
  );
  const save = useWorkspaceStore((s) => s.save);

  const chartId = target?.chartId ?? activeTab?.id;
  const instance =
    target && activeTab
      ? activeTab.indicatorInstances.find(
          (item) => item.instanceId === target.instanceId,
        )
      : undefined;
  const definition = instance
    ? findIndicatorDefinition(instance.definitionId)
    : undefined;
  const timeframe = activeTab?.timeframe ?? "1d";

  const [tab, setTab] = useState<ConfigTab>("data");
  const [draft, setDraft] = useState<ChartIndicatorInstance | null>(
    instance ?? null,
  );

  useEffect(() => {
    if (target && instance) {
      setDraft({ ...instance });
      setTab("data");
    }
  }, [target, instance]);

  const subIndicators = useMemo(
    () => (activeTab ? subPanelInstancesAll(activeTab.indicatorInstances) : []),
    [activeTab],
  );

  if (!target || !instance || !definition || !draft || !chartId) return null;

  const activeChartId = chartId;
  const activeDraft = draft;
  const isSubPanel = definition.panel === "sub";
  const lineColor = colorForInstance(activeDraft);
  const subIndex = isSubPanel
    ? subIndicators.findIndex(
        (item) => item.instanceId === activeDraft.instanceId,
      )
    : -1;
  const canMoveUp = isSubPanel && subIndex > 0;
  const canMoveDown =
    isSubPanel && subIndex >= 0 && subIndex < subIndicators.length - 1;

  function patch(partial: Partial<ChartIndicatorInstance>) {
    setDraft((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  function patchColor(hex: string) {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            parameters: normalizeParameters(definition!, {
              ...prev.parameters,
              color: hex,
            }),
          }
        : prev,
    );
  }

  function apply() {
    const snapshot = activeDraft;
    const nextId = updateInstance(
      snapshot.instanceId,
      {
        parameters: snapshot.parameters,
        visible: snapshot.visible,
        showLastValue: snapshot.showLastValue,
        scaleZoom: snapshot.scaleZoom,
        lineWidth: snapshot.lineWidth,
      },
      activeChartId,
    );
    if (nextId) {
      setSelectedIndicator(nextId);
      save();
      requestChartReflow();
      close();
    }
  }

  function toggleHiddenNow() {
    const nextVisible = !activeDraft.visible;
    const nextId = updateInstance(
      activeDraft.instanceId,
      { visible: nextVisible },
      activeChartId,
    );
    if (!nextId) return;
    setDraft((prev) =>
      prev ? { ...prev, visible: nextVisible, instanceId: nextId } : prev,
    );
    setSelectedIndicator(nextId);
    save();
    requestChartReflow();
  }

  function saveAsPersonalPreset() {
    const name = window.prompt(
      "Nombre del indicador personal:",
      instanceLabel(activeDraft),
    );
    if (!name?.trim()) return;
    let newPresetId: string | null = null;
    const sourcePresetId = activeDraft.presetId;
    if (sourcePresetId) {
      newPresetId = forkPresetToPersonal(sourcePresetId, name.trim(), {
        parameters: activeDraft.parameters,
        lineWidth: activeDraft.lineWidth,
        showLastValue: activeDraft.showLastValue,
      });
    } else {
      newPresetId = forkInstanceToPersonalPreset(
        activeDraft.instanceId,
        name.trim(),
        activeChartId,
      );
    }
    if (!newPresetId) return;
    save();
    if (
      window.confirm(
        "¿Reemplazar la instancia del gráfico por el nuevo preset personal? (recomendado)",
      )
    ) {
      const nextId = swapChartInstanceToPreset(
        activeDraft.instanceId,
        newPresetId,
        activeChartId,
      );
      if (nextId) setSelectedIndicator(nextId);
    }
    requestChartReflow();
    close();
  }

  function duplicateNow() {
    const nextId = duplicateInstance(activeDraft.instanceId, activeChartId);
    if (!nextId) return;
    save();
    requestChartReflow();
    openIndicatorConfig(activeChartId, nextId);
    setSelectedIndicator(nextId);
  }

  function deleteNow() {
    if (!window.confirm(`¿Eliminar ${instanceLabel(activeDraft)} del gráfico?`))
      return;
    removeInstance(activeDraft.instanceId, activeChartId);
    setSelectedIndicator(null);
    save();
    requestChartReflow();
    close();
  }

  function moveNow(direction: "up" | "down") {
    if (!isSubPanel || subIndex < 0) return;
    const targetIndex = direction === "up" ? subIndex - 1 : subIndex + 1;
    const swapWith = subIndicators[targetIndex];
    if (!swapWith) return;
    reorderInstances(
      activeDraft.instanceId,
      swapWith.instanceId,
      activeChartId,
    );
    save();
    requestChartReflow();
  }

  return (
    <Dialog
      open
      onClose={close}
      title={instanceLabel(activeDraft)}
      description={definition.description}
      className="max-w-md"
    >
      <DialogTabs
        tabs={TABS}
        active={tab}
        onChange={(id) => setTab(id as ConfigTab)}
      />

      {tab === "data" && (
        <div className="mt-4 space-y-3">
          <p className="text-[11px] text-muted-foreground">
            Los datos se calculan con la misma escala temporal del gráfico (
            <span className="font-medium text-foreground">{timeframe}</span>
            ). Al cambiar la escala en la barra superior, todos los indicadores
            se actualizan.
          </p>
          <IndicatorParametersForm
            definition={definition}
            values={activeDraft.parameters}
            onChange={(parameters) => patch({ parameters })}
          />
        </div>
      )}

      {tab === "style" && (
        <div className="mt-4 space-y-4">
          <FieldRow label="Color de línea">
            <div className="flex items-center gap-2">
              <input
                type="color"
                className="h-9 w-12 cursor-pointer rounded border border-border bg-background"
                value={lineColor}
                onChange={(event) => patchColor(event.target.value)}
              />
              <span className="text-xs text-muted-foreground">{lineColor}</span>
            </div>
          </FieldRow>
          <FieldRow label="Grosor de línea">
            <select
              className={inputClassName}
              value={String(activeDraft.lineWidth ?? 2)}
              onChange={(event) =>
                patch({ lineWidth: Number(event.target.value) })
              }
            >
              {[1, 2, 3, 4].map((width) => (
                <option key={width} value={width}>
                  {width}px
                </option>
              ))}
            </select>
          </FieldRow>
          {isSubPanel && (
            <FieldRow label="Zoom eje Y del panel">
              <input
                type="range"
                min={50}
                max={300}
                step={25}
                value={Math.round((activeDraft.scaleZoom ?? 1) * 100)}
                onChange={(event) =>
                  patch({ scaleZoom: Number(event.target.value) / 100 })
                }
                className="w-full"
              />
              <span className="text-xs text-muted-foreground">
                {Math.round((activeDraft.scaleZoom ?? 1) * 100)}%
              </span>
            </FieldRow>
          )}
        </div>
      )}

      {tab === "visibility" && (
        <div className="mt-4 space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={activeDraft.visible}
              onChange={(event) => patch({ visible: event.target.checked })}
            />
            Mostrar indicador en el gráfico
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={activeDraft.showLastValue === true}
              onChange={(event) =>
                patch({ showLastValue: event.target.checked })
              }
            />
            Etiqueta del último valor en la escala de precios
          </label>
          <p className="text-[11px] text-muted-foreground">
            Si ocultas el indicador, deja de dibujarse pero permanece en la
            lista bajo el precio para reactivarlo cuando quieras.
          </p>
        </div>
      )}

      <div className="mt-4 space-y-3 border-t border-border pt-3">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Gestión
        </p>
        <div className="flex flex-wrap gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={toggleHiddenNow}
          >
            {activeDraft.visible ? (
              <EyeOff className="mr-1.5 h-3.5 w-3.5" />
            ) : (
              <Eye className="mr-1.5 h-3.5 w-3.5" />
            )}
            {activeDraft.visible ? "Ocultar" : "Mostrar"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={saveAsPersonalPreset}
          >
            <Save className="mr-1.5 h-3.5 w-3.5" />
            Guardar como personal
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={duplicateNow}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            Duplicar
          </Button>
          {isSubPanel && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!canMoveUp}
                onClick={() => moveNow("up")}
              >
                <ChevronUp className="mr-1.5 h-3.5 w-3.5" />
                Subir
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!canMoveDown}
                onClick={() => moveNow("down")}
              >
                <ChevronDown className="mr-1.5 h-3.5 w-3.5" />
                Bajar
              </Button>
            </>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={deleteNow}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Eliminar
          </Button>
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={close}>
          Cancelar
        </Button>
        <Button type="button" onClick={apply}>
          Guardar
        </Button>
      </div>
    </Dialog>
  );
}
