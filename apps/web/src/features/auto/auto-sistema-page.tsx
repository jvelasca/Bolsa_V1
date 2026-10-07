/**
 * AUTO · SISTEMA (ADR-044 + spec 3.0 §5) — primero «qué está haciendo AUTO», después el interior.
 *
 * Primer nivel (usuario): estado de AUTO en frases. El reloj copia la última decisión
 * y, si existe, la próxima. Sin ese sello la frase es «Sin dato todavía». Reutiliza
 * `buildAutoHomeSummary`.
 *
 * Detalle técnico (experto), plegado: la ventana cruda del monitor (header + timeline + reservas +
 * concurrencia), broker/ejecución y la reconciliación read-only de la Consola. La auditoría son
 * enlaces y queda accesible en primer nivel.
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
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import {
  buildAutoHomeSummary,
  decisionClockCopy,
} from "@/features/auto/auto-home-summary";
import { buildAutoHumanState } from "@/features/auto/auto-human-state";
import { AutoHumanStateBadge } from "@/features/auto/auto-human-state-badge";

export function AutoSistemaPage() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const { effectiveAccountId } = useActiveAccount();
  const selfEval = useOpsSelfEval(effectiveAccountId);
  const lifecycle = useLifecycleReconciliation(effectiveAccountId);

  const status = buildAutoHomeSummary({
    header: view?.header ?? null,
    cycles: view?.cycles ?? [],
    isLoading,
    isError,
  });

  const humanState = buildAutoHumanState({
    header: view?.header ?? null,
    isLoading,
    isError,
  });

  return (
    <div className="space-y-6" data-testid="auto-sistema-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.sistema.title}
        description={AUTO_SECTION_COPY.sistema.description}
      />

      <section className="space-y-2" aria-labelledby="auto-sistema-estado">
        <AutoSectionBlockHeading id="auto-sistema-estado">
          Estado de AUTO
        </AutoSectionBlockHeading>
        <AutoHumanStateBadge
          state={humanState}
          testId="auto-sistema-human-state"
        />
        {status.isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-sistema-loading"
          >
            Cargando estado de AUTO…
          </p>
        ) : null}
        {status.isError ? (
          <p
            className="text-sm text-destructive"
            data-testid="auto-sistema-error"
          >
            No se pudo cargar el monitor operativo.
          </p>
        ) : null}
        {status.loaded ? (
          <div className="space-y-1 text-sm">
            <p
              className="text-base font-semibold"
              data-testid="auto-sistema-auto"
            >
              AUTO: {status.autoLabel}
            </p>
            <p className="font-medium" data-testid="auto-sistema-doing">
              {status.activityLabel}
            </p>
            <p
              className="text-muted-foreground"
              data-testid="auto-sistema-last-activity"
            >
              {decisionClockCopy(
                status.lastActivityLabel,
                status.nextStepLabel,
              )}
            </p>
          </div>
        ) : null}
      </section>

      <AutoTechnicalDetail testId="auto-sistema-technical">
        <section className="space-y-3" aria-labelledby="auto-sistema-salud">
          <AutoSectionBlockHeading id="auto-sistema-salud">
            Salud AUTO
          </AutoSectionBlockHeading>
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
          <p className="text-muted-foreground">
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
          <p className="text-muted-foreground">
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
      </AutoTechnicalDetail>

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
