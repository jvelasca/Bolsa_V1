/**
 * Panel lateral (slide-over) reutilizando el contrato visual de Dialog
 * (backdrop opaco, Escape, cierre). Sin Sheet de terceros.
 */

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type SlideOverProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  /** Extra header actions (p. ej. link a página completa). */
  headerActions?: ReactNode;
  className?: string;
  /** Ancho máx. del panel (Tailwind). */
  widthClassName?: string;
  /** test id del panel (role=dialog). */
  testId?: string;
};

export function SlideOver({
  open,
  onClose,
  title,
  description,
  children,
  headerActions,
  className,
  widthClassName = "max-w-lg",
  testId = "slide-over",
}: SlideOverProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex justify-end">
      <button
        type="button"
        aria-label="Cerrar"
        className="absolute inset-0 bg-black/75 backdrop-blur-[2px]"
        onClick={onClose}
        data-testid={`${testId}-backdrop`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="slide-over-title"
        data-testid={testId}
        className={cn(
          "relative z-[101] flex h-full w-full flex-col overflow-hidden border-l border-border bg-card shadow-2xl",
          widthClassName,
          className,
        )}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 id="slide-over-title" className="text-lg font-semibold">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
            {headerActions ? (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {headerActions}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Cerrar panel"
            data-testid={`${testId}-close`}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-3">{children}</div>
      </div>
    </div>
  );
}
