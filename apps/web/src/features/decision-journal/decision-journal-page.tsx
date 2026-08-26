/**
 * Decision Journal 2.0 — Tesis (vista) + Historial técnico (ADR-029).
 * Solo lectura. No muta TradePlan ni journal.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { JournalTimeline } from "@/features/decision-journal/journal-timeline";
import {
  DEFAULT_JOURNAL_STUDY_FILTERS,
  JournalStudiesFilters,
  type JournalStudyFilters,
} from "@/features/decision-journal/journal-studies-filters";
import { JournalStudiesTable } from "@/features/decision-journal/journal-studies-table";
import { DecisionFichaPanel } from "@/features/decision-journal/decision-ficha-panel";

type JournalTab = "tesis" | "historial";

export function DecisionJournalPage() {
  const { effectiveAccountId } = useActiveAccount();
  const [tab, setTab] = useState<JournalTab>("tesis");
  const [filters, setFilters] = useState<JournalStudyFilters>(
    DEFAULT_JOURNAL_STUDY_FILTERS,
  );
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selected, setSelected] = useState<DecisionJournalStudyViewV1 | null>(
    null,
  );
  const [fichaCollapsed, setFichaCollapsed] = useState(false);
  const [listPct, setListPct] = useState(62);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQ(filters.q), 250);
    return () => window.clearTimeout(handle);
  }, [filters.q]);

  const listsQuery = useQuery({
    queryKey: ["lists"],
    queryFn: () => api.getLists(),
  });

  const studiesQuery = useQuery({
    queryKey: [
      "decision-studies",
      effectiveAccountId,
      filters.listId,
      debouncedQ,
      filters.period,
      filters.opinion,
      filters.status,
      filters.strengthBand,
      filters.dateFrom,
      filters.dateTo,
    ],
    enabled: Boolean(effectiveAccountId) && tab === "tesis",
    queryFn: () =>
      api.getDecisionStudies(effectiveAccountId!, {
        listId: filters.listId === "todas" ? undefined : filters.listId,
        q: debouncedQ.trim() || undefined,
        period: filters.period === "all" ? undefined : filters.period,
        opinion: filters.opinion === "all" ? undefined : filters.opinion,
        status: filters.status === "all" ? undefined : filters.status,
        strengthBand:
          filters.strengthBand === "all" ? undefined : filters.strengthBand,
        from: filters.dateFrom
          ? `${filters.dateFrom}T00:00:00.000Z`
          : undefined,
        to: filters.dateTo ? `${filters.dateTo}T23:59:59.000Z` : undefined,
      }),
    refetchInterval: 60_000,
  });

  const journalQuery = useQuery({
    queryKey: ["decision-journal", effectiveAccountId],
    enabled: Boolean(effectiveAccountId) && tab === "historial",
    queryFn: () => api.getDecisionJournal(effectiveAccountId!),
    refetchInterval: 60_000,
  });

  const studies = studiesQuery.data?.data.studies ?? [];
  const journal = journalQuery.data?.data;
  const lists = useMemo(
    () =>
      (listsQuery.data?.data ?? []).map((item) => ({
        id: item.id,
        name: item.name,
      })),
    [listsQuery.data],
  );

  const showFicha = Boolean(selected) && !fichaCollapsed;

  return (
    <div
      className="flex min-h-0 flex-1 flex-col space-y-3 p-4 sm:p-6"
      data-testid="decision-journal"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
            Decision Journal
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Seguimiento de análisis y tesis
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            void studiesQuery.refetch();
            void journalQuery.refetch();
          }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Actualizar
        </Button>
      </div>

      <div className="flex gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
        <button
          type="button"
          data-testid="tab-tesis"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            tab === "tesis"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
          onClick={() => setTab("tesis")}
        >
          Tesis
        </button>
        <button
          type="button"
          data-testid="tab-historial"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            tab === "historial"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
          onClick={() => setTab("historial")}
        >
          Historial técnico
        </button>
      </div>

      {tab === "tesis" ? (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <JournalStudiesFilters
            value={filters}
            onChange={setFilters}
            lists={lists}
          />

          {studiesQuery.isLoading && studies.length === 0 ? (
            <p className="text-sm text-muted-foreground">Cargando tesis…</p>
          ) : null}

          {studiesQuery.isError ? (
            <Card className="rounded-xl border-destructive/40 bg-destructive/5 p-4">
              <p
                className="text-sm text-destructive"
                data-testid="studies-error"
              >
                No se pudo cargar las tesis. Revisa la API.
              </p>
            </Card>
          ) : null}

          <div className="flex min-h-[28rem] flex-1 overflow-hidden rounded-xl border border-border">
            <div
              className="min-w-0 overflow-auto"
              style={{ width: showFicha ? `${listPct}%` : "100%" }}
            >
              <JournalStudiesTable
                studies={studies}
                selectedSessionId={selected?.sessionId ?? null}
                onSelect={(study) => {
                  setSelected(study);
                  setFichaCollapsed(false);
                }}
              />
            </div>
            {selected && fichaCollapsed ? (
              <button
                type="button"
                className="w-8 border-l border-border bg-muted/30 text-[10px] text-muted-foreground"
                onClick={() => setFichaCollapsed(false)}
                aria-label="Mostrar ficha"
              >
                Ficha
              </button>
            ) : null}
            {showFicha && selected ? (
              <>
                <PanelResizeHandle
                  label="Redimensionar ficha"
                  onDrag={(delta) => {
                    const root = 900;
                    setListPct((pct) =>
                      Math.min(78, Math.max(36, pct + (delta / root) * 100)),
                    );
                  }}
                />
                <div
                  className="min-h-0 min-w-0"
                  style={{ width: `${100 - listPct}%` }}
                >
                  <DecisionFichaPanel
                    study={selected}
                    onClose={() => setSelected(null)}
                    onCollapse={() => setFichaCollapsed(true)}
                  />
                </div>
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <>
          {journalQuery.isLoading && !journal ? (
            <p className="text-sm text-muted-foreground">Cargando…</p>
          ) : null}
          {journalQuery.isError ? (
            <Card className="rounded-xl border-destructive/40 bg-destructive/5 p-4">
              <p
                className="text-sm text-destructive"
                data-testid="journal-error"
              >
                No se pudo cargar el Decision Journal. Revisa la API.
              </p>
            </Card>
          ) : null}
          {journal ? (
            <>
              <Card
                className="rounded-xl border-border bg-card px-4 py-3"
                data-testid="journal-meta"
              >
                <p className="text-xs text-muted-foreground">
                  Cuenta{" "}
                  <code className="text-[10px]">{journal.accountId}</code>
                  {" · "}
                  {journal.total} entrada{journal.total === 1 ? "" : "s"}
                  {journal.total > journal.entries.length
                    ? ` (mostrando ${journal.entries.length})`
                    : null}
                </p>
              </Card>
              <JournalTimeline entries={journal.entries} />
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
