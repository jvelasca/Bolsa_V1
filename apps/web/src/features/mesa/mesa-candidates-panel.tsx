/**
 * Candidatos agrupados LISTOS / PREPARADOS / VIGILAR / BLOQUEADOS (NIVEL 5).
 */

import { Link } from "react-router-dom";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  type MesaCandidateRowV1,
} from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";

type CandidateGroup = {
  status: string;
  label: string;
  items: MesaCandidateRowV1[];
  entriesBlocked: boolean;
};

function CandidateCard({
  row,
  entriesBlocked,
}: {
  row: MesaCandidateRowV1;
  entriesBlocked: boolean;
}) {
  const study = row.study;
  const opinion =
    study?.opinion != null ? JOURNAL_STUDY_OPINION_LABELS[study.opinion] : "—";

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid={`mesa-candidate-${row.symbol}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{row.symbol}</p>
          <p className="text-xs text-muted-foreground">
            {row.statusLabel} · Gate {row.gate}
          </p>
        </div>
        {study?.strength != null ? (
          <span className="text-sm font-semibold tabular-nums">
            {study.strength.toFixed(1)}
          </span>
        ) : null}
      </div>
      <dl className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Opinión</dt>
          <dd>{opinion}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Vigencia</dt>
          <dd>
            {study?.vigencia
              ? JOURNAL_STUDY_VIGENCIA_LABELS[study.vigencia]
              : "—"}
          </dd>
        </div>
        {study?.hasOperationalPlan ? (
          <>
            <div>
              <dt className="text-muted-foreground">Entrada</dt>
              <dd>{study.entry != null ? formatPrice(study.entry) : "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Stop</dt>
              <dd>{study.stop != null ? formatPrice(study.stop) : "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">TP1</dt>
              <dd>
                {study.target1 != null ? formatPrice(study.target1) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">R/R</dt>
              <dd>
                {study.expectedRR != null
                  ? `1:${study.expectedRR.toFixed(2)}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Riesgo máx.</dt>
              <dd>
                {study.riskAmount != null ? formatPrice(study.riskAmount) : "—"}
              </dd>
            </div>
          </>
        ) : (
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">{NO_OPERATIONAL_PLAN_COPY}</p>
          </div>
        )}
      </dl>
      <div className="mt-2 flex flex-wrap gap-2">
        {row.instrumentId ? (
          <Link
            to={mesaJournalTesisHref(row.instrumentId, { ficha: true })}
            className="text-[11px] text-primary hover:underline"
          >
            Ver tesis
          </Link>
        ) : null}
        {row.status === "TRIGGERED" && !entriesBlocked ? (
          <Link
            to={CONFIRM_PATH}
            className="text-[11px] text-primary hover:underline"
          >
            Revisar propuesta
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export function MesaCandidatesPanel({
  groups,
  entriesBlocked,
}: {
  groups: CandidateGroup[];
  entriesBlocked: boolean;
}) {
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);

  return (
    <Card data-testid="mesa-candidates-panel">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Nuevas oportunidades</CardTitle>
        <CardDescription>
          {entriesBlocked ? (
            <span className="text-rose-600 dark:text-rose-400">
              Nuevas entradas: BLOQUEADAS
            </span>
          ) : (
            `${total} candidato${total === 1 ? "" : "s"} en cola`
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sin candidatos en cola — puede ser una buena decisión.
          </p>
        ) : (
          groups.map((group) => (
            <section
              key={group.status}
              data-testid={`mesa-group-${group.status}`}
            >
              <h3
                className={cn(
                  "mb-2 text-xs font-semibold uppercase tracking-wide",
                  group.status === "BLOCKED"
                    ? "text-rose-600"
                    : group.status === "TRIGGERED"
                      ? "text-emerald-700 dark:text-emerald-300"
                      : "text-muted-foreground",
                )}
              >
                {group.label} ({group.items.length})
              </h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {group.items.map((row) => (
                  <CandidateCard
                    key={`${row.symbol}-${row.status}`}
                    row={row}
                    entriesBlocked={entriesBlocked}
                  />
                ))}
              </div>
            </section>
          ))
        )}
      </CardContent>
    </Card>
  );
}
