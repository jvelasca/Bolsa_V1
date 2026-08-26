/**
 * Timeline ADR-029 — Historial técnico del Decision Journal (solo lectura).
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
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
        <details className="mt-1">
          <summary
            className="cursor-pointer text-[10px] text-foreground/60"
            data-testid="journal-technical-details"
          >
            Información técnica
          </summary>
          <div className="mt-1 space-y-0.5">
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
              <pre className="mt-1 max-h-32 overflow-auto rounded bg-muted/50 p-2 text-[9px]">
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            ) : null}
          </div>
        </details>
      </div>
    </li>
  );
}

export function JournalTimeline({
  entries,
}: {
  entries: DecisionJournalEntryV1[];
}) {
  return (
    <Card className="rounded-xl border border-border bg-card">
      <CardHeader>
        <CardTitle className="text-sm">Historial técnico</CardTitle>
        <CardDescription>
          Audit trail append-only. IDs y payload bajo información técnica.
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
