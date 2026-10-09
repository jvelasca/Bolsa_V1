/**
 * P4 — «Por qué AUTO no operó»: panel de dos capas rotuladas en la sección Actividad.
 *
 * El contenedor compone las fuentes ya existentes (NO recalcula) y delega la lectura al
 * read-model puro `buildAutoNoTradeExplanation`; la vista presentacional sólo pinta el modelo.
 * Ninguna cifra se re-deriva y ningún hueco se rellena con 0: cuando una fuente no responde,
 * la capa entera se declara «Sin dato todavía».
 *
 * @see docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md (P4)
 * @see apps/web/src/features/auto/auto-no-trade-explanation.ts
 */

import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import { autoOperacionHref } from "@/features/auto/auto-nav";
import {
  AUTO_NO_TRADE_PANEL_DESCRIPTION,
  AUTO_NO_TRADE_PANEL_TITLE,
  type AutoNoTradeStatus,
} from "@/features/auto/auto-no-trade-labels";
import {
  buildAutoNoTradeExplanation,
  type AutoNoTradeAutoDeskFacts,
  type AutoNoTradeCycleFacts,
  type AutoNoTradeExplanationV1,
  type AutoNoTradeGateFacts,
  type AutoNoTradeLayerV1,
  type AutoNoTradeRowV1,
} from "@/features/auto/auto-no-trade-explanation";

const STATUS_DOT: Record<AutoNoTradeStatus, string> = {
  occurred: "bg-rose-500",
  not_applicable: "bg-muted-foreground/40",
  unknown: "bg-amber-500",
};

const STATUS_TONE: Record<AutoNoTradeStatus, string> = {
  occurred: "text-rose-600 dark:text-rose-400",
  not_applicable: "text-muted-foreground",
  unknown: "text-amber-600 dark:text-amber-400",
};

/** Fecha local `YYYY-MM-DD` (sin desplazamiento de zona). */
function todayIso(date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function EvidenceList({ row }: { row: AutoNoTradeRowV1 }) {
  if (row.evidence.length === 0) return null;
  return (
    <ul className="space-y-0.5">
      {row.evidence.map((item, index) => (
        <li
          key={`${row.id}-${index}`}
          className="text-xs text-muted-foreground"
          data-testid="auto-no-trade-evidence"
        >
          {item.label}
          {item.ref ? (
            <>
              {" "}
              <Link
                to={autoOperacionHref(item.ref)}
                className="underline hover:text-primary"
                data-testid="auto-no-trade-evidence-link"
              >
                Ver operación
              </Link>
            </>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function LayerSection({ layer }: { layer: AutoNoTradeLayerV1 }) {
  return (
    <div
      className="space-y-1.5"
      data-testid="auto-no-trade-layer"
      data-layer={layer.id}
      data-measured={layer.measured ? "true" : "false"}
    >
      <p className={cn("font-medium", AUTO_USER_TEXT)}>{layer.title}</p>
      <p className="text-xs text-muted-foreground">{layer.honestyNote}</p>
      <ol className="space-y-1.5" data-testid="auto-no-trade-rows">
        {layer.rows.map((row) => (
          <li
            key={row.id}
            className="rounded-md border border-border/60 px-3 py-2"
            data-testid="auto-no-trade-row"
            data-cause={row.id}
            data-status={row.status}
          >
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-1 inline-block size-1.5 shrink-0 rounded-full",
                  STATUS_DOT[row.status],
                )}
              />
              <span className={cn("font-medium", AUTO_USER_TEXT)}>
                {row.label}
              </span>
              <span
                className={cn(
                  "uppercase tracking-wide text-xs",
                  STATUS_TONE[row.status],
                )}
                data-testid="auto-no-trade-row-status"
              >
                {row.statusLabel}
              </span>
            </div>
            <EvidenceList row={row} />
          </li>
        ))}
      </ol>
    </div>
  );
}

export function AutoNoTradeExplanationView({
  explanation,
}: {
  explanation: AutoNoTradeExplanationV1;
}) {
  return (
    <section
      className="space-y-3"
      aria-labelledby="auto-no-trade-heading"
      data-testid="auto-no-trade-panel"
      data-has-cause={explanation.hasDeclaredCause ? "true" : "false"}
    >
      <div className="space-y-0.5">
        <h2
          id="auto-no-trade-heading"
          className={cn("font-semibold", AUTO_USER_TEXT)}
        >
          {AUTO_NO_TRADE_PANEL_TITLE}
        </h2>
        <p className="text-xs text-muted-foreground">
          {AUTO_NO_TRADE_PANEL_DESCRIPTION}
        </p>
        <p
          className={cn("font-medium", AUTO_USER_TEXT)}
          data-testid="auto-no-trade-headline"
        >
          {explanation.headline}
        </p>
      </div>
      {explanation.layers.map((layer) => (
        <LayerSection key={layer.id} layer={layer} />
      ))}
    </section>
  );
}

export function AutoNoTradePanel() {
  const { effectiveAccountId } = useActiveAccount();
  const { view, isLoading, isError } = useAutoOperationalMonitor();
  const blocked = useMesaEntriesBlocked();

  const dailyQuery = useQuery({
    queryKey: ["paper-desk-daily-report", effectiveAccountId, "auto-actividad"],
    queryFn: () =>
      api.getPaperDeskDailyReport(effectiveAccountId!, { asOf: todayIso() }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
  });

  const daily = dailyQuery.data?.data ?? null;

  const autoDesk: AutoNoTradeAutoDeskFacts | null = daily?.autoDesk
    ? {
        blocked: daily.autoDesk.blocked ?? null,
        blockReason: daily.autoDesk.blockReason ?? null,
        entry: daily.autoDesk.entry
          ? {
              status: daily.autoDesk.entry.status ?? null,
              proposed: daily.autoDesk.entry.proposed ?? null,
              executed: daily.autoDesk.entry.executed ?? null,
              candidates: daily.autoDesk.entry.candidates ?? null,
              skipped: daily.autoDesk.entry.skipped ?? null,
            }
          : null,
        jitDenies: daily.autoDesk.jitDenies ?? null,
      }
    : null;

  const gate: AutoNoTradeGateFacts = {
    killOn: blocked.killOn,
    vetoed: blocked.vetoed,
    incidentCount: blocked.incidentCount,
    incidentsFailed: blocked.incidentsFailed,
  };

  const engineCycles: AutoNoTradeCycleFacts[] = (view?.cycles ?? []).map(
    (cycle) => ({
      id: cycle.cycleId,
      closed: cycle.closed ?? null,
      closedMeasurement: cycle.closedMeasurement ?? null,
      resultClosedAt: cycle.result?.closedAt ?? null,
      steps: (cycle.steps ?? []).map((step) => ({
        id: step.id,
        state: step.state,
        measurement: step.measurement,
        note: step.note ?? null,
        at: step.at ?? null,
      })),
    }),
  );

  const explanation = buildAutoNoTradeExplanation({
    day: todayIso(),
    discovery: {
      loaded: dailyQuery.isSuccess && daily != null,
      estudioStatus: daily?.estudioStatus ?? null,
      estudioCount: daily?.estudioCount ?? null,
      autoDesk,
      gate,
    },
    engine: {
      loaded: !isLoading && !isError && view != null,
      cycles: engineCycles,
    },
  });

  return <AutoNoTradeExplanationView explanation={explanation} />;
}
