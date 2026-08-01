import { useEffect, useState } from 'react';
import type {
  ChartDrawing,
  ChartDrawingPoint,
  ChartDrawingTemplate,
  ChartDrawingVertexPatch,
  ChartLineStyle,
  ChartDrawingPropertiesTab,
} from '@bolsa/shared';
import {
  CHART_DRAWING_TYPE_LABELS,
  DEFAULT_LINE_WIDTH,
  DEFAULT_RECT_FILL_OPACITY,
  DEFAULT_BRUSH_STROKE_OPACITY,
  drawingAlertPrice,
  drawingTypeForTool,
  stylePatchFromTemplate,
  templateMatchesDrawingType,
} from '@bolsa/shared';
import { cn } from '@/lib/utils';
import { formatCoordinatePrice, parseCoordinatePrice } from '@/features/charts/chart-utils';

const TABS: { id: ChartDrawingPropertiesTab; label: string }[] = [
  { id: 'style', label: 'Estilo' },
  { id: 'text', label: 'Texto' },
  { id: 'coordinates', label: 'Coordenadas' },
  { id: 'visibility', label: 'Visibilidad' },
];

function hasEndpoints(
  drawing: ChartDrawing,
): drawing is ChartDrawing & { p1: ChartDrawingPoint; p2: ChartDrawingPoint } {
  return 'p1' in drawing && 'p2' in drawing;
}

interface ChartDrawingPropertiesPanelProps {
  mode: 'instance' | 'template';
  drawing?: ChartDrawing;
  template?: ChartDrawingTemplate;
  templates?: ChartDrawingTemplate[];
  locked?: boolean;
  onUpdateDrawing?: (patch: ChartDrawingVertexPatch) => void;
  onUpdateTemplate?: (templateId: string, patch: Partial<ChartDrawingTemplate>) => void;
  onApplyTemplate?: (templateId: string) => void;
  className?: string;
  compact?: boolean;
  initialTab?: ChartDrawingPropertiesTab;
}

export function ChartDrawingPropertiesPanel({
  mode,
  drawing,
  template,
  templates = [],
  locked = false,
  onUpdateDrawing,
  onUpdateTemplate,
  onApplyTemplate,
  className,
  compact = false,
  initialTab = 'style',
}: ChartDrawingPropertiesPanelProps) {
  const [tab, setTab] = useState<ChartDrawingPropertiesTab>(initialTab);

  useEffect(() => {
    setTab(initialTab);
  }, [drawing?.id, initialTab]);

  const subject = mode === 'instance' ? drawing : template;
  if (!subject) return null;

  const isLocked = locked || (mode === 'instance' && drawing?.locked === true);
  const alertPrice = mode === 'instance' && drawing ? drawingAlertPrice(drawing) : null;

  const styleColor = mode === 'instance' ? drawing!.color : template!.style.color;
  const styleWidth =
    mode === 'instance' ? (drawing!.lineWidth ?? DEFAULT_LINE_WIDTH) : template!.style.lineWidth;
  const styleLineStyle =
    mode === 'instance' ? (drawing!.lineStyle ?? 'solid') : template!.style.lineStyle;
  const fillOpacity =
    mode === 'instance'
      ? drawing!.type === 'rectangle' || drawing!.type === 'channel'
        ? drawing!.fillOpacity
        : undefined
      : template!.style.fillOpacity;
  const strokeOpacity =
    mode === 'instance' && drawing!.type === 'brush-stroke' ? drawing!.strokeOpacity : undefined;

  const textNote = mode === 'instance' ? drawing!.text ?? '' : template!.text.text ?? '';
  const textLabel =
    mode === 'instance'
      ? drawing!.type === 'info-line' || drawing!.type === 'text-label' || hasEndpoints(drawing!)
        ? drawing!.label ?? ''
        : drawing!.label ?? ''
      : template!.text.label ?? '';

  const showChartLineLabel =
    mode === 'instance'
      ? hasEndpoints(drawing!) && drawing!.type !== 'text-label'
      : template!.drawingTypes.some((type) =>
          ['line', 'ray', 'ext-line', 'info-line', 'trend-angle', 'regression'].includes(type),
        ) || !template!.drawingTypes.length;

  const visible =
    mode === 'instance' ? drawing!.visible !== false : template!.visibility.visible;
  const isSubjectLocked =
    mode === 'instance' ? drawing!.locked === true : template!.visibility.locked;
  const alertOnCross =
    mode === 'instance' ? drawing!.alertOnCross === true : template!.visibility.alertOnCross;

  const patchDrawing = (patch: ChartDrawingVertexPatch) => {
    if (!drawing || !onUpdateDrawing) return;
    onUpdateDrawing(patch);
  };

  const patchTemplate = (patch: Partial<ChartDrawingTemplate>) => {
    if (!template || !onUpdateTemplate) return;
    onUpdateTemplate(template.id, patch);
  };

  const showFill =
    mode === 'instance'
      ? drawing!.type === 'rectangle' || drawing!.type === 'channel'
      : template!.drawingTypes.some((t) => t === 'rectangle' || t === 'channel') ||
        !template!.drawingTypes.length;

  const showLineStyle =
    mode === 'instance'
      ? drawing!.type !== 'rectangle' &&
        drawing!.type !== 'cross-marker' &&
        drawing!.type !== 'dot-marker' &&
        drawing!.type !== 'brush-stroke'
      : true;
  const isBrushStroke = mode === 'instance' && drawing?.type === 'brush-stroke';

  const sortedTemplates =
    mode === 'instance' && drawing
      ? [...templates].sort((a, b) => {
          const aPrimary = templateMatchesDrawingType(a, drawing.type) ? 0 : 1;
          const bPrimary = templateMatchesDrawingType(b, drawing.type) ? 0 : 1;
          if (aPrimary !== bPrimary) return aPrimary - bPrimary;
          return a.name.localeCompare(b.name, 'es');
        })
      : templates;

  return (
    <div className={cn('flex flex-col', className)}>
      <div className="mb-2 flex gap-0.5 border-b border-border">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cn(
              'flex-1 px-1 py-1.5 text-[10px] font-medium transition-colors',
              tab === item.id
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className={cn('space-y-2.5', compact ? 'text-xs' : 'text-sm')}>
        {tab === 'style' && (
          <>
            {mode === 'instance' && sortedTemplates.length > 0 && onApplyTemplate && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Plantilla</span>
                <select
                  className="rounded border border-border bg-background px-2 py-1"
                  value={drawing?.templateId ?? ''}
                  disabled={isLocked}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (!value) {
                      patchDrawing({ templateId: undefined });
                      return;
                    }
                    onApplyTemplate(value);
                  }}
                >
                  <option value="">— Sin plantilla —</option>
                  {sortedTemplates.map((t) => {
                    const recommended =
                      drawing && templateMatchesDrawingType(t, drawing.type);
                    return (
                      <option key={t.id} value={t.id}>
                        {recommended ? '★ ' : ''}
                        {t.name}
                      </option>
                    );
                  })}
                </select>
                <span className="text-[10px] text-muted-foreground">
                  ★ recomendada para este tipo · todas aplican estilo y visibilidad
                </span>
              </label>
            )}

            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">Color</span>
              <input
                type="color"
                className="h-8 w-full cursor-pointer rounded border border-border bg-background"
                value={styleColor}
                disabled={isLocked}
                onChange={(e) =>
                  mode === 'instance'
                    ? patchDrawing({ color: e.target.value, templateId: undefined })
                    : patchTemplate({ style: { ...template!.style, color: e.target.value } })
                }
              />
            </label>

            {mode === 'instance' && drawing?.type === 'text-label' && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Tamaño texto</span>
                <input
                  type="range"
                  min={8}
                  max={72}
                  value={drawing.fontSize ?? 12}
                  disabled={isLocked}
                  onChange={(e) =>
                    patchDrawing({ fontSize: Number(e.target.value), templateId: undefined })
                  }
                />
              </label>
            )}

            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">Grosor</span>
              <input
                type="range"
                min={isBrushStroke ? 1 : 1}
                max={isBrushStroke ? 24 : 4}
                step={isBrushStroke ? 1 : 0.5}
                value={styleWidth}
                disabled={isLocked}
                onChange={(e) =>
                  mode === 'instance'
                    ? patchDrawing({ lineWidth: Number(e.target.value), templateId: undefined })
                    : patchTemplate({
                        style: { ...template!.style, lineWidth: Number(e.target.value) },
                      })
                }
              />
            </label>

            {isBrushStroke && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Opacidad trazo</span>
                <input
                  type="range"
                  min={0.05}
                  max={1}
                  step={0.01}
                  value={strokeOpacity ?? DEFAULT_BRUSH_STROKE_OPACITY}
                  disabled={isLocked}
                  onChange={(e) =>
                    patchDrawing({
                      strokeOpacity: Number(e.target.value),
                      templateId: undefined,
                    })
                  }
                />
              </label>
            )}

            {showLineStyle && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Estilo de línea</span>
                <select
                  className="rounded border border-border bg-background px-2 py-1"
                  value={styleLineStyle}
                  disabled={isLocked}
                  onChange={(e) =>
                    mode === 'instance'
                      ? patchDrawing({
                          lineStyle: e.target.value as ChartLineStyle,
                          templateId: undefined,
                        })
                      : patchTemplate({
                          style: {
                            ...template!.style,
                            lineStyle: e.target.value as ChartLineStyle,
                          },
                        })
                  }
                >
                  <option value="solid">Sólida</option>
                  <option value="dashed">Discontinua</option>
                  <option value="dotted">Punteada</option>
                </select>
              </label>
            )}

            {showFill && (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Opacidad relleno</span>
                <input
                  type="range"
                  min={0.05}
                  max={0.5}
                  step={0.01}
                  value={fillOpacity ?? DEFAULT_RECT_FILL_OPACITY}
                  disabled={isLocked}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    if (mode === 'instance') {
                      patchDrawing({ fillOpacity: value, templateId: undefined });
                    } else {
                      patchTemplate({ style: { ...template!.style, fillOpacity: value } });
                    }
                  }}
                />
              </label>
            )}
          </>
        )}

        {tab === 'text' && (
          <>
            {mode === 'instance' && drawing?.type === 'text-label' ? (
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">Texto en gráfico</span>
                <textarea
                  rows={3}
                  className="resize-none rounded border border-border bg-background px-2 py-1"
                  value={drawing.label ?? drawing.text ?? ''}
                  disabled={isLocked}
                  placeholder="Escribe la nota visible en el gráfico"
                  onChange={(e) => {
                    const value = e.target.value;
                    patchDrawing({ label: value, text: value, templateId: undefined });
                  }}
                />
              </label>
            ) : (
              <>
                <label className="flex flex-col gap-1 text-xs">
                  <span className="text-muted-foreground">Nota / texto</span>
                  <textarea
                    rows={2}
                    className="resize-none rounded border border-border bg-background px-2 py-1"
                    value={textNote}
                    disabled={isLocked}
                    placeholder="Texto auxiliar del objeto"
                    onChange={(e) =>
                      mode === 'instance'
                        ? patchDrawing({ text: e.target.value || undefined, templateId: undefined })
                        : patchTemplate({
                            text: { ...template!.text, text: e.target.value || undefined },
                          })
                    }
                  />
                </label>

                {(showChartLineLabel ||
                  (mode === 'instance' ? drawing!.type === 'info-line' : false)) && (
                  <label className="flex flex-col gap-1 text-xs">
                    <span className="text-muted-foreground">Etiqueta en gráfico</span>
                    <input
                      type="text"
                      className="rounded border border-border bg-background px-2 py-1"
                      value={textLabel}
                      disabled={isLocked}
                      placeholder="Texto visible sobre la línea"
                      onChange={(e) =>
                        mode === 'instance'
                          ? patchDrawing({
                              label: e.target.value || undefined,
                              templateId: undefined,
                            })
                          : patchTemplate({ text: { ...template!.text, label: e.target.value } })
                      }
                    />
                  </label>
                )}
              </>
            )}
          </>
        )}

        {tab === 'coordinates' && (
          <>
            {mode === 'template' ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <p>Las coordenadas se definen al colocar el objeto en el gráfico.</p>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={template!.coordinates.showPriceLabels === true}
                    onChange={(e) =>
                      patchTemplate({
                        coordinates: {
                          ...template!.coordinates,
                          showPriceLabels: e.target.checked,
                        },
                      })
                    }
                  />
                  Mostrar etiquetas de precio
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={template!.coordinates.showTimeLabels === true}
                    onChange={(e) =>
                      patchTemplate({
                        coordinates: {
                          ...template!.coordinates,
                          showTimeLabels: e.target.checked,
                        },
                      })
                    }
                  />
                  Mostrar etiquetas de tiempo
                </label>
              </div>
            ) : (
              drawing && (
                <div className="space-y-2 text-xs">
                  {hasEndpoints(drawing) && (
                    <>
                      <CoordField
                        label="P1 tiempo"
                        value={drawing.p1.time}
                        disabled={isLocked}
                        onChange={(time) => patchDrawing({ p1: { ...drawing.p1, time } })}
                      />
                      <CoordField
                        label="P1 precio"
                        value={formatCoordinatePrice(drawing.p1.price)}
                        disabled={isLocked}
                        numeric
                        onChange={(v) =>
                          patchDrawing({ p1: { ...drawing.p1, price: parseCoordinatePrice(v) } })
                        }
                      />
                      <CoordField
                        label="P2 tiempo"
                        value={drawing.p2.time}
                        disabled={isLocked}
                        onChange={(time) => patchDrawing({ p2: { ...drawing.p2, time } })}
                      />
                      <CoordField
                        label="P2 precio"
                        value={formatCoordinatePrice(drawing.p2.price)}
                        disabled={isLocked}
                        numeric
                        onChange={(v) =>
                          patchDrawing({ p2: { ...drawing.p2, price: parseCoordinatePrice(v) } })
                        }
                      />
                      {(drawing.type === 'channel' || drawing.type === 'pitchfork') &&
                        drawing.p3 && (
                        <>
                          <CoordField
                            label="P3 tiempo"
                            value={drawing.p3.time}
                            disabled={isLocked}
                            onChange={(time) =>
                              patchDrawing({ p3: { ...drawing.p3!, time } })
                            }
                          />
                          <CoordField
                            label="P3 precio"
                            value={formatCoordinatePrice(drawing.p3.price)}
                            disabled={isLocked}
                            numeric
                            onChange={(v) =>
                              patchDrawing({
                                p3: { ...drawing.p3!, price: parseCoordinatePrice(v) },
                              })
                            }
                          />
                        </>
                      )}
                    </>
                  )}

                  {drawing.type === 'hline' && (
                    <CoordField
                      label="Precio"
                      value={formatCoordinatePrice(drawing.price)}
                      disabled={isLocked}
                      numeric
                      onChange={(v) => patchDrawing({ price: parseCoordinatePrice(v) })}
                    />
                  )}

                  {drawing.type === 'vline' && (
                    <CoordField
                      label="Tiempo"
                      value={drawing.time}
                      disabled={isLocked}
                      onChange={(time) => patchDrawing({ time })}
                    />
                  )}

                  {(drawing.type === 'hray' ||
                    drawing.type === 'cross-marker' ||
                    drawing.type === 'dot-marker' ||
                    drawing.type === 'dot-halo-marker' ||
                    drawing.type === 'arrow-marker' ||
                    drawing.type === 'arrow-circle-marker' ||
                    drawing.type === 'text-label') && (
                    <>
                      <CoordField
                        label="Tiempo"
                        value={drawing.point.time}
                        disabled={isLocked}
                        onChange={(time) =>
                          patchDrawing({ point: { ...drawing.point, time } })
                        }
                      />
                      <CoordField
                        label="Precio"
                        value={formatCoordinatePrice(drawing.point.price)}
                        disabled={isLocked}
                        numeric
                        onChange={(v) =>
                          patchDrawing({
                            point: { ...drawing.point, price: parseCoordinatePrice(v) },
                          })
                        }
                      />
                    </>
                  )}

                  {!hasEndpoints(drawing) &&
                    drawing.type !== 'hline' &&
                    drawing.type !== 'vline' &&
                    drawing.type !== 'hray' &&
                    drawing.type !== 'cross-marker' &&
                    drawing.type !== 'dot-marker' &&
                    drawing.type !== 'dot-halo-marker' &&
                    drawing.type !== 'arrow-marker' &&
                    drawing.type !== 'arrow-circle-marker' &&
                    drawing.type !== 'text-label' && (
                      <p className="text-muted-foreground">Sin coordenadas editables.</p>
                    )}
                </div>
              )
            )}
          </>
        )}

        {tab === 'visibility' && (
          <>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={visible}
                onChange={(e) =>
                  mode === 'instance'
                    ? patchDrawing({ visible: e.target.checked, templateId: undefined })
                    : patchTemplate({
                        visibility: { ...template!.visibility, visible: e.target.checked },
                      })
                }
              />
              Visible en gráfico
            </label>

            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={isSubjectLocked}
                onChange={(e) =>
                  mode === 'instance'
                    ? patchDrawing({ locked: e.target.checked })
                    : patchTemplate({
                        visibility: { ...template!.visibility, locked: e.target.checked },
                      })
                }
              />
              Bloqueado
            </label>

            {(alertPrice != null || mode === 'template') && (
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={alertOnCross}
                  onChange={(e) =>
                    mode === 'instance'
                      ? patchDrawing({ alertOnCross: e.target.checked, templateId: undefined })
                      : patchTemplate({
                          visibility: {
                            ...template!.visibility,
                            alertOnCross: e.target.checked,
                          },
                        })
                  }
                />
                Alerta al cruzar
                {alertPrice != null && ` (${formatCoordinatePrice(alertPrice)})`}
              </label>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function CoordField({
  label,
  value,
  disabled,
  numeric,
  onChange,
}: {
  label: string;
  value: string;
  disabled?: boolean;
  numeric?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-muted-foreground">{label}</span>
      <input
        type={numeric ? 'number' : 'text'}
        step={numeric ? 0.0001 : undefined}
        className="rounded border border-border bg-background px-2 py-1 tabular-nums"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function drawingTypeTitle(drawing: ChartDrawing): string {
  return CHART_DRAWING_TYPE_LABELS[drawing.type] ?? drawing.type;
}

export { stylePatchFromTemplate, drawingTypeForTool };
