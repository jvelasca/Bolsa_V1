import { useEffect, useState } from "react";
import type { IndicatorPreset } from "@bolsa/shared";
import {
  colorForInstance,
  findIndicatorDefinition,
  normalizeParameters,
  presetDerivedHint,
} from "@bolsa/shared";
import { Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FieldRow, inputClassName } from "@/components/ui/dialog";
import { IndicatorParametersForm } from "@/features/charts/indicator-parameters-form";
import { useWorkspaceStore } from "@/stores/workspace-store";

interface IndicatorPresetEditorPanelProps {
  preset: IndicatorPreset;
  presets: IndicatorPreset[];
  onClose: () => void;
  onSaved?: () => void;
}

export function IndicatorPresetEditorPanel({
  preset,
  presets,
  onClose,
  onSaved,
}: IndicatorPresetEditorPanelProps) {
  const updatePreset = useWorkspaceStore((s) => s.updateIndicatorPreset);
  const removePreset = useWorkspaceStore((s) => s.removeIndicatorPreset);
  const save = useWorkspaceStore((s) => s.save);

  const definition = findIndicatorDefinition(preset.definitionId);
  const [name, setName] = useState(preset.name);
  const [parameters, setParameters] = useState({ ...preset.parameters });
  const [lineWidth, setLineWidth] = useState(preset.lineWidth ?? 2);
  const [showLastValue, setShowLastValue] = useState(
    preset.showLastValue === true,
  );

  useEffect(() => {
    setName(preset.name);
    setParameters({ ...preset.parameters });
    setLineWidth(preset.lineWidth ?? 2);
    setShowLastValue(preset.showLastValue === true);
  }, [preset]);

  if (!definition) return null;

  const previewInstance = {
    instanceId: "preview",
    presetId: preset.id,
    definitionId: preset.definitionId,
    parameters,
    visible: true,
    lineWidth,
    showLastValue,
  };
  const lineColor = colorForInstance(previewInstance);
  const derived = presetDerivedHint(preset, presets);

  function apply() {
    if (!definition) return;
    const normalized = normalizeParameters(definition, parameters);
    updatePreset(preset.id, {
      name: name.trim() || preset.name,
      parameters: normalized,
      lineWidth,
      showLastValue,
    });
    save();
    onSaved?.();
    onClose();
  }

  function handleDelete() {
    if (!window.confirm(`¿Eliminar el preset "${preset.name}" del catálogo?`))
      return;
    removePreset(preset.id);
    save();
    onClose();
  }

  return (
    <div className="mt-4 space-y-3 rounded-md border border-primary/30 bg-muted/30 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Editar preset personal</p>
          {derived && <p className="text-[11px] text-primary/80">{derived}</p>}
        </div>
        <button
          type="button"
          className="rounded p-1 hover:bg-accent"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <FieldRow label="Nombre">
        <input
          className={inputClassName}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </FieldRow>

      <IndicatorParametersForm
        definition={definition}
        values={parameters}
        onChange={setParameters}
      />

      <FieldRow label="Color de línea">
        <div className="flex items-center gap-2">
          <input
            type="color"
            className="h-9 w-12 cursor-pointer rounded border border-border bg-background"
            value={lineColor}
            onChange={(event) =>
              setParameters((prev) => ({ ...prev, color: event.target.value }))
            }
          />
          <span className="text-xs text-muted-foreground">{lineColor}</span>
        </div>
      </FieldRow>

      <FieldRow label="Grosor de línea">
        <select
          className={inputClassName}
          value={String(lineWidth)}
          onChange={(event) => setLineWidth(Number(event.target.value))}
        >
          {[1, 2, 3, 4].map((width) => (
            <option key={width} value={width}>
              {width}px
            </option>
          ))}
        </select>
      </FieldRow>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={showLastValue}
          onChange={(event) => setShowLastValue(event.target.checked)}
        />
        Etiqueta del último valor en escala
      </label>

      <div className="flex flex-wrap justify-between gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="text-destructive"
          onClick={handleDelete}
        >
          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
          Eliminar preset
        </Button>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="button" size="sm" onClick={apply}>
            Guardar preset
          </Button>
        </div>
      </div>
    </div>
  );
}
