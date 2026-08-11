/**
 * Outcomes / Learning compacto en Operativa → Info (5b).
 * DecisionSession learning del valor activo × cuenta — no es el dictamen diario.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAlertsStore } from "@/stores/alerts-store";
import { cn } from "@/lib/utils";

function formatShort(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

function hitRateLabel(rate: number | null | undefined): string {
  if (rate == null || !Number.isFinite(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

export function OperativaOutcomesBlock({
  instrumentId,
  accountId,
  symbol,
  className,
}: {
  instrumentId: string;
  accountId: string | null | undefined;
  symbol: string;
  className?: string;
}) {
  const qc = useQueryClient();
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enabled = Boolean(accountId && instrumentId);

  const learningQuery = useQuery({
    queryKey: ["decision-learning", accountId, instrumentId],
    queryFn: () =>
      api.getDecisionSessionLearningSummary({
        accountId: accountId!,
        instrumentId,
        limit: 40,
      }),
    enabled,
    staleTime: 60_000,
  });

  const sessionsQuery = useQuery({
    queryKey: ["decision-sessions", accountId, instrumentId],
    queryFn: () =>
      api.listDecisionSessions({
        accountId: accountId!,
        instrumentId,
        limit: 8,
      }),
    enabled,
    staleTime: 30_000,
  });

  const closeOutcome = useMutation({
    mutationFn: (sessionId: string) =>
      api.closeDecisionSessionOutcome(sessionId, { mode: "auto" }),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["decision-sessions", accountId, instrumentId],
      });
      void qc.invalidateQueries({
        queryKey: ["decision-learning", accountId, instrumentId],
      });
      pushToast(`Outcome cerrado · ${symbol}`);
    },
    onError: (e: Error) => {
      pushToast(`Outcome · ${e.message}`);
    },
  });

  const learning = learningQuery.data?.data;
  const sessions = sessionsQuery.data?.data ?? [];

  if (!accountId) {
    return (
      <p className={cn("text-[10px] text-muted-foreground", className)}>
        Sin cuenta activa para Learning.
      </p>
    );
  }

  return (
    <div
      className={cn("space-y-1.5 border-t border-border/50 pt-1.5", className)}
      data-testid="operativa-outcomes"
    >
      <div className="space-y-0.5">
        <p className="font-medium text-foreground">Resultados · {symbol}</p>
        <p className="text-[10px] leading-snug text-muted-foreground">
          Historial de decisiones Confirm de este valor (aprendizaje). No es el
          dictamen del día de arriba.
        </p>
      </div>

      {learningQuery.isLoading ? (
        <p className="text-[10px] text-muted-foreground">
          Cargando resultados…
        </p>
      ) : learning ? (
        <p
          className="text-[10px] text-muted-foreground"
          data-testid="operativa-learning-strip"
        >
          Cerradas {learning.sampleClosed}
          {learning.matureScored != null
            ? ` · maduras ${learning.matureScored}`
            : ""}
          {" · acierto "}
          {hitRateLabel(learning.matureHitRate ?? learning.hitRate)}
          {learning.hits != null && learning.misses != null
            ? ` · H/M ${learning.hits}/${learning.misses}`
            : ""}
          {learning.prematureScored != null && learning.prematureScored > 0
            ? ` · prematuros ${learning.prematureScored}`
            : ""}
        </p>
      ) : (
        <p className="text-[10px] text-muted-foreground">Sin resumen aún.</p>
      )}

      {sessions.length > 0 ? (
        <ul className="max-h-28 space-y-0.5 overflow-y-auto text-[10px]">
          {sessions.map((s) => (
            <li
              key={s.sessionId}
              className="flex items-center justify-between gap-1 border-b border-border/30 py-0.5 last:border-0"
            >
              <span className="min-w-0 truncate text-muted-foreground">
                {formatShort(s.createdAt)} · {s.kind} · {s.status}
              </span>
              {s.status === "open" ? (
                <button
                  type="button"
                  className="shrink-0 rounded border border-border px-1 py-0.5 text-primary hover:bg-accent disabled:opacity-50"
                  disabled={closeOutcome.isPending}
                  onClick={() => closeOutcome.mutate(s.sessionId)}
                >
                  Cerrar
                </button>
              ) : (
                <span className="shrink-0 text-muted-foreground">ok</span>
              )}
            </li>
          ))}
        </ul>
      ) : sessionsQuery.isLoading ? null : (
        <p className="text-[10px] text-muted-foreground">
          Aún no hay sesiones de este valor. En SEMI, cada Confirm crea una.
        </p>
      )}

      <button
        type="button"
        className="w-full rounded border border-border px-1.5 py-1 text-[10px] text-primary hover:bg-accent"
        onClick={() => {
          window.dispatchEvent(
            new CustomEvent("bolsa:open-help", {
              detail: { section: "value-analysis" },
            }),
          );
        }}
      >
        Replay completo (Ayuda)
      </button>
    </div>
  );
}
