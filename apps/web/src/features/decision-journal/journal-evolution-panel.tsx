import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  formatJournalStudyAge,
  type DecisionJournalStudyViewV1,
  type JournalStudyOpinion,
  type JournalStudyUserStatus,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { openDecisionReplay } from "@/features/decision-journal/decision-journal-helpers";
import { JournalStudyCompareCard } from "@/features/decision-journal/journal-study-compare-card";
import { JournalStudySparkline } from "@/features/decision-journal/journal-study-sparkline";

function formatStudiedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function hitRateLabel(rate: number | null | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

export function JournalEvolutionPanel({
  accountId,
  studiesCatalog,
  initialInstrumentId,
  onOpenHistorial,
}: {
  accountId: string;
  studiesCatalog: DecisionJournalStudyViewV1[];
  initialInstrumentId?: string | null;
  onOpenHistorial: (instrumentId: string) => void;
}) {
  const [manualInstrumentId, setManualInstrumentId] = useState<string | null>(
    null,
  );
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null,
  );

  const instrumentId =
    manualInstrumentId ??
    initialInstrumentId ??
    studiesCatalog[0]?.instrumentId ??
    "";

  useEffect(() => {
    if (initialInstrumentId) {
      setManualInstrumentId(null);
    }
  }, [initialInstrumentId]);

  const historyQuery = useQuery({
    queryKey: ["decision-study-history", accountId, instrumentId],
    enabled: Boolean(accountId && instrumentId),
    queryFn: () => api.getDecisionStudyHistory(accountId, instrumentId),
  });

  /** V2.07 — learning summary (SoT = decision_sessions, not journal). */
  const learningQuery = useQuery({
    queryKey: ["decision-learning", accountId, instrumentId, "journal"],
    enabled: Boolean(accountId && instrumentId),
    queryFn: () =>
      api.getDecisionSessionLearningSummary({
        accountId,
        instrumentId,
        limit: 40,
      }),
    staleTime: 60_000,
  });

  const studies = historyQuery.data?.data.studies ?? [];
  const meta = historyQuery.data?.data;
  const learning = learningQuery.data?.data;

  const selectedIndex = useMemo(() => {
    if (!selectedSessionId) return 0;
    const idx = studies.findIndex((s) => s.sessionId === selectedSessionId);
    return idx >= 0 ? idx : 0;
  }, [studies, selectedSessionId]);

  const selected = studies[selectedIndex] ?? null;
  const previous =
    selectedIndex >= 0 && selectedIndex < studies.length - 1
      ? studies[selectedIndex + 1]
      : null;

  const catalogOptions = useMemo(() => {
    const map = new Map<string, DecisionJournalStudyViewV1>();
    for (const row of studiesCatalog) {
      map.set(row.instrumentId, row);
    }
    return [...map.values()];
  }, [studiesCatalog]);

  return (
    <div
      className="flex min-h-0 flex-1 flex-col gap-3"
      data-testid="evolution-panel"
    >
      <Card className="rounded-xl border-border bg-card/60 px-3 py-2">
        <p className="text-xs text-muted-foreground">
          Memoria de la tesis — compara snapshots propose. El aprendizaje del
          motor (acierto / fallo) se muestra debajo; la fuente sigue siendo
          decision_sessions.
        </p>
        <label className="mt-2 flex flex-col gap-0.5 text-[10px] text-muted-foreground">
          Activo
          <select
            className="h-8 rounded-md border border-border bg-card px-2 text-xs text-foreground"
            value={instrumentId}
            onChange={(e) => {
              setManualInstrumentId(e.target.value);
              setSelectedSessionId(null);
            }}
            data-testid="evolution-instrument-select"
          >
            {catalogOptions.length === 0 ? (
              <option value="">Sin tesis en catálogo</option>
            ) : (
              catalogOptions.map((row) => (
                <option key={row.instrumentId} value={row.instrumentId}>
                  {row.symbol ?? row.instrumentId}
                  {row.name ? ` — ${row.name}` : ""}
                </option>
              ))
            )}
          </select>
        </label>
        {instrumentId ? (
          <p
            className="mt-2 text-[10px] text-muted-foreground"
            data-testid="journal-learning-strip"
          >
            {learningQuery.isLoading
              ? "Cargando resultados…"
              : learning
                ? `Resultados: cerradas ${learning.sampleClosed}${
                    learning.matureScored != null
                      ? ` · maduras ${learning.matureScored}`
                      : ""
                  } · acierto ${hitRateLabel(
                    learning.matureHitRate ?? learning.hitRate,
                  )} · H/M ${learning.hits ?? 0}/${learning.misses ?? 0}`
                : "Sin sesiones de aprendizaje para este valor aún."}
          </p>
        ) : null}
      </Card>

      {historyQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando evolución…</p>
      ) : null}

      {historyQuery.isError ? (
        <Card className="rounded-xl border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm text-destructive" data-testid="evolution-error">
            No se pudo cargar la evolución.
          </p>
        </Card>
      ) : null}

      {!historyQuery.isLoading && studies.length === 0 ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="evolution-empty"
        >
          No hay estudios propose para este activo.
        </p>
      ) : null}

      {studies.length > 0 ? (
        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <div className="min-h-0 space-y-3 overflow-auto rounded-xl border border-border p-3">
            <JournalStudySparkline studies={studies} />
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Versiones
            </p>
            <ul className="space-y-1" data-testid="evolution-version-list">
              {studies.map((study) => {
                const active = study.sessionId === (selected?.sessionId ?? "");
                const opinion = study.opinion
                  ? JOURNAL_STUDY_OPINION_LABELS[
                      study.opinion as JournalStudyOpinion
                    ]
                  : "—";
                const status =
                  JOURNAL_STUDY_STATUS_LABELS[
                    study.status as JournalStudyUserStatus
                  ] ?? study.status;
                return (
                  <li key={study.sessionId}>
                    <button
                      type="button"
                      data-testid="evolution-version-row"
                      className={cn(
                        "w-full rounded-md border px-2 py-1.5 text-left text-xs",
                        active
                          ? "border-primary/50 bg-primary/5"
                          : "border-border/60 hover:bg-muted/40",
                      )}
                      onClick={() => setSelectedSessionId(study.sessionId)}
                    >
                      <p className="font-medium">
                        {formatStudiedAt(study.studiedAt)}
                      </p>
                      <p className="text-muted-foreground">
                        {opinion} · {status}
                        {study.strength != null
                          ? ` · ${study.strength.toFixed(1)}/10`
                          : ""}
                        {study.ageMs != null
                          ? ` · ${formatJournalStudyAge(study.ageMs)}`
                          : ""}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="min-h-0 space-y-3 overflow-auto rounded-xl border border-border p-3">
            {selected ? (
              <>
                <div>
                  <p className="text-sm font-semibold">
                    {meta?.symbol ?? selected.symbol ?? selected.instrumentId}
                  </p>
                  {meta?.name ? (
                    <p className="text-xs text-muted-foreground">{meta.name}</p>
                  ) : null}
                  <p className="mt-1 text-xs text-muted-foreground">
                    Estudio {formatStudiedAt(selected.studiedAt)}
                  </p>
                </div>
                <JournalStudyCompareCard
                  prev={previous ?? null}
                  next={selected}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => openDecisionReplay(selected.sessionId)}
                  >
                    Abrir Replay
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onOpenHistorial(selected.instrumentId)}
                  >
                    Historial técnico del activo
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
