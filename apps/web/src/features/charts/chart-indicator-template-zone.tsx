import {
  templateHasIndicators,
  type IndicatorTemplate,
} from '@bolsa/shared';
import { LayoutTemplate } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { ChartBarZonePicker } from '@/features/charts/chart-bar-zone-picker';
import { ChartBarZoneIconAnchor } from '@/features/charts/chart-bar-zone-rail-button';
import { CHART_BAR_ZONE_ROW_CLASS } from '@/features/charts/chart-bar-zone-styles';
import { useChartIndicatorTemplateFavorites } from '@/features/charts/use-chart-indicator-template-favorites';
import { cn } from '@/lib/utils';

function templateShortLabel(name: string): string {
  const trimmed = name.trim();
  if (trimmed.length <= 10) return trimmed;
  return `${trimmed.slice(0, 9)}…`;
}

function buildTemplateMenuGroups(templates: IndicatorTemplate[]): string[][] {
  const builtin = templates
    .filter((template) => template.source === 'builtin' || template.locked)
    .map((template) => template.id);
  const custom = templates
    .filter((template) => !builtin.includes(template.id) && template.source === 'custom')
    .map((template) => template.id);
  const other = templates
    .filter((template) => !builtin.includes(template.id) && !custom.includes(template.id))
    .map((template) => template.id);
  return [builtin, custom, other].filter((group) => group.length > 0);
}

export function ChartIndicatorTemplateZone({
  templates,
  activeTemplateId,
  onApplyTemplate,
  className,
}: {
  templates: IndicatorTemplate[];
  activeTemplateId?: string | null;
  onApplyTemplate: (templateId: string) => boolean;
  className?: string;
}) {
  const [emptyHint, setEmptyHint] = useState<string | null>(null);
  const hintTimerRef = useRef<number | null>(null);
  const { favorites, toggleFavorite, isFavorite } = useChartIndicatorTemplateFavorites();

  const templateById = useMemo(
    () => new Map(templates.map((template) => [template.id, template])),
    [templates],
  );

  const menuGroups = useMemo(() => buildTemplateMenuGroups(templates), [templates]);
  const fallbackActiveId =
    templates.find((template) => templateHasIndicators(template))?.id ?? templates[0]?.id ?? '';
  const activeId = activeTemplateId ?? fallbackActiveId;

  const options = useMemo(
    () =>
      Object.fromEntries(
        templates.map((template) => {
          const empty = !templateHasIndicators(template);
          return [
            template.id,
            {
              id: template.id,
              label: empty ? `${template.name} (vacío)` : template.name,
              hint: empty
                ? `${template.name} (vacío — añade indicadores en el catálogo)`
                : `Aplicar plantilla ${template.name}`,
            },
          ];
        }),
      ),
    [templates],
  );

  function showEmptyHint(template: IndicatorTemplate) {
    setEmptyHint(`"${template.name}" no tiene indicadores`);
    if (hintTimerRef.current) window.clearTimeout(hintTimerRef.current);
    hintTimerRef.current = window.setTimeout(() => setEmptyHint(null), 2600);
  }

  function tryApply(templateId: string): boolean {
    const template = templateById.get(templateId);
    if (!template) return false;
    if (!templateHasIndicators(template)) {
      showEmptyHint(template);
      return false;
    }
    return onApplyTemplate(templateId);
  }

  useEffect(() => {
    return () => {
      if (hintTimerRef.current) window.clearTimeout(hintTimerRef.current);
    };
  }, []);

  if (templates.length === 0 || !activeId) {
    return (
      <div className={cn(CHART_BAR_ZONE_ROW_CLASS, className)} title="Plantillas de indicadores">
        <ChartBarZoneIconAnchor
          icon={LayoutTemplate}
          title="Plantillas"
          hint="Plantillas de indicadores (grupos)"
          showMenu={false}
          onOpenMenu={() => {}}
        />
      </div>
    );
  }

  return (
    <ChartBarZonePicker
      zoneIcon={LayoutTemplate}
      zoneTitle="Plantillas"
      zoneHint="Plantillas de indicadores. Icono muestra la plantilla activa; estrella = chip opcional."
      activeId={activeId}
      favorites={favorites}
      menuGroups={menuGroups}
      options={options}
      isFavorite={isFavorite}
      onToggleFavorite={toggleFavorite}
      onSelectOption={tryApply}
      getButtonLabel={(id) => templateShortLabel(templateById.get(id)?.name ?? '—')}
      isButtonVisible={(id) => Boolean(templateById.get(id))}
      trailing={
        emptyHint ? (
          <span className="ml-1 shrink-0 text-[10px] text-amber-600 dark:text-amber-400" role="status">
            {emptyHint}
          </span>
        ) : undefined
      }
      className={className}
    />
  );
}
