import { useState } from "react";
import type { InstrumentRemovalPreviewDto } from "@bolsa/shared";
import { Dialog } from "@/components/ui/dialog";
import { checkboxClassName } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface InstrumentRemovalConfirmDialogProps {
  open: boolean;
  preview: InstrumentRemovalPreviewDto | null;
  loading?: boolean;
  pending?: boolean;
  error?: string | null;
  onClose: () => void;
  /** Solo quitar de la lista (sin borrar BD). */
  onKeepInDb: () => void;
  /** Quitar de la lista y purgar BD si es posible. */
  onPurge: () => void;
}

export function InstrumentRemovalConfirmDialog({
  open,
  preview,
  loading,
  pending,
  error,
  onClose,
  onKeepInDb,
  onPurge,
}: InstrumentRemovalConfirmDialogProps) {
  const [ackWarnings, setAckWarnings] = useState(false);

  if (!open) return null;

  const canPurge = Boolean(preview?.canPurge);
  const warnings = preview?.purgeWarnings ?? [];
  const blocked = preview?.purgeBlockedReasons ?? [];
  const needsAck = warnings.length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={preview ? `Quitar ${preview.symbol}` : "Quitar valor"}
      description="Este valor ya no pertenecerá a ninguna lista persistente."
      className="max-w-lg"
    >
      {loading && (
        <p className="text-sm text-muted-foreground">Calculando impacto…</p>
      )}

      {!loading && preview && (
        <div className="space-y-3 text-sm">
          <p>
            <span className="font-medium">{preview.symbol}</span>
            <span className="text-muted-foreground"> · {preview.name}</span>
          </p>
          <p className="text-xs text-muted-foreground">
            Velas OHLCV: {preview.ohlcvBarCount.toLocaleString()} · Alertas
            precio: {preview.priceAlertsTotal} · Alertas señal:{" "}
            {preview.signalAlertsTotal} · Posiciones: {preview.positions} ·
            Órdenes: {preview.pendingOrders}
          </p>

          {blocked.length > 0 && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs">
              <p className="font-medium text-destructive">
                No se puede borrar de BD
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {blocked.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs">
              <p className="font-medium">Si borramos de BD</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {needsAck && canPurge && (
            <label className="flex items-start gap-2 text-xs">
              <input
                type="checkbox"
                className={cn(checkboxClassName, "mt-0.5")}
                checked={ackWarnings}
                onChange={(e) => setAckWarnings(e.target.checked)}
              />
              <span>
                Entiendo que se eliminarán alertas, velas y datos asociados.
              </span>
            </label>
          )}

          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <button
              type="button"
              className="rounded border border-border px-3 py-1.5 text-sm hover:bg-accent"
              onClick={onClose}
              disabled={pending}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="rounded border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
              disabled={pending}
              onClick={onKeepInDb}
            >
              Solo quitar de la lista
            </button>
            <button
              type="button"
              className="rounded bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
              disabled={pending || !canPurge || (needsAck && !ackWarnings)}
              onClick={onPurge}
              title={!canPurge ? blocked.join(" ") : undefined}
            >
              {pending ? "Eliminando…" : "Quitar y borrar de BD"}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
