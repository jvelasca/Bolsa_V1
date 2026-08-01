import { Outlet, useLocation } from 'react-router-dom';

import { TradingLayout } from '@/components/layout/trading-layout';

import { AppTopBar } from '@/components/layout/app-top-bar';

import { VisualizationLogDialog } from '@/features/trading/lists-tab/visualization-log-dialog';

import { ChartDataBarSettingsDialog } from '@/features/charts/chart-data-bar-settings-dialog';
import { ChartGlobalBarSettingsDialog } from '@/features/charts/chart-global-bar-settings-dialog';
import { IndicatorsCatalogDialog } from '@/features/charts/indicators-catalog-dialog';

import { AlertsMonitor } from '@/features/alerts/alerts-monitor';
import { DrawingAlertsMonitor } from '@/features/charts/use-drawing-alerts-monitor';

import { AlertToasts } from '@/features/alerts/alert-toasts';

import { InstrumentSyncDialog } from '@/features/instruments/instrument-sync-dialog';

import { PendingOrdersMonitor } from '@/features/trading/pending-orders-monitor';
import { TrackerAlarmInboxPoller } from '@/features/trading/tracker-alarm-inbox-poller';

import { InstrumentInfoDialog } from '@/features/trading/instrument-info-dialog';
import { OrderDialog } from '@/features/trading/order-dialog';

import { TradingStatusBar } from '@/features/trading/trading-status-bar';

import { WorkspaceAutoSave } from '@/features/workspace/workspace-auto-save';
import { WorkspaceBootstrap } from '@/features/workspace/workspace-bootstrap';
import { WorkspaceUiBridgeRegister } from '@/features/workspace/workspace-ui-bridge-register';
import { WorkspaceRemoteSync } from '@/features/workspace/workspace-remote-sync';
import { VisualizationWorkspaceSync } from '@/features/workspace/visualization-workspace-sync';
import { WorkspacePickerDialog } from '@/features/workspace/workspace-picker-dialog';

import { PlatformConfigDialog } from '@/features/config/platform-config-dialog';
import { CreateAccountWizardDialog } from '@/features/accounts/create-account-wizard-dialog';

import { BacktestsPage } from '@/features/backtests/backtests-page';

import { CoreRSchedulerHost } from '@/features/backtests/core-r-scheduler-host';
import { isFillHubRoute, isTradingRoute } from '@/lib/routes';
import { useListAutoActivityStore } from '@/stores/list-auto-activity-store';
import { useUiStore } from '@/stores/ui-store';
import { cn } from '@/lib/utils';

export function PlatformShell() {
  const { pathname } = useLocation();

  const trading = isTradingRoute(pathname);
  const fillHub = isFillHubRoute(pathname);
  const onBacktests = pathname.startsWith('/backtests');
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const mountBacktests = onBacktests || listAutoActive;

  const indicatorsCatalogOpen = useUiStore((s) => s.indicatorsCatalogOpen);
  const closeIndicatorsCatalog = useUiStore((s) => s.closeIndicatorsCatalog);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <AppTopBar />
      <WorkspaceBootstrap />
      <WorkspaceUiBridgeRegister />
      <WorkspaceAutoSave />
      <VisualizationWorkspaceSync />
      <WorkspaceRemoteSync />
      <CoreRSchedulerHost />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {trading ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <TradingLayout>
              <Outlet />
            </TradingLayout>
            <TradingStatusBar />
          </div>
        ) : !onBacktests ? (
          <main
            className={cn(
              'min-h-0 flex-1 p-3 md:p-4',
              fillHub ? 'flex flex-col overflow-hidden' : 'overflow-auto md:p-6',
            )}
          >
            <Outlet />
          </main>
        ) : null}

        {/*
          Keep-alive Lista AUTO: misma instancia de BacktestsPage al salir a Trading/otros hubs.
          Visible solo en /backtests; si la campaña sigue, queda montada fuera de flujo.
        */}
        {mountBacktests ? (
          <main
            className={cn(
              onBacktests
                ? 'flex min-h-0 flex-1 flex-col overflow-hidden p-3 md:p-4'
                : 'pointer-events-none fixed left-0 top-0 h-px w-px overflow-hidden opacity-0',
            )}
            aria-hidden={!onBacktests}
            data-testid="backtests-keepalive-host"
            data-list-auto-keepalive={listAutoActive && !onBacktests ? '1' : '0'}
          >
            <BacktestsPage />
          </main>
        ) : null}
      </div>

      <ChartGlobalBarSettingsDialog />
      <ChartDataBarSettingsDialog />
      <IndicatorsCatalogDialog open={indicatorsCatalogOpen} onClose={closeIndicatorsCatalog} />

      <WorkspacePickerDialog />

      <PlatformConfigDialog />

      <CreateAccountWizardDialog />

      <VisualizationLogDialog />

      <OrderDialog />

      <InstrumentInfoDialog />

      <InstrumentSyncDialog />

      <AlertsMonitor />
      <DrawingAlertsMonitor />
      <TrackerAlarmInboxPoller />
      <PendingOrdersMonitor />

      <AlertToasts />
    </div>
  );
}
