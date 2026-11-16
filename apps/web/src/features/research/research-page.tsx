/**
 * Contenedor de la puerta ASESOR (`/research`) — R5 (una sola puerta LAB).
 *
 * Solo lee la URL, decide la pestaña y monta los paneles. El Laboratorio del
 * Asesor es un **resumen corto**: estado + último experimento + CTA con
 * deep-link a `/backtests`. El historial de experimentos y la salud/cobertura de
 * métricas viven en `/backtests?tab=history` (`lab-research-section.tsx`).
 *
 * Compatibilidad: `?tab=history&trialId=…` (enlaces antiguos al detalle del
 * experimento) redirige al LAB conservando instrumento y experimento.
 *
 * @see docs/adr/040-user-information-architecture.md
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §6 (R5)
 */

import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { labHistoryHref } from "@/features/confirm/daily-nav";
import {
  AsesorHubTabsBar,
  isLabTab,
  parseTab,
  type HubTab,
} from "@/features/research/asesor-hub-tabs";
import { AsesorCarteraPanel } from "@/features/research/asesor-cartera-panel";
import { AsesorDailyOpsPanel } from "@/features/research/asesor-daily-ops-panel";
import { AsesorJournalBridge } from "@/features/research/asesor-journal-bridge";
import { AsesorOpinionesPanel } from "@/features/research/asesor-opiniones-panel";
import { LabSummaryPanel } from "@/features/research/lab-summary-panel";

/** Claves de la URL que solo tenían sentido cuando el historial vivía aquí. */
const LAB_FILTER_KEYS = [
  "trialId",
  "instrumentId",
  "proposedBy",
  "presetKey",
  "sort",
  "page",
] as const;

export function ResearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const onLabTab = isLabTab(tab);
  const trialId = searchParams.get("trialId");
  const instrumentId = searchParams.get("instrumentId") ?? "";

  const summaryQuery = useQuery({
    queryKey: ["research", "summary"],
    queryFn: api.getLaboratoryResearchSummary,
  });

  function setTab(next: HubTab) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", next);
    for (const key of LAB_FILTER_KEYS) nextParams.delete(key);
    setSearchParams(nextParams);
  }

  // Los enlaces antiguos al detalle del experimento siguen funcionando: el
  // ledger vive en el LAB, así que se redirige conservando instrumento y trial.
  if (onLabTab && trialId) {
    return <Navigate to={labHistoryHref(trialId, instrumentId)} replace />;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Asesor
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Capa de explicación: ¿por qué esta tesis, este riesgo, esta acción?
            No es una mesa de operaciones. Actuar en{" "}
            <Link
              to="/trading"
              className="text-primary underline hover:underline"
            >
              Mercado
            </Link>{" "}
            · excepciones en{" "}
            <Link to="/mesa" className="text-primary underline hover:underline">
              Hoy
            </Link>{" "}
            · firmar en Confirm. La experimentación vive en el{" "}
            <Link
              to={labHistoryHref()}
              className="text-primary underline hover:underline"
            >
              Laboratorio
            </Link>
            .
          </p>
        </div>
        <Link
          to="/decision-journal"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          Journal
        </Link>
      </div>

      <AsesorHubTabsBar tab={tab} onTab={setTab} />

      {tab === "cartera" && <AsesorCarteraPanel />}

      {tab === "diario" && <AsesorDailyOpsPanel />}

      {tab === "opiniones" && <AsesorOpinionesPanel />}

      {tab === "journal" && <AsesorJournalBridge />}

      {onLabTab && (
        <LabSummaryPanel
          summaryQuery={summaryQuery}
          instrumentId={instrumentId}
        />
      )}
    </div>
  );
}
