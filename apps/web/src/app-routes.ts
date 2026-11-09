import { lazy, type ComponentType, type LazyExoticComponent } from "react";

/**
 * Páginas de ruta cargadas bajo demanda (Fase 3.1, auditoría externa).
 *
 * Cada entrada es un ``import()`` literal para que Vite pueda analizarlo y emitir un
 * chunk por página. ``ROUTE_PAGES`` se deriva de este mapa: una sola fuente de verdad
 * entre el loader y el componente, y el test ``app-routes.test.ts`` comprueba que cada
 * módulo exporta de verdad el componente con ese nombre.
 *
 * El shell (``PlatformShell``), el layout de AUTO y el keep-alive de backtests NO están
 * aquí: son el marco y se mantienen eager.
 */
export const ROUTE_PAGE_LOADERS = {
  ChartWorkspacePage: () => import("@/features/charts/chart-workspace-page"),
  OverviewPage: () => import("@/features/dashboard/dashboard-page"),
  InstrumentDetailPage: () =>
    import("@/features/instruments/instrument-detail-page"),
  InstrumentsPage: () => import("@/features/instruments/instruments-page"),
  ResearchPage: () => import("@/features/research/research-page"),
  ScreenersPage: () => import("@/features/screeners/screeners-page"),
  AccountsPage: () => import("@/features/accounts/accounts-page"),
  HistoryPage: () => import("@/features/history/history-page"),
  TaxReportPage: () => import("@/features/fiscal/tax-report-page"),
  OperationalConsolePage: () =>
    import("@/features/operational-console/operational-console-page"),
  OperationsPage: () => import("@/features/operations/operations-page"),
  AutoMonitorPage: () => import("@/features/auto-monitor/auto-monitor-page"),
  AutoHomePage: () => import("@/features/auto/auto-home-page"),
  AutoOperarPage: () => import("@/features/auto/auto-operar-page"),
  AutoActividadPage: () => import("@/features/auto/auto-actividad-page"),
  AutoOperacionPage: () => import("@/features/auto/auto-operacion-page"),
  AutoCarteraPage: () => import("@/features/auto/auto-cartera-page"),
  AutoRiesgoPage: () => import("@/features/auto/auto-riesgo-page"),
  AutoAnalisisPage: () => import("@/features/auto/auto-analisis-page"),
  AutoSistemaPage: () => import("@/features/auto/auto-sistema-page"),
  DecisionJournalPage: () =>
    import("@/features/decision-journal/decision-journal-page"),
  MesaHoyPage: () => import("@/features/mesa/mesa-hoy-page"),
  ConfirmPage: () => import("@/features/confirm/confirm-page"),
  AlertsPage: () => import("@/features/alerts/alerts-page"),
  SettingsRedirectPage: () =>
    import("@/features/settings/settings-redirect-page"),
} as const;

export type RoutePageName = keyof typeof ROUTE_PAGE_LOADERS;

type NamedExportModule = Record<string, unknown>;

function lazyNamed(name: RoutePageName): LazyExoticComponent<ComponentType> {
  return lazy(async () => {
    const module = (await ROUTE_PAGE_LOADERS[name]()) as NamedExportModule;
    const exported = module[name];
    if (typeof exported !== "function" && typeof exported !== "object") {
      throw new TypeError(
        `El módulo de la ruta ${name} no exporta un componente con ese nombre`,
      );
    }
    return { default: exported as ComponentType };
  });
}

export const ROUTE_PAGES = Object.fromEntries(
  (Object.keys(ROUTE_PAGE_LOADERS) as RoutePageName[]).map((name) => [
    name,
    lazyNamed(name),
  ]),
) as Record<RoutePageName, LazyExoticComponent<ComponentType>>;
