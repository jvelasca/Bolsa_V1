/**
 * P4.2 — preview stop amend (proteger) en ticket Confirm.
 * Informativo + override H2; no ejecuta ni persiste stop.
 * V2.10 — bootstrap = emergency −5% (warning), not technical stop.
 * V2.47 — móvil: filas apiladas y motivo de override con objetivo táctil.
 */

import { bootstrapProtectStopLabel } from "@bolsa/shared";
import type { OperativaProtectMetaV1 } from "@/features/operations/propose-position-exit";
import { formatPrice } from "@/features/charts/chart-utils";
import { MesaTipButton } from "@/features/help/mesa-tip-button";
import { cn } from "@/lib/utils";
import {
  cabinRowClass,
  cabinRowValueClass,
  cabinWidth,
  useNarrowCabin,
} from "@/features/trading/use-narrow-cabin";

type F3ProtectStopBlockProps = {
  meta: OperativaProtectMetaV1;
  currency: string;
  overrideReason: string;
  onOverrideReasonChange: (value: string) => void;
  className?: string;
};

function Row({
  label,
  value,
  narrow,
}: {
  label: string;
  value: string;
  narrow: boolean;
}) {
  return (
    <div className={cabinRowClass(narrow)}>
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("tabular-nums", cabinRowValueClass(narrow))}>
        {value}
      </span>
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
  const narrow = useNarrowCabin();
  const money = (n: number | null) =>
    n != null ? `${formatPrice(n)} ${currency}` : "—";
  const isBootstrap = meta.protectKind === "bootstrap";
  const emergency = bootstrapProtectStopLabel();

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 space-y-2 text-xs",
        isBootstrap
          ? "border-amber-600/50 bg-amber-500/10"
          : "border-border bg-muted/20",
        className,
      )}
      data-testid="f3-protect-stop"
      data-protect-kind={meta.protectKind ?? "plan"}
      data-cabin-width={cabinWidth(narrow)}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="text-[11px] font-medium text-foreground">
          {isBootstrap
            ? emergency.title
            : meta.revisionOrigin === "trail"
              ? "Proteger · trail sugerido"
              : "Proteger · stop técnico sugerido"}
        </p>
        <MesaTipButton tip="confirm-risk-signature" />
      </div>
      {isBootstrap ? (
        <p
          className="text-[10px] text-amber-900 dark:text-amber-100"
          data-testid="f3-protect-bootstrap-banner"
        >
          No existe stop técnico válido. {emergency.suggestedLine}.{" "}
          {emergency.disclaimer}
        </p>
      ) : null}
      <div className="space-y-0.5">
        <Row
          label="Stop actual"
          value={money(meta.currentStop)}
          narrow={narrow}
        />
        <Row
          label={isBootstrap ? "Stop de emergencia" : "Stop propuesto"}
          value={money(meta.suggestedStop)}
          narrow={narrow}
        />
        <Row label="Dirección" value={meta.direction} narrow={narrow} />
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
          {isBootstrap
            ? "Encola protección de emergencia — Confirm es la firma; no muta stop solo."
            : "Encola stop amend advisory — Confirm es la firma; no muta stop solo."}
        </p>
      )}
    </div>
  );
}
