/**
 * Sección colapsable del panel Operativa: cabecera (+ summary / modo) + cuerpo con scroll
 * + asa de altura redimensionable (persistida en `operativaSectionHeights`).
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ChevronDown } from "lucide-react";
import {
  MAX_OPERATIVA_SECTION_HEIGHT_PX,
  MIN_OPERATIVA_SECTION_HEIGHT_PX,
  type OperativaSectionId,
  useTradingLayoutStore,
} from "@/stores/trading-layout-store";
import { cn } from "@/lib/utils";

const DEFAULT_HEIGHTS: Record<OperativaSectionId, number> = {
  recommendation: 320,
  info: 200,
  config: 180,
};

export function TradingOperativaSection({
  sectionId,
  title,
  summary,
  children,
  className,
}: {
  sectionId: OperativaSectionId;
  title: ReactNode;
  /** Resumen visible en cabecera (también con la sección colapsada). */
  summary?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const open = useTradingLayoutStore(
    (s) => s.operativaSections?.[sectionId] ?? true,
  );
  const storedHeight = useTradingLayoutStore(
    (s) => s.operativaSectionHeights?.[sectionId] ?? DEFAULT_HEIGHTS[sectionId],
  );
  const toggle = useTradingLayoutStore((s) => s.toggleOperativaSection);
  const setHeight = useTradingLayoutStore((s) => s.setOperativaSectionHeight);

  const [liveHeight, setLiveHeight] = useState(storedHeight);
  const pendingRef = useRef(storedHeight);

  useEffect(() => {
    setLiveHeight(storedHeight);
    pendingRef.current = storedHeight;
  }, [storedHeight]);

  const onResizePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const handle = event.currentTarget;
      handle.setPointerCapture(event.pointerId);
      let lastY = event.clientY;
      pendingRef.current = liveHeight;

      const onMove = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientY - lastY;
        lastY = moveEvent.clientY;
        const next = Math.min(
          MAX_OPERATIVA_SECTION_HEIGHT_PX,
          Math.max(MIN_OPERATIVA_SECTION_HEIGHT_PX, pendingRef.current + delta),
        );
        pendingRef.current = next;
        setLiveHeight(next);
      };
      const onUp = () => {
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        try {
          handle.releasePointerCapture(event.pointerId);
        } catch {
          /* already released */
        }
        setHeight(sectionId, pendingRef.current);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
      document.body.style.cursor = "row-resize";
      document.body.style.userSelect = "none";
      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    },
    [liveHeight, sectionId, setHeight],
  );

  return (
    <section
      className={cn(
        "flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border border-border/80 bg-background/60",
        className,
      )}
      data-testid={`operativa-section-${sectionId}`}
    >
      <button
        type="button"
        className="flex w-full shrink-0 items-center gap-1.5 px-2 py-1.5 text-left hover:bg-muted/40"
        aria-expanded={open}
        onClick={() => toggle(sectionId)}
      >
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
            !open && "-rotate-90",
          )}
        />
        <span className="min-w-0 flex-1 truncate text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </span>
        {summary ? (
          <span className="max-w-[45%] shrink-0 truncate text-right">
            {summary}
          </span>
        ) : null}
      </button>
      {open ? (
        <>
          <div
            className="min-h-0 overflow-y-auto overscroll-contain border-t border-border/70 px-2 py-2 text-[11px]"
            style={{ height: liveHeight }}
          >
            <div className="space-y-2">{children}</div>
          </div>
          <div
            role="separator"
            aria-orientation="horizontal"
            aria-label="Redimensionar sección"
            title="Arrastra para ampliar o reducir la sección"
            onPointerDown={onResizePointerDown}
            className="group flex h-2.5 shrink-0 cursor-row-resize items-center justify-center border-t border-border/50 bg-muted/25 hover:bg-primary/20"
          >
            <span
              className="h-0.5 w-8 rounded-full bg-muted-foreground/35 group-hover:bg-primary/70"
              aria-hidden
            />
          </div>
        </>
      ) : null}
    </section>
  );
}
