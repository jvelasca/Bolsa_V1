/**
 * F3 — Decision Journal (web, solo lectura).
 *
 * Timeline cronológico del audit trail append-only del Decision Spine.
 * NO escribe ni confirma nada: se limita a `GET /api/accounts/{account_id}/decision-journal`.
 *
 * @see packages/shared/src/cognitive/decision-journal.ts (DecisionJournalEntryV1)
 */

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import type { DecisionJournalEntryV1 } from "@bolsa/shared";
import {
  actorBadgeClasses,
  eventTypeBadgeClasses,
  formatEventTypeLabel,
  formatJournalDateTime,
  formatJournalSetupLine,
  openDecisionReplay,
} from "@/features/decision-journal/decision-journal-helpers";

function EventTypeBadge({ eventType }: { eventType: string }) {
  return (
    <span
      data-testid={`event-${eventType}`}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        eventTypeBadgeClasses(eventType),
      )}
    >
      {formatEventTypeLabel(eventType)}
    </span>
  );
}

function ActorBadge({ actor }: { actor: string }) {
  return (
    <span
      data-testid={`actor-${actor}`}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        actorBadgeClasses(actor),
      )}
    >
      {actor}
    </span>
  );
}

function JournalEntryRow({ entry }: { entry: DecisionJournalEntryV1 }) {
  const hasSession = Boolean(entry.sessionId?.trim());
  const setupLine = formatJournalSetupLine(entry.payload);

  return (
    <li
      data-testid="journal-entry"
      data-entry-id={entry.entryId}
      className="relative border-l-2 border-border/60 pl-4 pb-4 last:pb-0"
    >
      <span
        className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-primary"
        aria-hidden
      />
      <div className="flex flex-wrap items-center gap-2">
        <EventTypeBadge eventType={entry.eventType} />
        <ActorBadge actor={entry.actor} />
        <span className="text-[10px] tabular-nums text-muted-foreground">
          {formatJournalDateTime(entry.createdAt)}
        </span>
      </div>
      <div className="mt-1.5 space-y-0.5 text-[11px] text-muted-foreground">
        {setupLine ? (
          <p data-testid="journal-setup">
            <span className="text-foreground/70">Setup:</span> {setupLine}
          </p>
        ) : null}
        <p>
          <span className="text-foreground/70">decisionId:</span>{" "}
          <code className="text-[10px]">{entry.decisionId}</code>
        </p>
        {entry.instrumentId ? (
          <p>
            <span className="text-foreground/70">instrumentId:</span>{" "}
            <code className="text-[10px]">{entry.instrumentId}</code>
          </p>
        ) : null}
        {hasSession ? (
          <p className="flex flex-wrap items-center gap-1">
            <span className="text-foreground/70">sessionId:</span>{" "}
            <code className="text-[10px]">{entry.sessionId}</code>
            <button
              type="button"
              data-testid="open-replay"
              className="text-[10px] text-primary underline-offset-2 hover:underline"
              onClick={() => openDecisionReplay(entry.sessionId!)}
            >
              Abrir Replay
            </button>
          </p>
        ) : null}
        {entry.payload && Object.keys(entry.payload).length > 0 ? (
          <details className="mt-1">
            <summary className="cursor-pointer text-[10px] text-foreground/60">
              payload
            </summary>
            <pre className="mt-1 max-h-32 overflow-auto rounded bg-muted/50 p-2 text-[9px]">
              {JSON.stringify(entry.payload, null, 2)}
            </pre>
          </details>
        ) : null}
      </div>
    </li>
  );
}

function JournalTimeline({ entries }: { entries: DecisionJournalEntryV1[] }) {
  return (
    <Card className="rounded-xl border border-border bg-card">
      <CardHeader>
        <CardTitle className="text-sm">Timeline</CardTitle>
        <CardDescription>
          Transiciones registradas, más recientes primero.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="journal-empty"
          >
            Sin entradas en el journal para esta cuenta.
          </p>
        ) : (
          <ol className="space-y-0" data-testid="journal-timeline">
            {entries.map((entry) => (
              <JournalEntryRow key={entry.entryId} entry={entry} />
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

export function DecisionJournalPage() {
  const { effectiveAccountId } = useActiveAccount();

  const journalQuery = useQuery({
    queryKey: ["decision-journal", effectiveAccountId],
    enabled: Boolean(effectiveAccountId),
    queryFn: () => api.getDecisionJournal(effectiveAccountId!),
    refetchInterval: 60_000,
  });

  const journal = journalQuery.data?.data;

  return (
    <div className="space-y-4 p-4 sm:p-6" data-testid="decision-journal">
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Decision Journal
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Session = foto del razonamiento · Journal = historial de transiciones
        </p>
        <p className="mt-1 text-xs text-muted-foreground/80">
          Audit trail append-only del Decision Spine (solo lectura). Setup en
          payload cuando existe; Replay abre el outcome de sesión si hay
          sessionId.
        </p>
      </div>

      {journalQuery.isLoading && !journal ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : null}

      {journalQuery.isError ? (
        <Card className="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm text-destructive" data-testid="journal-error">
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
              Cuenta <code className="text-[10px]">{journal.accountId}</code>
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
    </div>
  );
}
