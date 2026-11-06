import { Dialog } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Confirmación destructiva dentro de la app (sustituye a `window.confirm` en
 * las acciones del gráfico): mismo lenguaje visual que el resto de diálogos,
 * testeable con Playwright y sin bloquear el hilo del navegador.
 */
export function ConfirmActionDialog({
  open,
  title,
  description,
  confirmLabel = "Eliminar",
  cancelLabel = "Cancelar",
  destructive = true,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      className="max-w-md"
    >
      <div className="flex justify-end gap-2">
        <button
          type="button"
          data-testid="confirm-action-cancel"
          className="rounded border border-border bg-muted px-3 py-2 text-sm hover:bg-accent"
          onClick={onCancel}
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          data-testid="confirm-action-accept"
          autoFocus
          className={cn(
            "rounded px-3 py-2 text-sm font-semibold text-white",
            destructive
              ? "bg-red-600 hover:bg-red-700"
              : "bg-emerald-600 hover:bg-emerald-700",
          )}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
