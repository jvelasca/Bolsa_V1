/**
 * F0.6 — Decision Board (web, solo lectura).
 *
 * Tablero de oportunidades pendientes del "Decision Spine": cola SEMI_F3 por
 * confirmar + decision sessions con su gate (PASS/VETO/DEFERRED/unknown).
 * NO escribe ni confirma nada: se limita a `GET /api/accounts/{account_id}/decision-board`.
 *
 * @see apps/api-python/src/bolsa_api/schemas/accounts.py (DecisionBoardDto)
 */

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { KeyValueList, KeyValueRow } from "@/components/ui/key-value-list";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import type { DecisionBoardV1, DecisionGate } from "@bolsa/shared";

function gateBadgeClasses(gate: string): string {
  switch (gate.toUpperCase() as DecisionGate) {
    case "VETO":
      return "bg-rose-500/15 text-rose-800 dark:text-rose-200";
    case "PASS":
      return "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
    case "DEFERRED":
      return "bg-amber-500/15 text-amber-900 dark:text-amber-200";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function BucketKpis({ buckets }: { buckets: DecisionBoardV1["buckets"] }) {
  const items: { label: string; value: number; className?: string }[] = [
    { label: "Por confirmar", value: buckets.pendingConfirm },
    { label: "Vetadas", value: buckets.vetoed },
    { label: "Diferidas", value: buckets.deferred },
    { label: "Auto en espera", value: buckets.autoWaiting },
    { label: "Total", value: buckets.total, className: "border-primary/40" },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((it) => (
        <Card
          key={it.label}
          data-testid={`bucket-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
          className={cn(
            "rounded-lg border-white/10 bg-black/20 px-3 py-2 backdrop-blur-sm",
            it.className,
          )}
        >
          <p className="text-[10px] uppercase tracking-wide text-white/60">
            {it.label}
          </p>
          <p className="mt-0.5 text-lg font-semibold tabular-nums text-white">
            {it.value}
          </p>
        </Card>
      ))}
    </div>
  );
}

function GateBadge({ gate }: { gate: string }) {
  return (
    <span
      data-testid={`gate-${gate.toUpperCase()}`}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        gateBadgeClasses(gate),
      )}
    >
      {gate}
    </span>
  );
}

function SemiF3QueueCard({ queue }: { queue: DecisionBoardV1["semiF3Queue"] }) {
  return (
    <Card className="rounded-xl border border-border bg-card">
      <CardHeader>
        <CardTitle className="text-sm">Cola SEMI_F3</CardTitle>
        <CardDescription>
          Oportunidades pendientes de confirmación.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {queue.length === 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="semi-f3-empty"
          >
            Sin confirmaciones pendientes.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {queue.map((q, i) => (
              <li
                key={q.instrumentId ?? q.symbol ?? `semi-${i}`}
                data-testid="semi-f3-item"
                className="flex items-center justify-between gap-2 border-b border-border/50 py-1 text-[11px] last:border-0"
              >
                <span className="font-medium text-foreground">
                  {q.symbol ?? q.instrumentId ?? "—"}
                </span>
                <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sky-800 dark:text-sky-200">
                  {q.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function DecisionSessionsCard({
  sessions,
}: {
  sessions: DecisionBoardV1["decisionSessions"];
}) {
  return (
    <Card className="rounded-xl border border-border bg-card">
      <CardHeader>
        <CardTitle className="text-sm">Decision sessions</CardTitle>
        <CardDescription>
          Sesiones recientes y su resultado de gate.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessions.length === 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="sessions-empty"
          >
            Sin decisiones recientes.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {sessions.map((s) => (
              <li
                key={s.sessionId}
                data-testid="decision-session-item"
                className="border-b border-border/50 py-1 text-[11px] last:border-0"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-foreground">
                    {s.symbol ?? s.instrumentId}
                  </span>
                  <GateBadge gate={s.gate} />
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-muted-foreground">
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[9px] uppercase">
                    {s.kind}
                  </span>
                  <span>{s.status}</span>
                  <span className="tabular-nums">
                    {formatDateTime(s.createdAt)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function DecisionBoardPage() {
  const { effectiveAccountId } = useActiveAccount();

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    enabled: Boolean(effectiveAccountId),
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    refetchInterval: 60_000,
  });

  const board = boardQuery.data?.data;

  return (
    <div className="space-y-4 p-4 sm:p-6" data-testid="decision-board">
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Decision Board
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tablero de solo lectura de oportunidades pendientes del Decision
          Spine.
        </p>
      </div>

      {boardQuery.isLoading && !board ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : null}

      {boardQuery.isError ? (
        <Card className="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
          <p className="text-sm text-destructive" data-testid="board-error">
            No se pudo cargar el Decision Board. Revisa la API.
          </p>
        </Card>
      ) : null}

      {board ? (
        <>
          <Card
            className="rounded-xl border-border bg-card p-4"
            data-testid="board-buckets"
          >
            <BucketKpis buckets={board.buckets} />
            {(board.equity != null || board.freeMargin != null) && (
              <KeyValueList className="mt-4">
                {board.equity != null && (
                  <KeyValueRow label="Equity">
                    {formatPrice(board.equity)}
                  </KeyValueRow>
                )}
                {board.freeMargin != null && (
                  <KeyValueRow label="Margen libre">
                    {formatPrice(board.freeMargin)}
                  </KeyValueRow>
                )}
              </KeyValueList>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <SemiF3QueueCard queue={board.semiF3Queue} />
            <DecisionSessionsCard sessions={board.decisionSessions} />
          </div>
        </>
      ) : null}

      {!boardQuery.isLoading &&
      !boardQuery.isError &&
      board &&
      board.semiF3Queue.length === 0 &&
      board.decisionSessions.length === 0 ? (
        <Card className="rounded-xl border border-dashed p-4">
          <p className="text-sm text-muted-foreground">
            Sin decisiones pendientes.
          </p>
        </Card>
      ) : null}
    </div>
  );
}
