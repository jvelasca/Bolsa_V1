import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Pila de diálogos abiertos (los últimos al final).
 *
 * Cada `Dialog` añade su propio listener de Escape; sin esta pila, Escape cerraba
 * a la vez el modal superior y el que estaba detrás (p. ej. gestor de espacios
 * abierto desde Configuración).
 */
const dialogStack: string[] = [];

function pushDialog(id: string) {
  if (!dialogStack.includes(id)) dialogStack.push(id);
}

function popDialog(id: string) {
  const index = dialogStack.indexOf(id);
  if (index >= 0) dialogStack.splice(index, 1);
}

function isTopDialog(id: string) {
  return dialogStack.length === 0 || dialogStack[dialogStack.length - 1] === id;
}

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: DialogProps) {
  const rawId = useId();
  const titleId = `dialog-title-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const instanceId = useRef(`dialog-${titleId}`);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const id = instanceId.current;
    pushDialog(id);
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (!isTopDialog(id)) return;
      event.stopPropagation();
      onCloseRef.current();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      popDialog(id);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Cerrar"
        className="absolute inset-0 bg-black/75 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "relative z-[101] flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-card shadow-2xl",
          className,
        )}
      >
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description && (
              <p className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

interface TabItem {
  id: string;
  label: string;
}

export function DialogTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
}) {
  const baseId = useId();
  const tabId = (id: string) =>
    `dialog-tab-${baseId.replace(/[^a-zA-Z0-9_-]/g, "")}-${id}`;

  function onKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((tab) => tab.id === active);
    if (index < 0) return;
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft")
      next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    const target = tabs[next];
    if (!target) return;
    onChange(target.id);
    document.getElementById(tabId(target.id))?.focus();
  }

  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      onKeyDown={onKeyDown}
      className="mb-4 flex flex-wrap gap-1 border-b border-border"
    >
      {tabs.map((tab) => {
        const selected = active === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={tabId(tab.id)}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm transition-colors",
              selected
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export function FieldRow({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

export const inputClassName =
  "rounded-md border border-border bg-background px-3 py-2 text-sm outline-none ring-primary focus:ring-1";

export const checkboxClassName = "h-4 w-4 rounded border-border accent-primary";
