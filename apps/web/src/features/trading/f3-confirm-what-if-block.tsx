/**
 * V1.25 — what-if cartera en Confirm (misma fn que Mesa).
 * V1.26 — fila Sector = exposición al sector del candidato (no tops independientes).
 */

import type { PortfolioScenarioV1 } from "@bolsa/shared";
import {
  candidateSectorExposurePair,
  dominantSectorExposure,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";

type F3ConfirmWhatIfBlockProps = {
  scenario: PortfolioScenarioV1;
  candidateSector?: string | null;
  className?: string;
};

function cell(value: string | number | null | undefined, suffix = ""): string {
  if (value == null || value === "") return "—";
  return `${value}${suffix}`;
}

export function F3ConfirmWhatIfBlock({
  scenario,
  candidateSector = null,
  className,
}: F3ConfirmWhatIfBlockProps) {
  const candidatePair = candidateSectorExposurePair(
    scenario.current.sectorExposurePct,
    scenario.after.sectorExposurePct,
    candidateSector,
  );
  const dominantCurrent = dominantSectorExposure(
    scenario.current.sectorExposurePct,
  );
  const showDominant =
    dominantCurrent != null &&
    (candidatePair == null || dominantCurrent.sector !== candidatePair.sector);

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
        <dd
          className="text-right tabular-nums"
          data-testid="f3-confirm-what-if-sector-current"
        >
          {candidatePair
            ? `${candidatePair.sector} ${candidatePair.currentPct}%`
            : "—"}
        </dd>
        <dd
          className="text-right tabular-nums"
          data-testid="f3-confirm-what-if-sector-after"
        >
          {candidatePair
            ? `${candidatePair.sector} ${candidatePair.afterPct}%`
            : "—"}
        </dd>
        {showDominant ? (
          <>
            <dt className="text-muted-foreground">
              Sector dominante (cartera)
            </dt>
            <dd className="text-right tabular-nums">
              {`${dominantCurrent.sector} ${dominantCurrent.pct}%`}
            </dd>
            <dd className="text-right tabular-nums text-muted-foreground">—</dd>
          </>
        ) : null}
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
