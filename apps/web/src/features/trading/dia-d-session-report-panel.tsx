import type { ReactNode } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";

interface Props {
  /** Rama del layout: desktop (informe lateral dentro del movie-row, con
   * drag-resize) o móvil (bloque `<details>` apilado debajo del movie-row). */
  variant: "desktop" | "mobile";
  /** Cuerpo compartido del informe (mismo `sessionReportBody`). */
  body: ReactNode;
  /** Informe lateral/móvil abierto (persistido por el orquestador). */
  reportOpen: boolean;
  /** Abrir/colapsar. El móvil lo llama desde `<details onToggle>`. */
  onOpenChange: (open: boolean) => void;
  /** Ancho del informe en % (solo desktop horizontal). */
  reportWidthPct: number;
  /** Drag para redimensionar (desktop): el orquestador computa el nuevo pct
   * con su ref de fila y persiste en `setLayout` (Diseño B). */
  onResizeDrag: (dx: number) => void;
  /** Fin del drag (desktop): el orquestador persiste el layout. */
  onResizeDragEnd: () => void;
}

/** Panel de Informe de sesión del panel DÍA D, en sus dos variantes de layout
 * (desktop lateral redimensionable / móvil `<details>`). Extraído de
 * `trading-dia-d-replay-panel.tsx` (feature-slicing M5, B.3). Diseño B: el
 * cuerpo compartido (`body`), el estado de apertura y los callbacks de
 * drag-resize se pasan como props y permanecen en el orquestador; aquí solo
 * vive el JSX presentacional de las dos ramas (con dos sitios de render
 * guardados por `isWide` en el orquestador, para no romper el drag-resize). */
export function DiaDSessionReportPanel({
  variant,
  body,
  reportOpen,
  onOpenChange,
  reportWidthPct,
  onResizeDrag,
  onResizeDragEnd,
}: Props) {
  if (!body) return null;

  if (variant === "mobile") {
    return (
      <details
        className="shrink-0 border-t border-border/60"
        open={reportOpen}
        onToggle={(e) => onOpenChange(e.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 bg-muted/30 px-3 py-1.5 text-[11px] font-semibold marker:content-none [&::-webkit-details-marker]:hidden">
          <span>Informe sesión</span>
          <span className="text-[10px] font-normal text-muted-foreground">
            {reportOpen ? "Colapsar" : "Expandir"}
          </span>
        </summary>
        <div
          id="dia-d-session-report-panel"
          className="max-h-[36vh] overflow-y-auto p-2 text-[10px]"
          data-testid="dia-d-session-report"
        >
          {body}
        </div>
      </details>
    );
  }

  if (!reportOpen) {
    return (
      <div className="flex w-9 shrink-0 flex-col items-center border-l border-border/60 bg-muted/20 py-1">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-auto w-8 flex-col gap-1 px-1 py-2 text-[9px] leading-tight"
          title="Mostrar informe"
          aria-label="Mostrar informe"
          aria-expanded={false}
          aria-controls="dia-d-session-report-panel"
          onClick={() => onOpenChange(true)}
        >
          <PanelRightOpen className="size-3.5" aria-hidden />
          <span
            className="max-h-24 overflow-hidden text-center"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          >
            Informe
          </span>
        </Button>
      </div>
    );
  }

  return (
    <>
      <PanelResizeHandle
        label="Redimensionar informe de sesión"
        orientation="vertical"
        onDrag={onResizeDrag}
        onDragEnd={onResizeDragEnd}
        className="mx-0.5"
      />
      <aside
        id="dia-d-session-report-panel"
        className="scroll-area flex shrink-0 flex-col overflow-hidden border-l border-border/60 text-[10px]"
        style={{ width: `${reportWidthPct}%` }}
        data-testid="dia-d-session-report"
      >
        <div className="flex shrink-0 items-center gap-1 border-b border-border/50 bg-muted/25 px-2 py-1">
          <p className="min-w-0 flex-1 truncate text-[11px] font-semibold text-foreground">
            Informe sesión
          </p>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-6 shrink-0 gap-1 px-1.5 text-[10px]"
            title="Colapsar informe"
            aria-label="Colapsar informe"
            onClick={() => onOpenChange(false)}
          >
            <PanelRightClose className="size-3.5" aria-hidden />
            <span className="hidden sm:inline">Colapsar</span>
          </Button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
          {body}
        </div>
      </aside>
    </>
  );
}
