import { useEffect, useState } from 'react';
import type { ChartToolbarGlobalConfig } from '@bolsa/shared';
import {
  CHART_TOOLBAR_GLOBAL_VISIBILITY_LABELS,
  normalizeChartToolbarGlobalConfig,
} from '@bolsa/shared';

import { Button } from '@/components/ui/button';
import { Dialog, FieldRow, checkboxClassName } from '@/components/ui/dialog';
import { ChartNewChartTemplatePinButton } from '@/features/charts/chart-new-chart-template-pin-button';
import { ColorField } from '@/features/charts/chart-toolbar-settings-fields';
import { useUiStore } from '@/stores/ui-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

/** Configuración exclusiva de la barra global del workspace. */
export function ChartGlobalBarSettingsDialog() {
  const open = useUiStore((s) => s.chartGlobalBarSettingsOpen);
  const close = useUiStore((s) => s.closeChartGlobalBarSettings);
  const globalRaw = useWorkspaceStore((s) => s.workspace.chartToolbarGlobal);
  const updateGlobal = useWorkspaceStore((s) => s.updateChartToolbarGlobal);
  const save = useWorkspaceStore((s) => s.save);

  const [draft, setDraft] = useState<ChartToolbarGlobalConfig>(() =>
    normalizeChartToolbarGlobalConfig(globalRaw),
  );

  useEffect(() => {
    if (!open) return;
    setDraft(normalizeChartToolbarGlobalConfig(globalRaw));
  }, [open, globalRaw]);

  function handleSave() {
    updateGlobal(draft);
    save();
    close();
  }

  function handleReset() {
    const defaults = normalizeChartToolbarGlobalConfig();
    setDraft((prev) => ({
      ...prev,
      visibility: defaults.visibility,
      appearance: {
        ...prev.appearance,
        globalBarBackground: defaults.appearance.globalBarBackground,
      },
    }));
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Barra del workspace"
      description="Indicadores, operaciones rápidas, scores FA/TA, estado de datos e inspector — solo esta barra superior."
      className="max-w-lg"
    >
      <section className="mb-4 space-y-2">
        <p className="text-xs font-medium text-foreground">Elementos visibles</p>
        <div className="grid grid-cols-2 gap-1.5">
          {(Object.keys(CHART_TOOLBAR_GLOBAL_VISIBILITY_LABELS) as Array<
            keyof typeof CHART_TOOLBAR_GLOBAL_VISIBILITY_LABELS
          >)
            .filter((key) => key !== 'settingsButton')
            .map((key) => (
              <label key={key} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  className={checkboxClassName}
                  checked={draft.visibility[key]}
                  onChange={() =>
                    setDraft((prev) => ({
                      ...prev,
                      visibility: { ...prev.visibility, [key]: !prev.visibility[key] },
                    }))
                  }
                />
                {CHART_TOOLBAR_GLOBAL_VISIBILITY_LABELS[key]}
              </label>
            ))}
        </div>
      </section>

      <section className="mb-4 space-y-2">
        <p className="text-xs font-medium text-foreground">Plantilla para gráficos nuevos</p>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          El icono de plantilla junto a Indicadores fija el gráfico activo como referencia. Los
          valores nuevos copiarán su configuración mientras esté activo; si no, usarán los defaults
          del workspace.
        </p>
        <ChartNewChartTemplatePinButton />
      </section>

      <FieldRow label="Fondo de la barra global">
        <ColorField
          value={draft.appearance.globalBarBackground}
          onChange={(globalBarBackground) =>
            setDraft((prev) => ({
              ...prev,
              appearance: { ...prev.appearance, globalBarBackground },
            }))
          }
        />
      </FieldRow>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={handleReset}>
          Restaurar valores
        </Button>
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
