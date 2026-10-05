/**
 * AUTO · SISTEMA (ADR-044) — Salud AUTO · Broker/ejecución · Reconciliación · Auditoría.
 *
 * Compone la ventana cruda del monitor (header + timeline + reservas +
 * concurrencia), la reconciliación read-only de la Consola y enlaces a la
 * auditoría. Resumen operativo arriba; detalle experto enlazado.
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { AutoConcurrencyPanel } from "@/features/auto-monitor/auto-concurrency-panel";
import { AutoCycleTimeline } from "@/features/auto-monitor/auto-cycle-timeline";
import { AutoMonitorHeader } from "@/features/auto-monitor/auto-monitor-header";
import { AutoReservationPanel } from "@/features/auto-monitor/auto-reservation-panel";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import {
  OpsLifecycleReconSection,
  OpsReconSection,
} from "@/features/operational-console/operational-console-sections";
import { useLifecycleReconciliation } from "@/features/operational-console/use-lifecycle-reconciliation";
import { useOpsSelfEval } from "@/features/operational-console/use-ops-self-eval";

export function AutoSistemaPage() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const { effectiveAccountId } = useActiveAccount();
  const selfEval = useOpsSelfEval(effectiveAccountId);
  const lifecycle = useLifecycleReconciliation(effectiveAccountId);

  return (
    <div className="space-y-6" data-testid="auto-sistema-page">
      <AutoSectionHeading
        title="Sistema"
        description="Salud del motor AUTO, broker/ejecución, reconciliación y auditoría. Read-only."
      />

      <section className="space-y-3" aria-labelledby="auto-sistema-salud">
        <AutoSectionBlockHeading id="auto-sistema-salud">
          Salud AUTO
        </AutoSectionBlockHeading>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Cargando monitor…</p>
        ) : null}
        {isError ? (
          <p className="text-sm text-destructive">
            No se pudo cargar el monitor operativo.
          </p>
        ) : null}
        {view ? (
          <>
            <AutoMonitorHeader header={view.header} />
            <AutoCycleTimeline cycles={view.cycles} />
            <div className="grid gap-4 lg:grid-cols-2">
              <AutoReservationPanel reservations={view.reservations} />
              <AutoConcurrencyPanel concurrency={view.concurrency} />
            </div>
          </>
        ) : null}
        <p className="text-xs text-muted-foreground">
          Vista experta (ventana actual con huecos declarados) en{" "}
          <Link
            to="/auto-monitor?mode=current"
            className="underline hover:text-primary"
          >
            Monitor AUTO
          </Link>
          .
        </p>
      </section>

      <section className="space-y-2" aria-labelledby="auto-sistema-broker">
        <AutoSectionBlockHeading id="auto-sistema-broker">
          Broker / ejecución
        </AutoSectionBlockHeading>
        <p className="text-sm text-muted-foreground">
          Ejecución declarada vs habilitada y modelo de protección en la salud
          de arriba; estado de cuenta y P&amp;L en el{" "}
          <Link to="/trading" className="underline hover:text-primary">
            terminal de Mercado
          </Link>
          .
        </p>
      </section>

      <section className="space-y-2" aria-labelledby="auto-sistema-recon">
        <AutoSectionBlockHeading id="auto-sistema-recon">
          Reconciliación
        </AutoSectionBlockHeading>
        <div className="grid gap-4 lg:grid-cols-2">
          <OpsReconSection report={selfEval.data} />
          <OpsLifecycleReconSection
            report={lifecycle.data}
            isLoading={lifecycle.isLoading}
            isError={lifecycle.isError}
            error={lifecycle.error}
          />
        </div>
      </section>

      <section className="space-y-2" aria-labelledby="auto-sistema-auditoria">
        <AutoSectionBlockHeading id="auto-sistema-auditoria">
          Auditoría
        </AutoSectionBlockHeading>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <li>
            <Link
              to="/decision-journal"
              className="underline hover:text-primary"
            >
              Decision Journal
            </Link>
          </li>
          <li>
            <Link to="/history" className="underline hover:text-primary">
              Historial · ledger y fills
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}
