/**
 * AUTO · RIESGO (ADR-044) — riesgo abierto, límites e integridad financiera.
 *
 * Reutiliza los bloques read-only de la Consola operativa; el detalle por
 * posición vive en Cartera → Riesgo (enlace). No re-deriva cifras.
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import {
  OpsFinancialIntegritySection,
  OpsLifecycleReconSection,
  OpsReconSection,
} from "@/features/operational-console/operational-console-sections";
import { useFinancialIntegrity } from "@/features/operational-console/use-financial-integrity";
import { useLifecycleReconciliation } from "@/features/operational-console/use-lifecycle-reconciliation";
import { useOpsSelfEval } from "@/features/operational-console/use-ops-self-eval";
import { CARTERA_RIESGO_PATH } from "@/features/confirm/daily-nav";

export function AutoRiesgoPage() {
  const { effectiveAccountId } = useActiveAccount();
  const selfEval = useOpsSelfEval(effectiveAccountId);
  const financial = useFinancialIntegrity(effectiveAccountId);
  const lifecycle = useLifecycleReconciliation(effectiveAccountId);

  return (
    <div className="space-y-6" data-testid="auto-riesgo-page">
      <AutoSectionHeading
        title="Riesgo"
        description="Riesgo abierto, límites e integridad financiera. Read-only: un hueco se declara NO MEDIDO."
      />

      <section
        className="space-y-2"
        aria-labelledby="auto-riesgo-integrity-heading"
      >
        <AutoSectionBlockHeading id="auto-riesgo-integrity-heading">
          Integridad financiera
        </AutoSectionBlockHeading>
        <OpsFinancialIntegritySection
          report={financial.data}
          isLoading={financial.isLoading}
          isError={financial.isError}
          error={financial.error}
        />
      </section>

      <section
        className="space-y-2"
        aria-labelledby="auto-riesgo-recon-heading"
      >
        <AutoSectionBlockHeading id="auto-riesgo-recon-heading">
          Reconciliación de ciclo de vida
        </AutoSectionBlockHeading>
        <OpsLifecycleReconSection
          report={lifecycle.data}
          isLoading={lifecycle.isLoading}
          isError={lifecycle.isError}
          error={lifecycle.error}
        />
      </section>

      <section
        className="space-y-2"
        aria-labelledby="auto-riesgo-portfolio-heading"
      >
        <AutoSectionBlockHeading id="auto-riesgo-portfolio-heading">
          Reconciliación de cartera
        </AutoSectionBlockHeading>
        <OpsReconSection report={selfEval.data} />
        <p className="text-xs text-muted-foreground">
          Riesgo por posición y límites en{" "}
          <Link
            to={CARTERA_RIESGO_PATH}
            className="underline hover:text-primary"
          >
            Cartera → Riesgo
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
