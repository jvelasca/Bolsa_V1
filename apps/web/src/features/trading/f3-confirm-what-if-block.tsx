/**
 * V1.25 — what-if cartera en Confirm (misma fn que Mesa).
 */

import type { PortfolioScenarioV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

type F3ConfirmWhatIfBlockProps = {
  scenario: PortfolioScenarioV1;
  className?: string;
};

function cell(value: string | number | null | undefined, suffix = ""): string {
  if (value == null || value === "") return "—";
  return `${value}${suffix}`;
}

export function F3ConfirmWhatIfBlock({
  scenario,
  className,
}: F3ConfirmWhatIfBlockProps) {
  const topSectorAfter = Object.entries(scenario.after.sectorExposurePct).sort(
    (a, b) => b[1] - a[1],
  )[0];
  const topSectorCurrent = Object.entries(
    scenario.current.sectorExposurePct,
  ).sort((a, b) => b[1] - a[1])[0];

  return (
    <div
      className={cn(
        "rounded-md border border-dashed border-border/60 bg-muted/10 px-3 py-2 text-[11px] space-y-1.5",
        className,
      )}
      data-testid="f3-confirm-what-if"
    >
      <p className="font-semibold text-foreground">Cartera · Antes → Después</p>
      <p className="text-[10px] text-muted-foreground">
        Estimación, no permiso. Confirm es la firma.
      </p>
      <div className="grid grid-cols-3 gap-1 text-[9px] font-semibold uppercase text-muted-foreground">
        <span />
        <span>Actual</span>
        <span>Después</span>
      </div>
      <dl className="grid grid-cols-3 gap-0.5">
        <dt className="text-muted-foreground">Cash</dt>
        <dd className="tabular-nums text-right">
          {cell(scenario.current.cashPct, "%")}
        </dd>
        <dd className="tabular-nums text-right">
          {cell(scenario.after.cashPct, "%")}
        </dd>
        <dt className="text-muted-foreground">Open Risk</dt>
        <dd className="tabular-nums text-right">
          {scenario.current.openRiskR != null
            ? `${scenario.current.openRiskR.toFixed(2)}R`
            : "—"}
        </dd>
        <dd className="tabular-nums text-right">
          {scenario.after.openRiskR != null
            ? `${scenario.after.openRiskR.toFixed(2)}R`
            : "—"}
        </dd>
        <dt className="text-muted-foreground">Sector</dt>
        <dd className="text-right tabular-nums">
          {topSectorCurrent
            ? `${topSectorCurrent[0]} ${topSectorCurrent[1]}%`
            : "—"}
        </dd>
        <dd className="text-right tabular-nums">
          {topSectorAfter ? `${topSectorAfter[0]} ${topSectorAfter[1]}%` : "—"}
        </dd>
        <dt className="text-muted-foreground">Fit</dt>
        <dd className="text-right">{scenario.current.portfolioFit}</dd>
        <dd className="text-right">{scenario.after.portfolioFit}</dd>
      </dl>
      <p>
        Veredicto:{" "}
        <span
          className={cn(
            "font-medium",
            scenario.verdict === "COMPATIBLE" && "text-emerald-700",
            scenario.verdict === "NO_RECOMENDADA" && "text-rose-700",
            scenario.verdict === "INSUFFICIENT_DATA" &&
              "text-amber-800 dark:text-amber-200",
          )}
          data-testid="f3-confirm-what-if-verdict"
        >
          {scenario.verdict}
        </span>
        {scenario.verdictReason ? ` — ${scenario.verdictReason}` : ""}
      </p>
    </div>
  );
}
