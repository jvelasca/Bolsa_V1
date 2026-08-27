/**
 * Chip «Datos» del encabezado de Hoy (V1.23 Fase 4).
 * Mismo builder que Mercado — sin scan no se inventa frescura.
 */

import { buildScanFreshnessChip } from "@bolsa/shared";
import { cn } from "@/lib/utils";

export function MesaDatosChip({
  scanUpdatedAt,
  className,
}: {
  scanUpdatedAt: string | null;
  className?: string;
}) {
  const chip = buildScanFreshnessChip({ scanUpdatedAt });

  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-medium",
        chip.tone === "fresh" &&
          "border-emerald-500/40 bg-emerald-500/5 text-emerald-800 dark:text-emerald-200",
        chip.tone === "stale" &&
          "border-amber-500/40 bg-amber-500/5 text-amber-900 dark:text-amber-100",
        chip.tone === "missing" &&
          "border-border/60 bg-muted/30 text-muted-foreground",
        className,
      )}
      data-testid="mesa-datos-chip"
      data-tone={chip.tone}
      title="Frescura del último barrido del universo Estudio"
    >
      {chip.label}
    </span>
  );
}
