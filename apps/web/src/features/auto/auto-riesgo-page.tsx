/**
 * AUTO · RIESGO (ADR-044) — riesgo abierto, límites e integridad financiera.
 *
 * Reutiliza los bloques read-only de la Consola operativa; el detalle por
 * posición vive en Cartera → Riesgo (enlace). La **reconciliación** (ciclo de vida y cartera) se
 * muestra UNA vez, en Sistema: aquí sólo se enlaza para no duplicar la superficie (F-DUP1).
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { OpsFinancialIntegritySection } from "@/features/operational-console/operational-console-sections";
import { useFinancialIntegrity } from "@/features/operational-console/use-financial-integrity";
import { CARTERA_RIESGO_PATH } from "@/features/confirm/daily-nav";
import { AUTO_SISTEMA_PATH } from "@/features/auto/auto-nav";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";

export function AutoRiesgoPage() {
  const { effectiveAccountId } = useActiveAccount();
  const financial = useFinancialIntegrity(effectiveAccountId);

  return (
    <div className="space-y-6" data-testid="auto-riesgo-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.riesgo.title}
        description={AUTO_SECTION_COPY.riesgo.description}
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
          Reconciliación
        </AutoSectionBlockHeading>
        <p className="text-sm text-muted-foreground">
          El cuadre de ciclo de vida y de cartera se muestra una sola vez, en{" "}
          <Link to={AUTO_SISTEMA_PATH} className="underline hover:text-primary">
            Sistema
          </Link>
          . Riesgo por posición y límites, en{" "}
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
