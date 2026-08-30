import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  filterCommands,
  type CommandRunContext,
  type PlatformCommand,
} from "@/features/command-palette/command-registry";

const GROUP_LABEL: Record<PlatformCommand["group"], string> = {
  nav: "Navegación",
  config: "Configuración",
  density: "Densidad",
  theme: "Tema",
  layout: "Layout",
};

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  runContext: CommandRunContext;
};

export function CommandPalette({
  open,
  onClose,
  runContext,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => filterCommands(query), [query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((i) =>
          results.length === 0 ? 0 : Math.min(i + 1, results.length - 1),
        );
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (event.key === "Enter") {
        const cmd = results[activeIndex];
        if (!cmd) return;
        event.preventDefault();
        cmd.run(runContext);
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, results, activeIndex, runContext]);

  if (!open) return null;

  let lastGroup: PlatformCommand["group"] | null = null;

  return (
    <div className="fixed inset-0 z-[110] flex items-start justify-center px-4 pt-[12vh]">
      <button
        type="button"
        aria-label="Cerrar palette"
        className="absolute inset-0 bg-black/70 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative z-[111] flex w-full max-w-lg flex-col overflow-hidden rounded-lg border border-border bg-card shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ir a… · Config · Densidad · Tema"
            className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            aria-autocomplete="list"
            aria-controls="command-palette-list"
          />
          <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline">
            Esc
          </kbd>
        </div>
        <ul
          id="command-palette-list"
          role="listbox"
          className="max-h-[min(50vh,360px)] overflow-auto py-1"
        >
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">
              Sin resultados
            </li>
          ) : (
            results.map((cmd, index) => {
              const showGroup = cmd.group !== lastGroup;
              lastGroup = cmd.group;
              return (
                <li key={cmd.id} role="presentation">
                  {showGroup ? (
                    <div className="px-3 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      {GROUP_LABEL[cmd.group]}
                    </div>
                  ) : null}
                  <button
                    type="button"
                    role="option"
                    aria-selected={index === activeIndex}
                    className={cn(
                      "flex w-full items-center px-3 py-2 text-left text-sm",
                      index === activeIndex
                        ? "bg-accent text-foreground"
                        : "text-foreground/90 hover:bg-accent/60",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => {
                      cmd.run(runContext);
                      onClose();
                    }}
                  >
                    {cmd.label}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
