import { Bell, X } from "lucide-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { openHelpBacktesting } from "@/features/backtests/core-r-status";
import {
  useAlertsStore,
  type AlertToast,
  type AlertToastAction,
} from "@/stores/alerts-store";
import { cn } from "@/lib/utils";

const AUTO_DISMISS_MS = 12_000;

export function AlertToasts() {
  const toasts = useAlertsStore((s) => s.toasts);
  const dismissToast = useAlertsStore((s) => s.dismissToast);
  const navigate = useNavigate();

  return (
    <div className="pointer-events-none fixed bottom-10 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => (
        <AlertToastItem
          key={toast.id}
          toast={toast}
          onDismiss={() => dismissToast(toast.id)}
          onAction={(action) => runToastAction(action, navigate)}
        />
      ))}
    </div>
  );
}

function runToastAction(
  action: AlertToastAction,
  navigate: ReturnType<typeof useNavigate>,
): void {
  if (action.type === "open_help_backtesting_monitor") {
    openHelpBacktesting({ panel: "monitor" });
    return;
  }
  if (action.type === "open_asesor_opiniones") {
    navigate("/research?tab=opiniones");
  }
}

function AlertToastItem({
  toast,
  onDismiss,
  onAction,
}: {
  toast: AlertToast;
  onDismiss: () => void;
  onAction: (action: AlertToastAction) => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [onDismiss]);

  const action = toast.action;
  const actionLabel =
    action?.label ??
    (action?.type === "open_asesor_opiniones"
      ? "Ver Opiniones"
      : "Abrir Monitor");

  return (
    <div
      className={cn(
        "pointer-events-auto flex items-start gap-2 rounded-md border border-amber-500/40",
        "bg-card/95 p-3 text-sm shadow-lg backdrop-blur",
      )}
    >
      <Bell className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="leading-snug">{toast.message}</p>
        {action ? (
          <button
            type="button"
            className="text-xs font-medium text-primary hover:underline"
            onClick={() => {
              onAction(action);
              onDismiss();
            }}
          >
            {actionLabel}
          </button>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        aria-label="Cerrar"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
