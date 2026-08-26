/**
 * P4 — barra operativa: estado global mesa (read-only) + VS-1 venue Paper|Live.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deriveMesaRegimeHint } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

type MesaOperationalBarProps = {
  /** Override; si omitido, se lee de portfolio. */
  positionsCount?: number;
  className?: string;
};

type BrokerVenue = "paper" | "live";

export function MesaOperationalBar({
  positionsCount: positionsCountProp,
  className,
}: MesaOperationalBarProps) {
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const qc = useQueryClient();

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: () => api.getAccountSummary(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    enabled: Boolean(accountScope),
    staleTime: 15_000,
  });

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId],
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });

  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: 15_000,
  });

  const venueQuery = useQuery({
    queryKey: ["broker-venue"],
    queryFn: () => api.getBrokerVenue(),
    staleTime: 15_000,
  });

  const venueMut = useMutation({
    mutationFn: (venue: BrokerVenue) => api.setBrokerVenue(venue),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["risk-kill-switch"] });
      void qc.invalidateQueries({ queryKey: ["broker-venue"] });
      void qc.invalidateQueries({ queryKey: ["ops-self-eval"] });
      void qc.invalidateQueries({ queryKey: ["account-broker-venue"] });
    },
  });

  const selfEvalQuery = useQuery({
    queryKey: ["ops-self-eval", effectiveAccountId],
    queryFn: () => api.getOpsSelfEval(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
  });

  const cash = summaryQuery.data?.data?.cash;
  const portfolio = portfolioQuery.data?.data;
  const board = boardQuery.data?.data;
  const positionsCount = positionsCountProp ?? portfolio?.positions.length ?? 0;
  const equity = portfolio?.totalEquity ?? summaryQuery.data?.data?.totalEquity;
  const unrealized =
    portfolio?.totalUnrealizedPnl ??
    summaryQuery.data?.data?.totalUnrealizedPnl;
  const pendingConfirm = board?.buckets?.pendingConfirm ?? 0;
  const deferred = board?.buckets?.deferred ?? 0;
  const autoWaiting = board?.buckets?.autoWaiting ?? 0;
  const exceptions = deferred + autoWaiting;
  const regimeHint = board ? deriveMesaRegimeHint(board) : null;
  const vetoed = board?.buckets?.vetoed ?? 0;
  const killOn = killQuery.data?.effective === true;
  const brokerVenue: BrokerVenue =
    killQuery.data?.brokerVenue ?? venueQuery.data?.brokerVenue ?? "paper";
  const semiMark = selfEvalQuery.data?.lanes?.semi?.mark ?? null;
  const autoMark = selfEvalQuery.data?.lanes?.auto?.mark ?? null;
  const readinessState =
    selfEvalQuery.data?.operationalReadiness?.state ?? null;
  const readinessReasons =
    selfEvalQuery.data?.operationalReadiness?.reasons ?? [];

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs",
        className,
      )}
      data-testid="mesa-operational-bar"
    >
      {regimeHint ? (
        <span className="text-muted-foreground" title="Hint régimen / mesa">
          Mercado{" "}
          <span className="font-medium capitalize text-foreground">
            {regimeHint}
          </span>
        </span>
      ) : null}
      <span className="text-muted-foreground">
        Caja{" "}
        <span className="font-medium tabular-nums text-foreground">
          {cash != null ? formatPrice(cash) : "—"}
        </span>
      </span>
      <span className="text-muted-foreground">
        Patrimonio{" "}
        <span className="font-medium tabular-nums text-foreground">
          {equity != null ? formatPrice(equity) : "—"}
        </span>
      </span>
      <span className="text-muted-foreground">
        P&amp;L{" "}
        <span
          className={cn(
            "font-medium tabular-nums",
            unrealized != null && unrealized >= 0
              ? "text-emerald-700 dark:text-emerald-300"
              : unrealized != null
                ? "text-rose-700 dark:text-rose-300"
                : "text-foreground",
          )}
        >
          {unrealized != null ? formatPrice(unrealized) : "—"}
        </span>
      </span>
      <span className="text-muted-foreground">
        Posiciones{" "}
        <span className="font-medium tabular-nums text-foreground">
          {positionsCount}
        </span>
      </span>
      <div
        className="inline-flex items-center gap-0.5"
        data-testid="mesa-broker-venue"
        title="Venue de ejecución: Paper = simulación; Live = XTB bridge (sin URL → not_wired; submitted ≠ fill salvo filled)"
      >
        <span className="mr-1 text-muted-foreground">Venue</span>
        {(["paper", "live"] as const).map((v) => {
          const active = brokerVenue === v;
          return (
            <button
              key={v}
              type="button"
              disabled={venueMut.isPending}
              className={cn(
                "rounded border px-1.5 py-0.5 text-[10px] font-medium capitalize",
                active
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground opacity-60",
              )}
              title={
                v === "live"
                  ? "Live = XTB bridge; sin URL → not_wired; submitted ≠ fill unless filled"
                  : "Paper = PaperBroker (simulación ledger)"
              }
              onClick={() => {
                if (!active) venueMut.mutate(v);
              }}
              data-testid={`mesa-broker-venue-${v}`}
            >
              {v === "paper" ? "Paper" : "Live"}
            </button>
          );
        })}
      </div>
      {pendingConfirm > 0 ? (
        <span
          className="rounded bg-sky-500/15 px-1.5 py-0.5 font-medium text-sky-900 dark:text-sky-100"
          title="Tickets en cola Confirm supervisada"
        >
          Confirm ({pendingConfirm})
        </span>
      ) : (
        <span className="text-muted-foreground">Confirm 0</span>
      )}
      {exceptions > 0 ? (
        <span
          className="rounded bg-orange-500/15 px-1.5 py-0.5 font-medium text-orange-900 dark:text-orange-100"
          title="Sesiones diferidas o auto en espera"
        >
          Excepciones ({exceptions})
        </span>
      ) : null}
      {killOn ? (
        <span
          className="rounded bg-rose-500/15 px-1.5 py-0.5 font-medium text-rose-800 dark:text-rose-200"
          title="Kill switch activo: bloquea aperturas y AUTO; desriesgo SEMI permitido"
        >
          Kill switch ON
        </span>
      ) : (
        <span className="text-muted-foreground">Kill switch off</span>
      )}
      {vetoed > 0 ? (
        <span
          className="rounded bg-amber-500/15 px-1.5 py-0.5 font-medium text-amber-900 dark:text-amber-200"
          title="Entradas con gate VETO en el Decision Board"
        >
          Veto entradas ({vetoed})
        </span>
      ) : (
        <span className="text-muted-foreground">Sin veto global</span>
      )}
      <span
        className="rounded border border-border px-1.5 py-0.5 font-medium text-foreground"
        data-testid="mesa-ops-self-eval"
        title="OE-1 Autoeval SEMI vs AUTO (read-only). Rojo ≠ permiso thaw. measure ≠ Accept."
      >
        Autoeval{" "}
        <span className="text-muted-foreground">
          SEMI {semiMark ?? "…"} · AUTO {autoMark ?? "…"}
        </span>
      </span>
      <span
        className={cn(
          "rounded border px-1.5 py-0.5 font-medium",
          readinessState === "PAPER_READY"
            ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-200"
            : readinessState === "LIVE_EXPERIMENTAL"
              ? "border-sky-500/40 text-sky-900 dark:text-sky-100"
              : readinessState === "LIVE_BLOCKED"
                ? "border-rose-500/40 text-rose-800 dark:text-rose-200"
                : "border-amber-500/40 text-amber-900 dark:text-amber-200",
        )}
        data-testid="mesa-operational-readiness"
        title={
          readinessReasons.length > 0
            ? `OR-6 readiness (no se promedia). ${readinessReasons.join(" · ")}`
            : "OR-6 SEMI certification. Un FAIL crítico no es un % listo. LIVE nunca accepted."
        }
      >
        {readinessState ?? "Readiness …"}
      </span>
    </div>
  );
}
