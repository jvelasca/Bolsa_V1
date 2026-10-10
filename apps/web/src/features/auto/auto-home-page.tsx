/**
 * AUTO · RESUMEN (HOME del cockpit) — `/auto` (ADR-044 + UI Contract 5.0 §UI5-04, UI REFACTOR 5.1).
 *
 * Landing del espacio AUTO: responde en 5 s las preguntas del usuario básico sin obligarle a
 * entrar en Sistema ni a conocer la arquitectura interna.
 *
 *   Estado → oportunidades → decisión → operación → dinero → detalles (plegados).
 *
 * Cada hecho se pinta **una sola vez** en primer nivel (`UI5-04`). El estado del motor vive en
 * la insignia humana; la actividad del último tick, en una única línea bajo ella; las
 * operaciones en curso, en un único bloque; el dinero, en un bloque con sus cifras (el chip
 * `SIMULADO` lo aporta el semáforo de realidad montado por el layout, no se repite aquí).
 * Se han retirado la batería de seis preguntas («¿AUTO está funcionando?» … «¿Qué dinero
 * utiliza?»), la fila de tiles y el bloque «¿Qué está haciendo AUTO?», que repetían estado,
 * operación y dinero (auditorías `G-01` y HOME user-first 5.1).
 *
 * Read-only y honesto: compone por enlace (no reimplementa Mesa/Análisis) y todo dato no medido
 * se declara «Sin dato todavía» (`buildAutoHomeSummary`). `ranking ≠ decisión` (`UI5-12`): la
 * decisión de cartera es un hueco declarado hasta que exista traza durable, nunca se deduce del
 * TOP3. El semáforo de realidad monetaria ya se monta sobre el `Outlet` del layout, así que esta
 * sección lo hereda en primer nivel.
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
  autoTechnicalDetailHref,
  AUTO_ACTIVIDAD_PATH,
  AUTO_ANALISIS_PATH,
  AUTO_OPERAR_PATH,
} from "@/features/auto/auto-nav";
import { mesaOportunidadesHref } from "@/features/mesa/mesa-nav-links";
import { buildAutoBasicHome } from "@/features/auto/auto-basic-home";
import {
  AUTO_HOME_NO_DATA_LABEL,
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
          totalRealizedPnl: summaryQuery.data.totalRealizedPnl ?? null,
        }
      : null,
    riskLabel: summary.riskLabel,
  });
  // Un solo hueco declarado (`UI5-04`): si la cuenta no está medida, no se apilan cifras
  // «Sin dato todavía». El riesgo es independiente del resumen y se conserva.
  const accountMeasured = summaryQuery.data != null;
  const visibleFigures = accountMeasured
    ? figures
    : figures.filter((figure) => figure.id === "risk");
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

  // Única línea de actividad de primer nivel (absorbe «¿Qué está haciendo?» sin repetirlo).
  const clockCopy = decisionClockCopy(
    summary.lastActivityLabel,
    summary.nextStepLabel,
  );
  const activityParts = [
    basic.doingLabel,
    clockCopy === AUTO_HOME_NO_DATA_LABEL ? null : clockCopy,
  ].filter((part): part is string => Boolean(part));
  const activityText = activityParts.join(" · ");
  // No se repite el hueco: si la insignia ya declara «Sin dato todavía» y la actividad no
  // aporta nada más, la línea se omite (evita declarar el mismo hecho dos veces, UI5-04).
  const showActivityLine =
    summary.loaded &&
    activityText.length > 0 &&
    !(
      activityText === AUTO_HOME_NO_DATA_LABEL &&
      humanState.label === AUTO_HOME_NO_DATA_LABEL
    );

  return (
    <div className="space-y-6" data-testid="auto-home-page">
      <AutoSectionHeading
        title="Resumen"
        description="Consulta qué está haciendo AUTO y qué ha ocurrido. No necesitas intervenir salvo que aparezca una acción."
      />

      {/* 1 · ESTADO — único lugar donde se afirma el estado del motor (UI5-04). */}
      <section
        className="space-y-2"
        aria-labelledby="auto-home-state-heading"
        data-testid="auto-home-state"
      >
        <AutoHumanStateBadge
          state={humanState}
          testId="auto-home-human-state"
        />
        {showActivityLine ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-home-activity-line"
          >
            {activityText}
          </p>
        ) : null}
      </section>

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
      </section>

      {/* 3 · DECISIÓN — hueco declarado: no se deduce del ranking (`UI5-12`).
          La cadena completa es oportunidad → ranking → (decisión de cartera) → orden; AUTO todavía
          no registra una decisión de cartera duradera, así que el eslabón se declara «Sin dato
          todavía» en vez de inferirlo del TOP3. */}
      <section
        className="space-y-1"
        aria-labelledby="auto-home-decision-heading"
        data-testid="auto-home-decision"
      >
        <AutoSectionBlockHeading id="auto-home-decision-heading">
          Decisión de cartera
        </AutoSectionBlockHeading>
        <p
          className={cn("font-semibold", AUTO_USER_TEXT)}
          data-testid="auto-home-decision-label"
        >
          {basic.decisionLabel}
        </p>
        <p className="text-sm text-muted-foreground">
          El ranking no es una decisión de compra. AUTO todavía no registra una
          decisión de cartera (qué activo y cuánto entrar); hasta que exista,
          este dato se declara «Sin dato todavía» y no se deduce del TOP3.
        </p>
      </section>

      {/* 4 · OPERACIÓN EN CURSO — un único bloque: contador + tarjetas + enlaces (UI5-04). */}
      {!summary.isLoading && !summary.isError ? (
        <section
          className="space-y-2"
          aria-labelledby="auto-home-operations-heading"
          data-testid="auto-home-operations"
        >
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <AutoSectionBlockHeading id="auto-home-operations-heading">
              Operación
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

          {/* El listado completo de operaciones vive en Operar: pertenece a Operación,
              no a Oportunidades (`UI5-04`, oportunidad ≠ operación). */}
          <p className="text-sm text-muted-foreground">
            <Link
              to={AUTO_OPERAR_PATH}
              className="underline hover:text-primary"
              data-testid="auto-home-all-operations-link"
            >
              Ver todas las operaciones
            </Link>{" "}
            en Operar.
          </p>
        </section>
      ) : null}

      {/* 5 · DINERO — cifras ya medidas de la cuenta simulada. El chip `SIMULADO` lo pinta el
          semáforo de realidad del layout; aquí no se repite (`UI5-04`). Un único hueco
          declarado: si la cuenta no está medida, no se apilan cifras «Sin dato todavía». */}
      <section
        className="space-y-2"
        aria-labelledby="auto-home-money-heading"
        data-testid="auto-home-account-figures"
      >
        <AutoSectionBlockHeading id="auto-home-money-heading">
          Dinero
        </AutoSectionBlockHeading>
        {accountMeasured ? null : (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-home-money-absent"
          >
            {AUTO_HOME_NO_DATA_LABEL}
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {visibleFigures.map((figure) => (
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

      {/* 6 · DETALLE — todo lo demás, bajo demanda (no compite en el primer nivel). */}
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
            <li>
              <Link
                to={autoTechnicalDetailHref()}
                className="underline hover:text-primary"
                data-testid="auto-home-technical-detail-link"
              >
                Detalle técnico
              </Link>
            </li>
          </ul>
          <AutoWhyButton why={why} testId="auto-home-why" />
        </section>
      </details>
    </div>
  );
}
