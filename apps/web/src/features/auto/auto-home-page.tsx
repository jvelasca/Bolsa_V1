/**
 * AUTO · RESUMEN (HOME del cockpit) — `/auto` (ADR-044 + spec 3.0 §2).
 *
 * Landing del espacio AUTO: responde en 5 s las preguntas del usuario básico sin obligarle a
 * entrar en Sistema ni a conocer la arquitectura interna.
 *
 *   Seis preguntas · cifras de cuenta · tarjeta de la operación en curso.
 *   Oportunidades, DÍA-D, evidencia e investigación quedan detrás de «Ver actividad».
 *
 * Read-only y honesto: compone por enlace (no reimplementa Mesa/Análisis) y todo dato no medido
 * se declara «Sin dato todavía» (`buildAutoHomeSummary`). El semáforo de realidad monetaria ya se
 * monta sobre el `Outlet` del layout, así que esta sección lo hereda en primer nivel.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §2
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §3 §4
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useFinancialIntegrity } from "@/features/operational-console/use-financial-integrity";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { buildAutoAccountFigures } from "@/features/auto/auto-account-figures";
import { buildOperationIdentity } from "@/features/auto/auto-operation-identity";
import { buildAutoOperationCard } from "@/features/auto/auto-operation-card";
import { AutoOperationCardView } from "@/features/auto/auto-operation-card-view";
import {
  autoOperacionHref,
  AUTO_ANALISIS_PATH,
  AUTO_OPERAR_PATH,
} from "@/features/auto/auto-nav";
import { mesaOportunidadesHref } from "@/features/mesa/mesa-nav-links";
import { buildAutoBasicHome } from "@/features/auto/auto-basic-home";
import {
  buildAutoHomeSummary,
  decisionClockCopy,
} from "@/features/auto/auto-home-summary";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import { AUTO_RISK_TONE_CLASS } from "@/features/auto/auto-risk-summary";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

function SummaryTile({
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
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-1 text-lg font-semibold", valueClass)}>{value}</p>
    </div>
  );
}

export function AutoHomePage() {
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const { effectiveAccountId } = useActiveAccount();
  const financial = useFinancialIntegrity(effectiveAccountId);
  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: async () =>
      (await api.getAccountSummary(effectiveAccountId!)).data,
    enabled: Boolean(effectiveAccountId),
  });

  const cycles = view?.cycles ?? [];
  const summary = buildAutoHomeSummary({
    header: view?.header ?? null,
    cycles,
    riskOperationalState: financial.data?.operationalState ?? null,
    isLoading,
    isError,
  });
  const basic = buildAutoBasicHome({
    isLoading,
    isError,
    header: view?.header ?? null,
    cycles,
  });
  const figures = buildAutoAccountFigures({
    summary: summaryQuery.data
      ? {
          positionsCount: summaryQuery.data.positionsCount,
          cash: summaryQuery.data.cash,
          totalUnrealizedPnl: summaryQuery.data.totalUnrealizedPnl,
        }
      : null,
    riskLabel: summary.riskLabel,
  });
  const figureById = (id: string) =>
    figures.find((item) => item.id === id)?.value ?? "";
  const accountForCard = {
    positionLabel: figureById("position"),
    cashLabel: figureById("cash"),
    pnlLabel: figureById("pnl"),
  };
  const cards = basic.currentOperations.flatMap((operation) => {
    const cycle = cycles.find((item) => item.cycleId === operation.cycleId);
    return cycle ? [buildAutoOperationCard(cycle, accountForCard)] : [];
  });

  const inCourseOperations = basic.currentOperations.flatMap((operation) => {
    const cycle = cycles.find((item) => item.cycleId === operation.cycleId);
    return cycle
      ? [
          {
            cycleId: operation.cycleId,
            identity: buildOperationIdentity(cycle),
          },
        ]
      : [];
  });

  return (
    <div className="space-y-6" data-testid="auto-home-page">
      <AutoSectionHeading
        title="Resumen"
        description="Qué está haciendo AUTO, qué puedes hacer y qué ha pasado. Todo es dinero virtual (DEMO)."
      />

      <section
        className="space-y-3"
        aria-label="Seis preguntas de AUTO"
        data-testid="auto-home-questions"
      >
        {(
          [
            [
              "¿AUTO está funcionando?",
              basic.workingLabel,
              "auto-home-q-working",
            ],
            ["¿Qué está haciendo?", basic.doingLabel, "auto-home-q-doing"],
            ["¿Qué activo?", basic.assetLabel, "auto-home-q-asset"],
            ["¿Qué ha decidido?", basic.decisionLabel, "auto-home-q-decision"],
            [
              "¿Qué ha ocurrido realmente?",
              basic.happenedLabel,
              "auto-home-q-happened",
            ],
            ["¿Qué dinero utiliza?", basic.moneyLabel, "auto-home-q-money"],
          ] as const
        ).map(([question, answer, testId]) => (
          <div key={testId} data-testid={testId}>
            <p className={cn(AUTO_USER_TEXT, "text-muted-foreground")}>
              {question}
            </p>
            <p className={cn("mt-0.5 font-semibold", AUTO_USER_TEXT)}>
              {answer}
            </p>
          </div>
        ))}
      </section>

      <section
        className="grid gap-3 sm:grid-cols-2"
        aria-label="Cifras de la cuenta simulada"
        data-testid="auto-home-account-figures"
      >
        {figures.map((figure) => (
          <div key={figure.id} data-testid={`auto-home-figure-${figure.id}`}>
            <p className={cn(AUTO_USER_TEXT, "text-muted-foreground")}>
              {figure.label}
            </p>
            <p className={cn("mt-0.5 font-semibold", AUTO_USER_TEXT)}>
              {figure.value}
            </p>
          </div>
        ))}
      </section>

      {cards.length > 0 ? (
        <section
          className="space-y-3"
          aria-label="Operaciones en curso"
          data-testid="auto-home-operation-cards"
        >
          {cards.map((card) => (
            <AutoOperationCardView key={card.cycleId} card={card} />
          ))}
        </section>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryTile
          label="AUTO"
          value={summary.autoLabel}
          testId="auto-home-tile-auto"
        />
        <SummaryTile
          label="Operaciones"
          value={summary.inCourseOperationsLabel}
          testId="auto-home-tile-operations"
        />
        <SummaryTile
          label="Riesgo"
          value={summary.riskLabel}
          valueClass={AUTO_RISK_TONE_CLASS[summary.riskTone]}
          testId="auto-home-tile-risk"
        />
      </div>

      <section className="space-y-2" aria-labelledby="auto-home-doing">
        <AutoSectionBlockHeading id="auto-home-doing">
          ¿Qué está haciendo AUTO?
        </AutoSectionBlockHeading>
        {summary.isLoading ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-home-loading"
          >
            Cargando estado de AUTO…
          </p>
        ) : null}
        {summary.isError ? (
          <p className="text-sm text-destructive" data-testid="auto-home-error">
            No se pudo cargar el estado de AUTO.
          </p>
        ) : null}
        {summary.loaded ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium" data-testid="auto-home-doing">
              {summary.statusLabel}
            </p>
            <p
              className="text-muted-foreground"
              data-testid="auto-home-last-activity"
            >
              {decisionClockCopy(
                summary.lastActivityLabel,
                summary.nextStepLabel,
              )}
            </p>
          </div>
        ) : null}
      </section>

      <section className="space-y-2" aria-labelledby="auto-home-can-do">
        <AutoSectionBlockHeading id="auto-home-can-do">
          ¿Qué puedo hacer?
        </AutoSectionBlockHeading>

        {!summary.isLoading && !summary.isError ? (
          inCourseOperations.length > 0 ? (
            <ul
              className="space-y-1.5"
              data-testid="auto-home-in-course-operations"
            >
              {inCourseOperations.map((operation) => (
                <li key={operation.cycleId}>
                  <Link
                    to={autoOperacionHref(operation.cycleId)}
                    data-testid="auto-home-operation-link"
                    data-cycle-id={operation.cycleId}
                    className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent hover:text-foreground"
                  >
                    <span className="font-medium">
                      {operation.identity.label}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      Ver historia →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p
              className="text-sm text-muted-foreground"
              data-testid="auto-home-in-course-empty"
            >
              Sin operaciones en curso.
            </p>
          )
        ) : null}

        <p className="text-sm text-muted-foreground">
          <Link
            to={AUTO_OPERAR_PATH}
            className="underline hover:text-primary"
            data-testid="auto-home-all-operations-link"
          >
            Ver todas las operaciones
          </Link>
        </p>
      </section>

      <details className="space-y-2" data-testid="auto-home-activity">
        <summary className={cn("cursor-pointer font-medium", AUTO_USER_TEXT)}>
          Ver actividad
        </summary>
        <section
          className="space-y-2 pt-2"
          aria-labelledby="auto-home-happened"
        >
          <AutoSectionBlockHeading id="auto-home-happened">
            ¿Qué ha pasado?
          </AutoSectionBlockHeading>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <li>
              <Link
                to={mesaOportunidadesHref()}
                className="underline hover:text-primary"
                data-testid="auto-home-opportunities-link"
              >
                Oportunidades
              </Link>
            </li>
            <li>
              <Link
                to={`${AUTO_ANALISIS_PATH}?tab=dia-d`}
                className="underline hover:text-primary"
                data-testid="auto-home-link-dia-d"
              >
                DÍA-D
              </Link>
            </li>
            <li>
              <Link
                to={`${AUTO_ANALISIS_PATH}?tab=evidencia`}
                className="underline hover:text-primary"
              >
                Evidencia
              </Link>
            </li>
            <li>
              <Link
                to={`${AUTO_ANALISIS_PATH}?tab=investigacion`}
                className="underline hover:text-primary"
              >
                Investigación
              </Link>
            </li>
          </ul>
        </section>
      </details>
    </div>
  );
}
