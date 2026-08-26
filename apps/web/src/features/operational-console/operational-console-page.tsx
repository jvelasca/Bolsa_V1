/**
 * Operational Console — agregador read-only de salud operativa (OE-1, OR-6, recon, DEX-3).
 * Complementa P4 /operations (posiciones-first). No firma ni ejecuta.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { OperationalIncidentV1 } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";
import {
  OpsReadinessSection,
  OpsReconSection,
  OpsRuntimeSection,
  OpsSelfEvalSection,
} from "@/features/operational-console/operational-console-sections";
import {
  OpsIncidentsSection,
  OpsQuickLinksSection,
} from "@/features/operational-console/ops-incidents-and-links";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { api } from "@/lib/api";

export function OperationalConsolePage() {
  const { effectiveAccountId, account } = useActiveAccount();
  const selfEvalQuery = useOpsSelfEval(effectiveAccountId);
  const report = selfEvalQuery.data;
  const portfolioReconStatus = portfolioReconStatusFromReport(report);

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
  });

  const [incidentPanel, setIncidentPanel] = useState<{
    open: boolean;
    incidentId: string | null;
  }>({ open: false, incidentId: null });

  function handleManageIncident(incident: OperationalIncidentV1) {
    setIncidentPanel({
      open: true,
      incidentId: incident.incidentId,
    });
  }

  const pendingConfirm = boardQuery.data?.data?.buckets?.pendingConfirm ?? 0;

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      data-testid="operational-console"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight">
            Consola operacional
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Salud ops read-only — OE-1, readiness, recon e incidentes
            {account ? ` · ${account.name}` : ""}.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Posiciones y CTAs de desriesgo siguen en{" "}
            <Link to="/operations" className="text-primary hover:underline">
              Libro · Operaciones
            </Link>
            . Confirm = única firma.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void selfEvalQuery.refetch()}
          disabled={selfEvalQuery.isFetching}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Actualizar
        </Button>
      </div>

      {selfEvalQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando scorecard…</p>
      ) : null}

      {selfEvalQuery.isError ? (
        <p className="text-sm text-destructive" data-testid="ops-console-error">
          No se pudo cargar ops-self-eval.
        </p>
      ) : null}

      {effectiveAccountId ? (
        <MesaIncidentBanner
          accountId={effectiveAccountId}
          portfolioReconStatus={portfolioReconStatus}
          showBanner
          panelOpen={incidentPanel.open}
          onPanelOpenChange={(open) =>
            setIncidentPanel((prev) => ({ ...prev, open }))
          }
          focusIncidentId={incidentPanel.incidentId}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <OpsReadinessSection report={report} />
        <OpsRuntimeSection report={report} />
        <OpsSelfEvalSection report={report} />
        <OpsReconSection report={report} />
        {effectiveAccountId ? (
          <OpsIncidentsSection
            accountId={effectiveAccountId}
            onManageIncident={handleManageIncident}
          />
        ) : null}
        <OpsQuickLinksSection pendingConfirm={pendingConfirm} />
      </div>
    </div>
  );
}
