/**
 * AUTO · RESUMEN (HOME del cockpit) — `/auto` (ADR-044 + UI Contract 5.0 §UI5-04).
 *
 * Landing del espacio AUTO: responde en 5 s las preguntas del usuario básico sin obligarle a
 * entrar en Sistema ni a conocer la arquitectura interna.
 *
 *   Estado → oportunidades → decisión → operación → dinero → enlaces.
 *
 * Cada hecho se pinta **una sola vez** en primer nivel (`UI5-04`): el estado del motor vive en el
 * badge humano y en su pregunta; las operaciones en curso, en un único bloque (contador + tarjetas
 * + enlaces). Se han retirado la fila de tiles y el bloque «¿Qué está haciendo AUTO?», que
 * repetían el estado y las operaciones (auditoría `G-01`).
 *
 * Read-only y honesto: compone por enlace (no reimplementa Mesa/Análisis) y todo dato no medido
 * se declara «Sin dato todavía» (`buildAutoHomeSummary`). El semáforo de realidad monetaria ya se
 * monta sobre el `Outlet` del layout, así que esta sección lo hereda en primer nivel.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-04 §UI5-05
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §2
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
  AUTO_ACTIVIDAD_PATH,
  AUTO_ANALISIS_PATH,
  AUTO_OPERAR_PATH,
} from "@/features/auto/auto-nav";
import { mesaOportunidadesHref } from "@/features/mesa/mesa-nav-links";
import { buildAutoBasicHome } from "@/features/auto/auto-basic-home";
import {
  buildAutoHomeSummary,
  decisionClockCopy,
} from "@/features/auto/auto-home-summary";
import { buildAutoHumanState } from "@/features/auto/auto-human-state";
import { AutoHumanStateBadge } from "@/features/auto/auto-human-state-badge";
import { buildAutoStateWhy } from "@/features/auto/auto-why";
import { AutoWhyButton } from "@/features/auto/auto-why-button";
import { AutoTop3Panel } from "@/features/auto/auto-top3-panel";
import { useAutoTop3Opportunities } from "@/features/auto/use-auto-top3-opportunities";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

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

  const humanState = buildAutoHumanState({
    header: view?.header ?? null,
    riskOperationalState: financial.data?.operationalState ?? null,
    isLoading,
    isError,
  });
  const why = buildAutoStateWhy({
    state: humanState,
    header: view?.header ?? null,
    riskOperationalState: financial.data?.operationalState ?? null,
    hasOperationsInCourse: inCourseOperations.length > 0,
  });
  const top3 = useAutoTop3Opportunities();

  return (
    <div className="space-y-6" data-testid="auto-home-page">
      <AutoSectionHeading
        title="Resumen"
        description="Qué está haciendo AUTO, qué puedes hacer y qué ha pasado. Todo es dinero virtual (DEMO)."
      />

      {/* 1 · ESTADO — único lugar donde se afirma el estado del motor (UI5-04). */}
      <AutoHumanStateBadge state={humanState} testId="auto-home-human-state" />
      <AutoWhyButton why={why} testId="auto-home-why" />

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
        ).map(([question, answer, testId]) => {
          const isDoing = testId === "auto-home-q-doing";
          return (
            <div key={testId} data-testid={testId}>
              <p className={cn(AUTO_USER_TEXT, "text-muted-foreground")}>
                {question}
              </p>
              <p
                className={cn("mt-0.5 font-semibold", AUTO_USER_TEXT)}
                {...(isDoing ? { "data-testid": "auto-home-doing" } : {})}
              >
                {answer}
              </p>
              {isDoing && summary.loaded ? (
                <p
                  className="mt-0.5 text-xs text-muted-foreground"
                  data-testid="auto-home-last-activity"
                >
                  {decisionClockCopy(
                    summary.lastActivityLabel,
                    summary.nextStepLabel,
                  )}
                </p>
              ) : null}
            </div>
          );
        })}
      </section>

      {/* 2 · OPORTUNIDADES — TOP3 resumido; el ranking completo vive en Operar (UI5-05/06). */}
      <section
        className="space-y-2"
        aria-labelledby="auto-home-opportunities-heading"
        data-testid="auto-home-opportunities"
      >
        <AutoSectionBlockHeading id="auto-home-opportunities-heading">
          Oportunidades
        </AutoSectionBlockHeading>
        <AutoTop3Panel
          view={top3.view}
          isLoading={top3.isLoading}
          isError={top3.isError}
          compact
          testId="auto-home-top3"
        />
        <p className="text-sm text-muted-foreground">
          El universo completo vive en{" "}
          <Link
            to={mesaOportunidadesHref()}
            className="underline hover:text-primary"
            data-testid="auto-home-opportunities-more-link"
          >
            Hoy → Oportunidades
          </Link>
          ; aquí se resume el subconjunto que AUTO usa.
        </p>
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

      {/* 3 · OPERACIÓN EN CURSO — un único bloque: contador + tarjetas + enlaces (UI5-04). */}
      {!summary.isLoading && !summary.isError ? (
        <section
          className="space-y-2"
          aria-labelledby="auto-home-operations-heading"
          data-testid="auto-home-operations"
        >
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <AutoSectionBlockHeading id="auto-home-operations-heading">
              Operaciones en curso
            </AutoSectionBlockHeading>
            <span
              className="text-xs text-muted-foreground"
              data-testid="auto-home-tile-operations"
            >
              {summary.inCourseOperationsLabel}
            </span>
          </div>

          {inCourseOperations.length > 0 ? (
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
                      Ver operación →
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
          )}

          {cards.length > 0 ? (
            <div
              className="space-y-3"
              aria-label="Tarjeta de la operación en curso"
              data-testid="auto-home-operation-cards"
            >
              {cards.map((card) => (
                <AutoOperationCardView key={card.cycleId} card={card} />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* 4 · DINERO — cifras ya medidas de la cuenta simulada. */}
      <section
        className="space-y-2"
        aria-labelledby="auto-home-money-heading"
        data-testid="auto-home-account-figures"
      >
        <AutoSectionBlockHeading id="auto-home-money-heading">
          Dinero
        </AutoSectionBlockHeading>
        <div className="grid gap-3 sm:grid-cols-2">
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
        </div>
      </section>

      {/* 5 · ENLACES — el resto de superficies, bajo demanda. */}
      <details className="space-y-2" data-testid="auto-home-activity">
        <summary className={cn("cursor-pointer font-medium", AUTO_USER_TEXT)}>
          Ver actividad
        </summary>
        <section
          className="space-y-2 pt-2"
          aria-labelledby="auto-home-happened-heading"
        >
          <AutoSectionBlockHeading id="auto-home-happened-heading">
            ¿Qué ha pasado?
          </AutoSectionBlockHeading>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <li>
              <Link
                to={AUTO_ACTIVIDAD_PATH}
                className="underline hover:text-primary"
                data-testid="auto-home-activity-link"
              >
                Toda la actividad
              </Link>
            </li>
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
