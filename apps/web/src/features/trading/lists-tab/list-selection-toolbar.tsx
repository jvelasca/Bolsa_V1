import {
  AlertTriangle,
  ArrowDownWideNarrow,
  Eraser,
  LineChart,
  ListMinus,
  ListPlus,
  RefreshCw,
} from "lucide-react";

/**
 * Barra de acciones sobre la selección del panel Valores (búsqueda/pestañas/Estudio).
 *
 * Presentacional (Diseño B): la lógica de selección (estado `selectedInstrumentIds`, handlers de
 * add/remove/reordenar/abrir/actualizar) vive en el orquestador `ListValuesPanel`, que inyecta aquí
 * los valores y callbacks como props-closure. Se traslada fielmente el bloque `<div>` con
 * `data-testid="list-selection-actions"`; la guarda `{selectionEnabled && count > 0}` permanece en
 * el orquestador. No se mueve lógica de ciclo ni de estado.
 */
export function ListSelectionToolbar({
  count,
  viewingEstudio,
  viewingVisualizados,
  updatingSelected,
  sortingByIo,
  selectedInEstudioCount,
  onAddToEstudio,
  onRemove,
  onReorderByIo,
  onOpenCharts,
  onUpdateSelected,
  onClear,
}: {
  count: number;
  viewingEstudio: boolean;
  viewingVisualizados: boolean;
  updatingSelected: boolean;
  sortingByIo: boolean;
  selectedInEstudioCount: number;
  onAddToEstudio: () => void;
  onRemove: () => void;
  onReorderByIo: () => void;
  onOpenCharts: () => void;
  onUpdateSelected: (opts: { rediscover: boolean }) => void;
  onClear: () => void;
}) {
  return (
    <div
      className="z-20 flex shrink-0 flex-wrap items-center gap-1.5 border-t border-border bg-card px-2 py-2 text-[11px] shadow-[0_-4px_12px_rgba(0,0,0,0.06)]"
      data-testid="list-selection-actions"
      role="toolbar"
      aria-label="Acciones sobre la selección"
    >
      <span className="mr-1 tabular-nums text-muted-foreground">
        {count} seleccionado{count === 1 ? "" : "s"}
      </span>
      {!viewingEstudio ? (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-primary/50 bg-primary/15 px-2 py-1.5 font-semibold text-primary hover:bg-primary/20"
          onClick={onAddToEstudio}
          title="Pasar la selección a Estudio (supervisión)"
        >
          <ListPlus className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />A
          Estudio
        </button>
      ) : null}
      <button
        type="button"
        className={
          viewingEstudio || viewingVisualizados
            ? "inline-flex items-center gap-1 rounded border border-destructive/40 bg-destructive/10 px-2 py-1.5 font-semibold text-destructive hover:bg-destructive/15 disabled:cursor-not-allowed disabled:opacity-40"
            : "inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
        }
        onClick={onRemove}
        disabled={
          viewingVisualizados
            ? count === 0
            : viewingEstudio
              ? count === 0
              : selectedInEstudioCount === 0
        }
        title={
          viewingVisualizados
            ? "Cierra las pestañas de la selección (salen de Visualizados)"
            : viewingEstudio
              ? "Elimina de Estudio (sale de la cola de supervisión)"
              : "Quita la selección de Estudio"
        }
      >
        <ListMinus className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
        {viewingVisualizados
          ? "Quitar"
          : viewingEstudio
            ? "Eliminar"
            : "Quitar"}
      </button>
      {viewingVisualizados ? (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
          disabled={count < 2 || sortingByIo}
          onClick={onReorderByIo}
          title="Ordena pestañas por Índice Operativo (IO 0–100): mayor IO a la izquierda (#1 en Estudio = mejor IO). Usa caché de Operativa; si falta, carga en trozos pequeños."
        >
          <ArrowDownWideNarrow
            className="h-3.5 w-3.5 shrink-0 opacity-70"
            aria-hidden
          />
          {sortingByIo ? "IO…" : "Por IO"}
        </button>
      ) : null}
      {/* En Visualizados sobra: esa lista ya es el espejo de pestañas abiertas. */}
      {!viewingVisualizados ? (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1.5 font-medium text-foreground hover:bg-accent"
          onClick={onOpenCharts}
          title="Abrir gráficos de la selección"
        >
          <LineChart className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
          Abrir gráficos
        </button>
      ) : null}
      {viewingEstudio ? (
        <>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1.5 font-semibold text-foreground hover:bg-accent disabled:opacity-50"
            disabled={updatingSelected}
            title="Adelanta vigilia + frescura (velas + Lab). Funciona con Supervisión OFF."
            onClick={() => onUpdateSelected({ rediscover: false })}
          >
            <RefreshCw className="h-3.5 w-3.5 opacity-70" aria-hidden />
            {updatingSelected ? "Actualizando…" : "Actualizar"}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded border border-amber-500/50 bg-amber-500/10 px-2.5 py-1.5 font-semibold text-amber-800 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-200"
            disabled={updatingSelected}
            title="Costoso: embudo completo y búsqueda de nuevas estrategias TOP. Pide confirmación."
            onClick={() => onUpdateSelected({ rediscover: true })}
          >
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
            Redescubrir
          </button>
        </>
      ) : null}
      <button
        type="button"
        className="ml-auto inline-flex items-center gap-1 rounded px-2.5 py-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={onClear}
        title="Quitar la selección"
      >
        <Eraser className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
        Limpiar
      </button>
    </div>
  );
}
