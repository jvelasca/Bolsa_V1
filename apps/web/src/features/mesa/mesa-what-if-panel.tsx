/**
 * Portfolio Scenario — estimación de cartera, no permiso (Confirm = firma).
 */

import { useState } from "react";
import type {
  MesaCandidateRowV1,
  PortfolioPositionRiskInput,
  PortfolioRiskSnapshotV1,
} from "@bolsa/shared";
import {
  buildPortfolioScenario,
  candidateSectorExposurePair,
  dominantSectorExposure,
  PORTFOLIO_SCENARIO_DEFAULT_MAX_SECTOR_PCT,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type MesaWhatIfPanelProps = {
  row: MesaCandidateRowV1;
  portfolioRisk: PortfolioRiskSnapshotV1 | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  candidateSector?: string | null;
  equity: number | null;
  cash: number | null;
  className?: string;
};

function cell(value: string | number | null | undefined, suffix = ""): string {
  if (value == null || value === "") return "—";
  return `${value}${suffix}`;
}

export function MesaWhatIfPanel({
  row,
  portfolioRisk,
  positions = [],
  candidateSector = null,
  equity,
  cash,
  className,
}: MesaWhatIfPanelProps) {
  const [open, setOpen] = useState(false);

  const scenario = buildPortfolioScenario({
    candidate: row,
    positions,
    equity,
    cash,
    candidateSector,
    riskTolerance: null,
    maxSectorExposurePct: PORTFOLIO_SCENARIO_DEFAULT_MAX_SECTOR_PCT,
    portfolioRiskLimitR: portfolioRisk?.portfolioRiskLimitR ?? null,
  });

  const limit = portfolioRisk?.portfolioRiskLimitR ?? scenario.riskLimitR;
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
  const unknownPct =
    scenario.after.sectorExposurePct.Unknown ??
    scenario.current.sectorExposurePct.Unknown ??
    0;

  if (!open) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn("h-7 text-[10px]", className)}
        onClick={() => setOpen(true)}
        data-testid={`mesa-whatif-open-${row.symbol}`}
      >
        Simular impacto
      </Button>
    );
  }

  return (
    <div
      className={cn(
        "mt-2 rounded border border-dashed border-border/60 bg-muted/10 px-2 py-2 text-[10px]",
        className,
      )}
      data-testid={`mesa-whatif-${row.symbol}`}
    >
      <p className="font-semibold">¿Qué pasa si añado {row.symbol}?</p>
      <p className="text-muted-foreground">
        Estimación de cartera, no permiso. Confirm es la firma. No evalúa
        check_opening, DS-05 ni Fit de firma.
      </p>
      <div className="mt-1 grid grid-cols-3 gap-1 text-[9px] font-semibold uppercase text-muted-foreground">
        <span />
        <span>Actual</span>
        <span>Después</span>
      </div>
      <dl className="mt-0.5 grid grid-cols-3 gap-0.5">
        <dt className="text-muted-foreground">Capital</dt>
        <dd className="tabular-nums text-right">
          {cell(scenario.current.capital)}
        </dd>
        <dd className="tabular-nums text-right">
          {cell(scenario.after.capital)}
        </dd>
        <dt className="text-muted-foreground">Invertido</dt>
        <dd className="tabular-nums text-right">
          {cell(scenario.current.investedPct, "%")}
        </dd>
        <dd className="tabular-nums text-right">
          {cell(scenario.after.investedPct, "%")}
        </dd>
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
        <dt
          className="text-muted-foreground"
          title="cota concurrente stops; sin correlación"
        >
          Stress
        </dt>
        <dd
          className="tabular-nums text-right"
          title="cota concurrente stops; sin correlación"
        >
          {portfolioRisk?.portfolioStressRiskR != null
            ? `${portfolioRisk.portfolioStressRiskR.toFixed(2)}R`
            : "—"}
        </dd>
        <dd
          className="tabular-nums text-right text-muted-foreground"
          title="cota concurrente stops; sin correlación · no proyectado en scenario"
        >
          —
        </dd>
        <dt className="text-muted-foreground">Sector</dt>
        <dd className="text-right tabular-nums">
          {candidatePair
            ? `${candidatePair.sector} ${candidatePair.currentPct}%`
            : "—"}
        </dd>
        <dd className="text-right tabular-nums">
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
        {unknownPct > 0 ? (
          <>
            <dt className="text-muted-foreground">Unknown</dt>
            <dd className="text-right tabular-nums">{unknownPct}%</dd>
            <dd className="text-right tabular-nums">
              {cell(scenario.after.sectorExposurePct.Unknown, "%")}
            </dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">Fit</dt>
        <dd className="text-right">{scenario.current.portfolioFit}</dd>
        <dd className="text-right">{scenario.after.portfolioFit}</dd>
      </dl>
      <p className="mt-1">
        Veredicto:{" "}
        <span
          className={cn(
            "font-medium",
            scenario.verdict === "COMPATIBLE" && "text-emerald-700",
            scenario.verdict === "NO_RECOMENDADA" && "text-rose-700",
            scenario.verdict === "INSUFFICIENT_DATA" &&
              "text-amber-800 dark:text-amber-200",
          )}
          data-testid={`mesa-whatif-verdict-${row.symbol}`}
        >
          {scenario.verdict}
        </span>
        {scenario.verdictReason ? ` — ${scenario.verdictReason}` : ""}
      </p>
      <p className="text-muted-foreground">
        Concentración sectorial:{" "}
        {scenario.after.sectorConcentration != null
          ? scenario.after.sectorConcentration.toFixed(2)
          : "—"}
      </p>
      <p className="text-muted-foreground">Límite mandato: {limit}R</p>
      {scenario.warnings.length > 0 ? (
        <ul className="mt-1 list-disc pl-4 text-amber-700 dark:text-amber-300">
          {scenario.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="mt-1 h-6 text-[10px]"
        onClick={() => setOpen(false)}
      >
        Cerrar
      </Button>
    </div>
  );
}
