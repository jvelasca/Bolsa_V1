/**
 * V1.19 — panel what-if read-only para candidatos Mesa.
 */

import { useState } from "react";
import type { MesaCandidateRowV1 } from "@bolsa/shared";
import { projectMesaWhatIf } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type MesaWhatIfPanelProps = {
  row: MesaCandidateRowV1;
  portfolioRiskR: number | null;
  equity: number | null;
  cash: number | null;
  className?: string;
};

export function MesaWhatIfPanel({
  row,
  portfolioRiskR,
  equity,
  cash,
  className,
}: MesaWhatIfPanelProps) {
  const [open, setOpen] = useState(false);
  const study = row.study;
  const notional =
    study?.entry != null && study?.riskAmount != null
      ? study.riskAmount * 10
      : null;

  const projection = projectMesaWhatIf({
    symbol: row.symbol,
    candidateRiskR:
      study?.riskAmount != null && study?.entry != null && study?.stop != null
        ? Math.abs(study.entry - study.stop) > 0
          ? (study.riskAmount / Math.abs(study.entry - study.stop)) * 0.01
          : null
        : null,
    portfolioRiskR,
    equity,
    cash,
    candidateNotional: notional,
  });

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
      <p className="font-semibold">What-if (solo lectura)</p>
      <dl className="mt-1 grid gap-0.5">
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Riesgo actual</dt>
          <dd className="tabular-nums">
            {projection.currentRiskR != null
              ? `${projection.currentRiskR.toFixed(2)} R`
              : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">+ {row.symbol}</dt>
          <dd className="tabular-nums">
            {projection.projectedRiskR != null
              ? `${projection.projectedRiskR.toFixed(2)} R`
              : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-muted-foreground">Exposición</dt>
          <dd className="tabular-nums">
            {projection.currentExposurePct != null
              ? `${projection.currentExposurePct}%`
              : "—"}
            {projection.projectedExposurePct != null
              ? ` → ${projection.projectedExposurePct}%`
              : ""}
          </dd>
        </div>
      </dl>
      {projection.warnings.length > 0 ? (
        <ul className="mt-1 list-disc pl-4 text-amber-700 dark:text-amber-300">
          {projection.warnings.map((w) => (
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
