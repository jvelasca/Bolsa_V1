import { Link } from "react-router-dom";
import type { ResearchTrialDto } from "@bolsa/shared";
import {
  ASESOR_LABEL,
  VER_EN_ASESOR_LABEL,
  asesorHistoryHref,
} from "@/features/confirm/daily-nav";
import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { ResearchLabEvidenceSummary } from "@/features/research/research-lab-evidence-summary";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function metricNum(
  metrics: Record<string, number | string | null> | undefined,
  key: string,
): number | null {
  if (!metrics) return null;
  const v = metrics[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function formatMetric(
  v: number | null,
  kind: "ratio" | "pct" | "money" | "raw" = "ratio",
): string {
  if (v == null) return "—";
  if (kind === "pct") return formatPct(v);
  if (kind === "money") return formatPrice(v);
  if (kind === "raw") return String(Math.round(v * 1000) / 1000);
  return v.toFixed(2);
}

type Props = {
  trialId?: string | null;
  metrics?: Record<string, number | string | null> | null;
  /** Fallback from backtest run columns when metrics not in mutation payload */
  fallback?: {
    totalReturnPct?: number;
    maxDrawdownPct?: number;
    commissionBps?: number | null;
    slippageBps?: number | null;
  };
  /** Optional full trial when loaded from Research API */
  trial?: ResearchTrialDto | null;
  className?: string;
};

export function ResearchTrialResultBlock({
  trialId,
  metrics,
  fallback,
  trial,
  className,
}: Props) {
  const id = trialId ?? trial?.id;
  const backtestRunId = trial?.backtestRunId ?? null;
  const m = metrics ?? trial?.isMetrics ?? {};
  const k = trial?.kContribution ?? 1;
  const preset =
    trial?.presetKey ??
    (typeof trial?.params?.presetKey === "string"
      ? trial.params.presetKey
      : null);
  const proposedBy = trial?.proposedBy ?? "human";

  const sharpe = metricNum(m, "sharpeRatio");
  const sortino = metricNum(m, "sortinoRatio");
  const calmar = metricNum(m, "calmarRatio");
  const maxDd =
    metricNum(m, "maxDrawdownPct") ?? fallback?.maxDrawdownPct ?? null;
  const pnl =
    metricNum(m, "totalReturnPct") ?? fallback?.totalReturnPct ?? null;
  const buyHold = metricNum(m, "buyHoldReturnPct");
  const excess = metricNum(m, "excessReturnPct");
  const pf = metricNum(m, "profitFactor");
  const wr = metricNum(m, "winRate");
  const commission = metricNum(m, "totalCommission");
  const commissionBps =
    metricNum(m, "commissionBps") ?? fallback?.commissionBps ?? null;
  const slippageBps =
    metricNum(m, "slippageBps") ?? fallback?.slippageBps ?? null;
  const spreadBps = metricNum(m, "spreadBps");

  if (!id && !metrics && !trial) return null;

  async function copyId() {
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
    } catch {
      /* ignore */
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-muted/20 p-3 space-y-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {ASESOR_LABEL}
          </p>
          <p className="mt-0.5 font-mono text-sm text-foreground">
            trialId: {id ?? "—"}
            {id && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="ml-1 h-7 px-2"
                onClick={() => void copyId()}
              >
                Copiar
              </Button>
            )}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            K contribution:{" "}
            <span className="text-foreground font-medium">{k}</span>
            {preset ? ` · Preset ${preset}` : ""}
            {` · Proposed by ${proposedBy}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {id && (
            <Link
              to={asesorHistoryHref(id)}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              {VER_EN_ASESOR_LABEL}
            </Link>
          )}
          {backtestRunId && (
            <Link
              to={`/backtests?tab=run&runId=${encodeURIComponent(backtestRunId)}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              Abrir backtest
            </Link>
          )}
        </div>
      </div>

      {trial && <ResearchLabEvidenceSummary trial={trial} variant="panel" />}

      <div>
        <p className="mb-2 text-xs font-medium text-foreground">
          Performance (IS)
        </p>
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
          <Mini label="PnL" value={formatMetric(pnl, "pct")} />
          <Mini label="Buy & hold" value={formatMetric(buyHold, "pct")} />
          <Mini label="Vs B&H" value={formatMetric(excess, "pct")} />
          <Mini label="Sharpe" value={formatMetric(sharpe)} />
          <Mini label="Sortino" value={formatMetric(sortino)} />
          <Mini label="Calmar" value={formatMetric(calmar)} />
          <Mini label="Max DD" value={formatMetric(maxDd, "pct")} />
          <Mini label="Profit Factor" value={formatMetric(pf)} />
          <Mini
            label="Win Rate"
            value={wr == null ? "—" : `${(wr * 100).toFixed(1)}%`}
          />
          <Mini label="Commission" value={formatMetric(commission, "money")} />
        </div>
      </div>

      <div>
        <p className="mb-1 text-xs font-medium text-foreground">
          Costes aplicados
        </p>
        <p className="text-xs text-muted-foreground">
          Commission: {commissionBps ?? 0} bps · Slippage: {slippageBps ?? 0}{" "}
          bps · Spread: {spreadBps ?? 0} bps
        </p>
      </div>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card/60 px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-medium tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}
