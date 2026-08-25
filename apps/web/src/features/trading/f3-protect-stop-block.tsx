/**
 * P4.2 — preview stop amend (proteger) en ticket Confirm.
 * Informativo + override H2; no ejecuta ni persiste stop.
 */

import type { OperativaProtectMetaV1 } from "@/features/operations/propose-position-exit";
import { formatPrice } from "@/features/charts/chart-utils";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import { cn } from "@/lib/utils";

type F3ProtectStopBlockProps = {
  meta: OperativaProtectMetaV1;
  currency: string;
  overrideReason: string;
  onOverrideReasonChange: (value: string) => void;
  className?: string;
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

export function F3ProtectStopBlock({
  meta,
  currency,
  overrideReason,
  onOverrideReasonChange,
  className,
}: F3ProtectStopBlockProps) {
  const money = (n: number | null) =>
    n != null ? `${formatPrice(n)} ${currency}` : "—";

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-muted/20 px-3 py-2 space-y-2 text-xs",
        className,
      )}
      data-testid="f3-protect-stop"
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          Proteger · stop sugerido
        </p>
        <MesaTipButton tip="confirm-risk-signature" />
      </div>
      <div className="space-y-0.5">
        <Row label="Stop actual" value={money(meta.currentStop)} />
        <Row label="Stop propuesto" value={money(meta.suggestedStop)} />
        <Row label="Dirección" value={meta.direction} />
      </div>
      {meta.stopOverrideRequired ? (
        <div className="space-y-1 border-t border-border/60 pt-1.5">
          <p className="text-[11px] text-amber-800 dark:text-amber-300">
            El stop propuesto empeora el actual (H2). Escribe un motivo para
            firmar.
          </p>
          <textarea
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-[11px]"
            rows={2}
            value={overrideReason}
            onChange={(e) => onOverrideReasonChange(e.target.value)}
            placeholder="Motivo del override de stop"
            data-testid="f3-protect-stop-override-reason"
          />
        </div>
      ) : (
        <p className="text-[10px] text-muted-foreground">
          Encola stop amend advisory — Confirm es la firma; no muta stop solo.
        </p>
      )}
    </div>
  );
}
