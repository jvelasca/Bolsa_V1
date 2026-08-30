import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { TradingLayout } from "@/components/layout/trading-layout";

import { AppTopBar } from "@/components/layout/app-top-bar";
import { AdminRail } from "@/components/layout/admin-rail";

import { VisualizationLogDialog } from "@/features/trading/lists-tab/visualization-log-dialog";

import { ChartDataBarSettingsDialog } from "@/features/charts/chart-data-bar-settings-dialog";
import { ChartGlobalBarSettingsDialog } from "@/features/charts/chart-global-bar-settings-dialog";
import { IndicatorsCatalogDialog } from "@/features/charts/indicators-catalog-dialog";

import { AlertsMonitor } from "@/features/alerts/alerts-monitor";
import { DrawingAlertsMonitor } from "@/features/charts/use-drawing-alerts-monitor";

import { AlertToasts } from "@/features/alerts/alert-toasts";

import { InstrumentSyncDialog } from "@/features/instruments/instrument-sync-dialog";

import { PendingOrdersMonitor } from "@/features/trading/pending-orders-monitor";
import { TrackerAlarmInboxPoller } from "@/features/trading/tracker-alarm-inbox-poller";
import { EstudioOpinionAlarmPoller } from "@/features/research/estudio-opinion-alarm-poller";
import { OperativaPhaseToastPoller } from "@/features/trading/operativa-phase-toast-poller";

import { InstrumentInfoDialog } from "@/features/trading/instrument-info-dialog";
import { OrderDialog } from "@/features/trading/order-dialog";

import { TradingStatusBar } from "@/features/trading/trading-status-bar";

import { WorkspaceAutoSave } from "@/features/workspace/workspace-auto-save";
import { WorkspaceBootstrap } from "@/features/workspace/workspace-bootstrap";
import { WorkspaceUiBridgeRegister } from "@/features/workspace/workspace-ui-bridge-register";
import { WorkspaceRemoteSync } from "@/features/workspace/workspace-remote-sync";
import { VisualizationWorkspaceSync } from "@/features/workspace/visualization-workspace-sync";
import { EstudioApiSync } from "@/features/trading/estudio-api-sync";
import {
  ESTUDIO_SUPERVISION_EVENT,
  loadEstudioSupervisionPrefs,
} from "@/features/trading/estudio-supervision";
import { EstudioSupervisionHost } from "@/features/trading/estudio-supervision-host";
import { wireEstudioProcessRunningEvents } from "@/stores/estudio-process-running-store";
import { WorkspacePickerDialog } from "@/features/workspace/workspace-picker-dialog";

import { PlatformConfigDialog } from "@/features/config/platform-config-dialog";
import { CommandPaletteHost } from "@/features/command-palette/command-palette-host";
import { CreateAccountWizardDialog } from "@/features/accounts/create-account-wizard-dialog";

import { BacktestsPage } from "@/features/backtests/backtests-page";

import { CoreRSchedulerHost } from "@/features/backtests/core-r-scheduler-host";
import { SupervisedF3QueueHost } from "@/features/trading/supervised-f3-queue-host";
import { ConfirmDrawerHost } from "@/features/confirm/confirm-drawer-host";
import {
  BOLSA_NAVIGATE_EVENT,
  CONFIRM_PATH,
  isConfirmNavigateTarget,
} from "@/features/confirm/confirm-nav";
import { isFillHubRoute, isTradingRoute } from "@/lib/routes";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import { useUiStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";

function useEstudioSupervisionArmed(): boolean {
  const [armed, setArmed] = useState(
    () => loadEstudioSupervisionPrefs().enabled,
  );
  useEffect(() => {
    const sync = () => setArmed(loadEstudioSupervisionPrefs().enabled);
    sync();
    window.addEventListener(ESTUDIO_SUPERVISION_EVENT, sync);
    return () => window.removeEventListener(ESTUDIO_SUPERVISION_EVENT, sync);
  }, []);
  return armed;
}

function EstudioProcessRunningWire() {
  useEffect(() => wireEstudioProcessRunningEvents(), []);
  return null;
}

export function PlatformShell() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const onNavigate = (event: Event) => {
      const to = (event as CustomEvent<{ to?: unknown }>).detail?.to;
      if (!isConfirmNavigateTarget(to)) return;
      navigate(CONFIRM_PATH);
    };
    window.addEventListener(BOLSA_NAVIGATE_EVENT, onNavigate);
    return () => window.removeEventListener(BOLSA_NAVIGATE_EVENT, onNavigate);
  }, [navigate]);

  const trading = isTradingRoute(pathname);
  const fillHub = isFillHubRoute(pathname);
  const onBacktests = pathname.startsWith("/backtests");
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const supervisionArmed = useEstudioSupervisionArmed();
  // Supervisión ON mantiene Lab montado para ticks de frescura / rediscubrimiento.
  const mountBacktests = onBacktests || listAutoActive || supervisionArmed;

  const indicatorsCatalogOpen = useUiStore((s) => s.indicatorsCatalogOpen);
  const closeIndicatorsCatalog = useUiStore((s) => s.closeIndicatorsCatalog);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <AdminRail />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <AppTopBar />
          <WorkspaceBootstrap />
          <WorkspaceUiBridgeRegister />
          <WorkspaceAutoSave />
          <VisualizationWorkspaceSync />
          <EstudioApiSync />
          <WorkspaceRemoteSync />
          <CoreRSchedulerHost />
          <EstudioSupervisionHost />
          <EstudioProcessRunningWire />
          <SupervisedF3QueueHost />

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
                  "min-h-0 flex-1 p-[var(--density-pad)] md:p-[var(--density-pad-md)]",
                  fillHub
                    ? "flex flex-col overflow-hidden"
                    : "overflow-auto md:p-[var(--density-pad-lg)]",
                )}
              >
                <Outlet />
              </main>
            ) : null}

            {mountBacktests ? (
              <main
                className={cn(
                  onBacktests
                    ? "flex min-h-0 flex-1 flex-col overflow-hidden p-[var(--density-pad)] md:p-[var(--density-pad-md)]"
                    : "pointer-events-none fixed left-0 top-0 h-px w-px overflow-hidden opacity-0",
                )}
                aria-hidden={!onBacktests}
                data-testid="backtests-keepalive-host"
                data-list-auto-keepalive={
                  listAutoActive && !onBacktests ? "1" : "0"
                }
              >
                <BacktestsPage />
              </main>
            ) : null}
          </div>
        </div>
      </div>

      <ChartGlobalBarSettingsDialog />
      <ChartDataBarSettingsDialog />
      <IndicatorsCatalogDialog
        open={indicatorsCatalogOpen}
        onClose={closeIndicatorsCatalog}
      />

      <WorkspacePickerDialog />

      <PlatformConfigDialog />

      <CommandPaletteHost />

      <CreateAccountWizardDialog />

      <VisualizationLogDialog />

      <OrderDialog />

      <ConfirmDrawerHost />

      <InstrumentInfoDialog />

      <InstrumentSyncDialog />

      <AlertsMonitor />
      <DrawingAlertsMonitor />
      <TrackerAlarmInboxPoller />
      <EstudioOpinionAlarmPoller />
      <OperativaPhaseToastPoller />
      <PendingOrdersMonitor />

      <AlertToasts />
    </div>
  );
}
