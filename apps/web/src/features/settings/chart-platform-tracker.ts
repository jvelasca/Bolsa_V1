import { HELP_CONTENT_AS_OF } from '@/features/help/help-content-as-of';

export type ChartTrackStatus = 'done' | 'partial' | 'planned';

export interface ChartTrackItem {
  id: string;
  title: string;
  status: ChartTrackStatus;
  detail: string;
}

export const CHART_TRACKER_SYNC = {
  asOf: HELP_CONTENT_AS_OF,
  adr: 'docs/adr/006-chart-platform-and-settings.md',
  chartDataBar: 'docs/CHART_DATA_BAR.md',
} as const;

export const CHART_STATUS_LABEL: Record<ChartTrackStatus, string> = {
  done: 'Hecho',
  partial: 'Parcial',
  planned: 'Pendiente',
};

export const CHART_CAPABILITIES: ChartTrackItem[] = [
  {
    id: 'adaptive-chart',
    title: 'Gráfico adaptativo (velas + volumen)',
    status: 'done',
    detail: 'Se ajusta al panel; propiedades por pestaña (grid, colores, cursor).',
  },
  {
    id: 'timeframes-zoom',
    title: 'Timeframes, zoom y sync de ejes',
    status: 'done',
    detail:
      'Selector por pestaña, zoom ± / ajustar ventana, API OHLCV. Sync: rango temporal + crosshair entre paneles; rueda anclada al cursor.',
  },
  {
    id: 'indicators-catalog',
    title: 'Catálogo e instancias de indicadores',
    status: 'done',
    detail:
      'Catálogo unificado IND-* + UI. Oleadas 1–3: XTB core + OBV/MFI/Aroon/ROC/Ichimoku/PSAR/Elder/Alligator/Fractals (Py+TS+Feature Registry).',
  },
  {
    id: 'drawings',
    title: 'Objetos gráficos y plantillas',
    status: 'done',
    detail:
      'Líneas, rayos, horizontales, fibo, canal, formas, inspector (color, grosor, bloqueo) y plantillas de estilo. Algunos tipos raros siguen desactivados en la barra.',
  },
  {
    id: 'tab-uniqueness',
    title: 'Una pestaña por instrumento',
    status: 'done',
    detail:
      'openChartTab / focusInstrumentFromList reutilizan la pestaña existente. normalizeWorkspace deduplica legacy. No se clonan pestañas del mismo valor (evita sync OHLCV a medias). Docs: WORKSPACE_PERSISTENCE §2b.',
  },
  {
    id: 'drawing-alerts',
    title: 'Alertas al cruzar un dibujo',
    status: 'partial',
    detail:
      'Monitor en cliente con alertOnCross. Falta acción «crear orden» desde el gráfico y evaluación formal en servidor para backtest.',
  },
  {
    id: 'ai-indicators',
    title: 'Indicadores con asistencia IA',
    status: 'partial',
    detail:
      'Borrador desde prompt en el catálogo (governance LLM). Pendiente: DSL/Pine completo y sandbox de scripts de usuario.',
  },
  {
    id: 'chart-orders',
    title: 'Órdenes / reglas programables en gráfico',
    status: 'planned',
    detail:
      'Triggers gráfico → orden mercado/pendiente (estilo ProRealTime). No bloquea uso diario de Trading.',
  },
];
