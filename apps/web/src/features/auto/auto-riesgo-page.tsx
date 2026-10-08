/**
 * AUTO · RIESGO (ADR-044 + spec 3.0 §5) — primero «¿cuánto puedo perder?», después el detalle.
 *
 * Primer nivel (usuario): una cabecera plana con el **estado** y lo que el read-model de AUTO sí
 * materializa (integridad de cartera, incidencias de enlace). Riesgo por posición, máxima pérdida y
 * límites NO viven aquí: se declaran «Sin dato todavía» y se enlazan a su superficie canónica
 * (Cartera → Riesgo). Nunca se inventa una cifra ni se rellena un hueco con `0`.
 *
 * Detalle técnico (experto): integridad financiera read-only. La **reconciliación** se muestra UNA
 * vez, en Sistema: aquí sólo se enlaza para no duplicar la superficie (F-DUP1).
 */

import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { AutoTechnicalDetail } from "@/features/auto/auto-technical-detail";
import { absentDataLabel } from "@/components/absent-data";
import { OpsFinancialIntegritySection } from "@/features/operational-console/operational-console-sections";
import { useFinancialIntegrity } from "@/features/operational-console/use-financial-integrity";
import { CARTERA_RIESGO_PATH } from "@/features/confirm/daily-nav";
import { AUTO_SISTEMA_PATH } from "@/features/auto/auto-nav";
import { AUTO_SECTION_COPY } from "@/features/auto/auto-copy";
import {
  buildAutoRiskSummary,
  AUTO_RISK_TONE_CLASS,
} from "@/features/auto/auto-risk-summary";
import { cn } from "@/lib/utils";

function RiskField({
  label,
  value,
  valueClass,
  testId,
}: {
  label: string;
  value: string;
  valueClass?: string;
  testId: string;
}) {
  return (
    <div
      className="rounded-lg border border-border bg-card px-4 py-3"
      data-testid={testId}
    >
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={cn("mt-1 text-lg font-semibold", valueClass)}>{value}</dd>
    </div>
  );
}

export function AutoRiesgoPage() {
  const { effectiveAccountId } = useActiveAccount();
  const financial = useFinancialIntegrity(effectiveAccountId);

  const risk = buildAutoRiskSummary({
    operationalState: financial.data?.operationalState ?? null,
    portfolioStatus: financial.data?.portfolioStatus ?? null,
    fillLinkIssuesCount: financial.data?.fillLinkIssues?.length ?? null,
    isLoading: financial.isLoading,
    isError: financial.isError,
  });

  return (
    <div className="space-y-6" data-testid="auto-riesgo-page">
      <AutoSectionHeading
        title={AUTO_SECTION_COPY.riesgo.title}
        description={AUTO_SECTION_COPY.riesgo.description}
      />

      {/* Primer nivel (`UI5-18`, `RT-03`): un veredicto + una frase + como máximo UNA
          declaración de hueco. Los campos sólo aparecen cuando traen un valor medido. */}
      <div className="space-y-6" data-testid="auto-riesgo-first-level">
        {/* Veredicto human-first (`UI5-18`): el primer nivel responde «¿cuánto puedo perder?»
          con una palabra, no con métricas. */}
        <section
          className="space-y-1 rounded-lg border border-border bg-card px-4 py-3"
          data-testid="auto-riesgo-verdict"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Veredicto
          </p>
          <p
            className={cn(
              "text-lg font-semibold",
              AUTO_RISK_TONE_CLASS[risk.verdictTone],
            )}
            data-testid="auto-riesgo-verdict-label"
          >
            {risk.verdict}
          </p>
          <p className="text-sm text-muted-foreground">
            {risk.verdictSentence}
          </p>
        </section>

        <section className="space-y-3" aria-labelledby="auto-riesgo-now">
          <AutoSectionBlockHeading id="auto-riesgo-now">
            Riesgo actual
          </AutoSectionBlockHeading>

          {risk.isLoading ? (
            <p
              className="text-sm text-muted-foreground"
              data-testid="auto-riesgo-loading"
            >
              Cargando riesgo…
            </p>
          ) : null}
          {risk.isError ? (
            <p
              className="text-sm text-destructive"
              data-testid="auto-riesgo-error"
            >
              No se pudo cargar la integridad financiera.
            </p>
          ) : null}

          {risk.stateAvailable ||
          risk.portfolioAvailable ||
          risk.fillLinkIssuesAvailable ? (
            <dl className="grid gap-3 sm:grid-cols-3">
              {risk.stateAvailable ? (
                <RiskField
                  label="Estado"
                  value={risk.stateLabel}
                  valueClass={AUTO_RISK_TONE_CLASS[risk.stateTone]}
                  testId="auto-riesgo-state"
                />
              ) : null}
              {risk.portfolioAvailable ? (
                <RiskField
                  label="Integridad de cartera"
                  value={risk.portfolioLabel}
                  testId="auto-riesgo-portfolio"
                />
              ) : null}
              {risk.fillLinkIssuesAvailable ? (
                <RiskField
                  label="Incidencias de enlace"
                  value={risk.fillLinkIssuesLabel}
                  testId="auto-riesgo-fill-links"
                />
              ) : null}
            </dl>
          ) : null}

          {risk.positionRiskAvailable ? (
            <dl className="grid gap-2 sm:grid-cols-2">
              <div className="flex justify-between gap-4 text-sm">
                <dt className="text-muted-foreground">Riesgo abierto</dt>
                <dd data-testid="auto-riesgo-open-risk">
                  {risk.positionRiskLabel}
                </dd>
              </div>
              <div className="flex justify-between gap-4 text-sm">
                <dt className="text-muted-foreground">Máxima pérdida</dt>
                <dd data-testid="auto-riesgo-max-loss">
                  {risk.positionRiskLabel}
                </dd>
              </div>
              <div className="flex justify-between gap-4 text-sm">
                <dt className="text-muted-foreground">Posiciones con riesgo</dt>
                <dd data-testid="auto-riesgo-position-risk">
                  {risk.positionRiskLabel}
                </dd>
              </div>
              <div className="flex justify-between gap-4 text-sm">
                <dt className="text-muted-foreground">Límite diario</dt>
                <dd data-testid="auto-riesgo-daily-limit">
                  {risk.positionRiskLabel}
                </dd>
              </div>
            </dl>
          ) : (
            // Los límites detallados no viven en el read-model de AUTO. Si el veredicto ya declaró
            // el hueco (`Sin dato todavía`), aquí sólo se enlaza la superficie canónica para no
            // repetir el rótulo; si el veredicto trae una lectura real, éste es el único mensaje de
            // hueco del primer nivel. Nunca se rellena con `0`.
            <p
              className="text-sm text-muted-foreground"
              data-testid="auto-riesgo-limits"
            >
              {risk.verdictTone === "unknown" ? (
                <>El riesgo por posición y los límites se calculan en </>
              ) : (
                <>
                  Riesgo por posición y límites: {absentDataLabel()}. El detalle
                  se calcula en{" "}
                </>
              )}
              <Link
                to={CARTERA_RIESGO_PATH}
                className="underline hover:text-primary"
              >
                Cartera → Riesgo
              </Link>
              .
            </p>
          )}
        </section>
      </div>

      <AutoTechnicalDetail testId="auto-riesgo-technical">
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
          <p className="text-muted-foreground">
            El cuadre de ciclo de vida y de cartera se muestra una sola vez, en{" "}
            <Link
              to={AUTO_SISTEMA_PATH}
              className="underline hover:text-primary"
            >
              Sistema
            </Link>
            .
          </p>
        </section>
      </AutoTechnicalDetail>
    </div>
  );
}
