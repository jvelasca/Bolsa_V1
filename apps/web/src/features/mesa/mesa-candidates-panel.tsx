/**
 * Candidatos agrupados + ranking operable + what-if (V1.16–V1.19).
 */

import { Link } from "react-router-dom";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  mapCandidateNextAction,
  sortMesaCandidatesOperable,
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
import { MesaWhatIfPanel } from "@/features/mesa/mesa-what-if-panel";

type CandidateGroup = {
  status: string;
  label: string;
  items: MesaCandidateRowV1[];
  entriesBlocked: boolean;
};

function CandidateNextAction({
  row,
  entriesBlocked,
}: {
  row: MesaCandidateRowV1;
  entriesBlocked: boolean;
}) {
  const next = mapCandidateNextAction(row, entriesBlocked);

  if (next.kind === "review_proposal") {
    return (
      <Link
        to={CONFIRM_PATH}
        className="text-[11px] font-medium text-primary hover:underline"
        data-testid={`mesa-candidate-cta-${row.symbol}`}
      >
        {next.label}
      </Link>
    );
  }
  if (next.kind === "view_thesis" && row.instrumentId) {
    return (
      <Link
        to={mesaJournalTesisHref(row.instrumentId, { ficha: true })}
        className="text-[11px] font-medium text-primary hover:underline"
        data-testid={`mesa-candidate-cta-${row.symbol}`}
      >
        {next.label}
      </Link>
    );
  }
  if (next.kind === "watch") {
    return (
      <span
        className="text-[11px] text-muted-foreground"
        data-testid={`mesa-candidate-cta-${row.symbol}`}
      >
        {next.label}
      </span>
    );
  }
  if (row.instrumentId) {
    return (
      <Link
        to={mesaJournalTesisHref(row.instrumentId, { ficha: true })}
        className="text-[11px] text-primary hover:underline"
      >
        Ver tesis
      </Link>
    );
  }
  return null;
}

function CandidateCard({
  row,
  entriesBlocked,
  portfolioRiskR,
  equity,
  cash,
  operableRank,
}: {
  row: MesaCandidateRowV1;
  entriesBlocked: boolean;
  portfolioRiskR: number | null;
  equity: number | null;
  cash: number | null;
  operableRank?: number;
}) {
  const study = row.study;
  const opinion =
    study?.opinion != null ? JOURNAL_STUDY_OPINION_LABELS[study.opinion] : "—";
  const score = sortMesaCandidatesOperable([row], entriesBlocked)[0]
    ?.operableScore;

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid={`mesa-candidate-${row.symbol}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {operableRank != null ? `#${operableRank} ` : ""}
            {row.symbol}
          </p>
          <p className="text-xs text-muted-foreground">
            {row.statusLabel} · Gate {row.gate}
          </p>
        </div>
        <div className="text-right">
          {study?.strength != null ? (
            <span className="text-sm font-semibold tabular-nums">
              {study.strength.toFixed(1)}
            </span>
          ) : null}
          {score?.operable ? (
            <p className="text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
              OPERABLE
            </p>
          ) : null}
        </div>
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
          </>
        ) : (
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">{NO_OPERATIONAL_PLAN_COPY}</p>
          </div>
        )}
      </dl>
      {!score?.operable && (score?.blockReasons.length ?? 0) > 0 ? (
        <p className="mt-1 text-[10px] text-amber-800 dark:text-amber-200">
          No operable: {score?.blockReasons.join(" · ")}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <CandidateNextAction row={row} entriesBlocked={entriesBlocked} />
        <MesaWhatIfPanel
          row={row}
          portfolioRiskR={portfolioRiskR}
          equity={equity}
          cash={cash}
        />
      </div>
    </div>
  );
}

export function MesaCandidatesPanel({
  groups,
  entriesBlocked,
  portfolioRiskR = null,
  equity = null,
  cash = null,
  useOperableRanking = true,
}: {
  groups: CandidateGroup[];
  entriesBlocked: boolean;
  portfolioRiskR?: number | null;
  equity?: number | null;
  cash?: number | null;
  useOperableRanking?: boolean;
}) {
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  const allRows = groups.flatMap((g) => g.items);
  const operableOrder = useOperableRanking
    ? sortMesaCandidatesOperable(allRows, entriesBlocked)
    : null;
  const rankBySymbol = new Map<string, number>();
  operableOrder?.forEach((row, i) => {
    if (row.operableScore.operable) rankBySymbol.set(row.symbol, i + 1);
  });

  const readyCount =
    groups.find((g) => g.status === "TRIGGERED")?.items.length ?? 0;

  return (
    <Card data-testid="mesa-candidates-panel">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Oportunidades operables</CardTitle>
        <CardDescription>
          {entriesBlocked ? (
            <span className="text-rose-600 dark:text-rose-400">
              Nuevas entradas: BLOQUEADAS
            </span>
          ) : readyCount > 0 ? (
            `Hoy: ${readyCount} operación${readyCount === 1 ? "" : "es"} posible${readyCount === 1 ? "" : "s"}`
          ) : (
            `${total} candidato${total === 1 ? "" : "s"} en cola`
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.length === 0 ? (
          <div
            className="rounded-md border border-dashed border-border/60 px-4 py-6 text-center"
            data-testid="mesa-no-operations"
          >
            <p className="font-medium">Hoy no hay operaciones recomendadas</p>
            <p className="mt-1 text-sm text-muted-foreground">
              La decisión correcta puede ser no operar.
            </p>
          </div>
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
                    portfolioRiskR={portfolioRiskR}
                    equity={equity}
                    cash={cash}
                    operableRank={rankBySymbol.get(row.symbol)}
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
