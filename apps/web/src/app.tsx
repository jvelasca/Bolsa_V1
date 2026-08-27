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

import { ChartWorkspacePage } from "@/features/charts/chart-workspace-page";

import { OverviewPage } from "@/features/dashboard/dashboard-page";

import { InstrumentDetailPage } from "@/features/instruments/instrument-detail-page";

import { InstrumentsPage } from "@/features/instruments/instruments-page";

import { ResearchPage } from "@/features/research/research-page";
/** BacktestsPage vive en PlatformShell (keep-alive Lista AUTO). */
function BacktestsRouteSlot() {
  return null;
}
import { ScreenersPage } from "@/features/screeners/screeners-page";
import { AccountsPage } from "@/features/accounts/accounts-page";
import { HistoryPage } from "@/features/history/history-page";
import { TaxReportPage } from "@/features/fiscal/tax-report-page";
import { OperationalConsolePage } from "@/features/operational-console/operational-console-page";
import { DecisionJournalPage } from "@/features/decision-journal/decision-journal-page";
import { MesaHoyPage } from "@/features/mesa/mesa-hoy-page";
import { ConfirmPage } from "@/features/confirm/confirm-page";
import { AlertsPage } from "@/features/alerts/alerts-page";
import { SettingsRedirectPage } from "@/features/settings/settings-redirect-page";

import { queryClient } from "@/lib/query-client";
import { useWorkspaceStore } from "@/stores/workspace-store";

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

      { path: "mesa", element: <MesaHoyPage /> },

      { path: "trading", element: <ChartWorkspacePage /> },

      { path: "workspace", element: <Navigate to="/trading" replace /> },

      { path: "dashboard", element: <Navigate to="/overview" replace /> },

      { path: "overview", element: <OverviewPage /> },

      { path: "instruments", element: <InstrumentsPage /> },

      { path: "instruments/:id", element: <InstrumentDetailPage /> },

      { path: "portfolio", element: <Navigate to="/accounts" replace /> },

      { path: "backtests", element: <BacktestsRouteSlot /> },

      { path: "research", element: <ResearchPage /> },

      { path: "screeners", element: <ScreenersPage /> },

      { path: "alerts", element: <AlertsPage /> },

      { path: "accounts", element: <AccountsPage /> },

      {
        path: "operations",
        element: <Navigate to="/mesa?view=posiciones" replace />,
      },

      { path: "operational-console", element: <OperationalConsolePage /> },

      {
        path: "decision-board",
        element: <Navigate to="/mesa?view=decisiones" replace />,
      },

      { path: "hoy", element: <Navigate to="/mesa" replace /> },

      { path: "decision-journal", element: <DecisionJournalPage /> },

      { path: "confirm", element: <ConfirmPage /> },

      { path: "history", element: <HistoryPage /> },

      { path: "fiscal", element: <TaxReportPage /> },

      { path: "settings", element: <SettingsRedirectPage /> },
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
