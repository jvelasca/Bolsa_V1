import { Suspense, type ReactNode } from "react";

import { QueryClientProvider } from "@tanstack/react-query";

import {
  createBrowserRouter,
  Navigate,
  RouterProvider,
} from "react-router-dom";

import { installChartPerfAnalyzer } from "@/features/charts/chart-perf-analyzer";

import { PlatformShell } from "@/components/layout/platform-shell";

import { AuthGate } from "@/features/auth/auth-gate";

import { AppErrorBoundary } from "@/components/layout/app-error-boundary";

import { AutoWorkspaceLayout } from "@/components/layout/auto-workspace-layout";

import { ROUTE_PAGES } from "@/app-routes";

import { queryClient } from "@/lib/query-client";
import { useWorkspaceStore } from "@/stores/workspace-store";

const {
  AccountsPage,
  AlertsPage,
  AutoActividadPage,
  AutoAnalisisPage,
  AutoCarteraPage,
  AutoHomePage,
  AutoMonitorPage,
  AutoOperacionPage,
  AutoOperarPage,
  AutoRiesgoPage,
  AutoSistemaPage,
  ChartWorkspacePage,
  ConfirmPage,
  DecisionJournalPage,
  HistoryPage,
  InstrumentDetailPage,
  InstrumentsPage,
  MesaHoyPage,
  OperationalConsolePage,
  OperationsPage,
  OverviewPage,
  ResearchPage,
  ScreenersPage,
  SettingsRedirectPage,
  TaxReportPage,
} = ROUTE_PAGES;

function RouteFallback() {
  return (
    <div
      className="flex min-h-[40vh] flex-col items-center justify-center gap-2 text-sm text-muted-foreground"
      data-testid="route-fallback"
      aria-live="polite"
    >
      <span
        className="size-5 animate-spin rounded-full border-2 border-current border-t-transparent"
        aria-hidden="true"
      />
      Cargando página…
    </div>
  );
}

function SuspendedRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

function route(node: ReactNode) {
  return <SuspendedRoute>{node}</SuspendedRoute>;
}

/** BacktestsPage vive en PlatformShell (keep-alive Lista AUTO). */
function BacktestsRouteSlot() {
  return null;
}

installChartPerfAnalyzer(
  (listener) => useWorkspaceStore.subscribe(listener),
  queryClient,
);

const router = createBrowserRouter([
  {
    path: "/",

    element: (
      <AuthGate>
        <AppErrorBoundary>
          <PlatformShell />
        </AppErrorBoundary>
      </AuthGate>
    ),

    children: [
      { index: true, element: <Navigate to="/mesa" replace /> },

      { path: "mesa", element: route(<MesaHoyPage />) },

      { path: "trading", element: route(<ChartWorkspacePage />) },

      { path: "workspace", element: <Navigate to="/trading" replace /> },

      { path: "dashboard", element: <Navigate to="/overview" replace /> },

      { path: "overview", element: route(<OverviewPage />) },

      { path: "instruments", element: route(<InstrumentsPage />) },

      { path: "instruments/:id", element: route(<InstrumentDetailPage />) },

      { path: "portfolio", element: <Navigate to="/accounts" replace /> },

      { path: "backtests", element: <BacktestsRouteSlot /> },

      { path: "research", element: route(<ResearchPage />) },

      { path: "screeners", element: route(<ScreenersPage />) },

      { path: "alerts", element: route(<AlertsPage />) },

      { path: "accounts", element: route(<AccountsPage />) },

      {
        path: "operations",
        element: route(<OperationsPage />),
      },

      {
        path: "operational-console",
        element: route(<OperationalConsolePage />),
      },

      { path: "auto-monitor", element: route(<AutoMonitorPage />) },

      {
        path: "auto",
        element: <AutoWorkspaceLayout />,
        children: [
          { index: true, element: route(<AutoHomePage />) },
          { path: "operar", element: route(<AutoOperarPage />) },
          { path: "actividad", element: route(<AutoActividadPage />) },
          {
            path: "operar/operacion/:cycleId",
            element: route(<AutoOperacionPage />),
          },
          { path: "cartera", element: route(<AutoCarteraPage />) },
          { path: "riesgo", element: route(<AutoRiesgoPage />) },
          { path: "analisis", element: route(<AutoAnalisisPage />) },
          { path: "sistema", element: route(<AutoSistemaPage />) },
        ],
      },

      {
        path: "decision-board",
        element: <Navigate to="/mesa?view=decisiones" replace />,
      },

      { path: "hoy", element: <Navigate to="/mesa" replace /> },

      { path: "decision-journal", element: route(<DecisionJournalPage />) },

      { path: "confirm", element: route(<ConfirmPage />) },

      { path: "history", element: route(<HistoryPage />) },

      { path: "fiscal", element: route(<TaxReportPage />) },

      { path: "settings", element: route(<SettingsRedirectPage />) },
    ],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
