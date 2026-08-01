/** Tipografía y altura unificadas de la barra por gráfico (Escala / Valor / Cursor). */
export const CHART_BAR_ZONE_ROW_CLASS =
  'flex h-[1.375rem] min-w-0 items-center gap-1.5';

/** Contenedor desplazable para chips de zona en paneles estrechos. */
export const CHART_BAR_ZONE_SCROLL_ROW_CLASS =
  'chart-bar-zone-chip-row chart-bar-zone-scroll flex min-w-0 flex-1 items-center gap-1.5';

/** Contenedor de chips en línea (sin scroll horizontal). */
export const CHART_BAR_ZONE_INLINE_ROW_CLASS =
  'chart-bar-zone-chip-row flex shrink-0 items-center gap-1.5';

export const CHART_BAR_ZONE_LABEL_CLASS =
  'shrink-0 text-[11px] font-bold leading-none text-foreground';

/** Botón con apariencia de etiqueta de zona (p. ej. Indicadores). */
export const CHART_BAR_ZONE_LABEL_BTN_CLASS =
  'shrink-0 rounded px-0.5 text-[11px] font-bold leading-none text-foreground transition-colors hover:bg-accent';

export const CHART_BAR_ZONE_CHIP_CLASS =
  'inline-flex h-[1.375rem] max-w-[11rem] items-center truncate rounded px-1.5 text-[11px] font-medium leading-none whitespace-nowrap';

export const CHART_BAR_ZONE_CHIP_MUTED = 'text-muted-foreground';

export const CHART_BAR_ZONE_CHIP_ANCHOR_CLASS =
  'inline-flex h-[1.375rem] min-w-[7rem] items-center justify-between gap-0.5 rounded border border-primary/30 bg-primary/10 px-1.5 text-[11px] font-medium leading-none tabular-nums text-primary hover:bg-primary/15';

/** Ancho fijo para valores OHLC en chips (3 decimales). */
export const CHART_BAR_ZONE_PRICE_VALUE_CLASS =
  'inline-block min-w-[5.75rem] text-right tabular-nums text-foreground';

/** Ancla del cursor con ancho fijo (precio C con 3 decimales). */
export const CHART_BAR_ZONE_CURSOR_ANCHOR_CLASS =
  'inline-flex h-[1.375rem] w-[8.75rem] min-w-[8.75rem] max-w-[8.75rem] items-center justify-between gap-0.5 rounded border border-primary/30 bg-primary/10 px-1.5 text-[11px] font-medium leading-none tabular-nums text-primary hover:bg-primary/15';

export const CHART_BAR_ZONE_VALUE_CLASS = 'tabular-nums text-foreground';

/** Layout compartido de barras workspace y gráfico activo. */
export const CHART_TOOLBAR_SECTION_DIVIDER = 'mx-1.5 w-0.5 shrink-0 self-stretch rounded-full bg-border';
export const CHART_TOOLBAR_ZONE_PAD = 'px-2 py-0.5';
export const CHART_TOOLBAR_ZONE_BLOCK =
  'chart-toolbar-zone flex min-w-0 max-w-full shrink items-center';
export const CHART_TOOLBAR_EMBEDDED_CLASS = 'border-0 rounded-none bg-transparent shadow-none';

/** Panel opaco compartido por menús emergentes (barra horizontal y vertical). */
export const CHART_ZONE_DROPDOWN_PANEL_CLASS =
  'rounded-lg border border-border bg-card text-foreground shadow-2xl ring-1 ring-black/20';
