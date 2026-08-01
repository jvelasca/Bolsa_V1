import { VIRTUAL_LIST_LABELS, VIRTUAL_LIST_VISUALIZATION } from '@bolsa/shared';
import { Dialog } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useUiStore } from '@/stores/ui-store';
import { useVisualizationStore } from '@/stores/visualization-store';

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString('es-ES', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

const SOURCE_LABELS = {
  search: 'Búsqueda',
  list: 'Lista',
  import: 'Importación',
} as const;

export function VisualizationLogDialog() {
  const open = useUiStore((state) => state.visualizationLogOpen);
  const close = useUiStore((state) => state.closeVisualizationLog);
  const log = useVisualizationStore((state) => state.log);
  const entries = useVisualizationStore((state) => state.entries);

  return (
    <Dialog
      open={open}
      onClose={close}
      title={`Historial — ${VIRTUAL_LIST_LABELS[VIRTUAL_LIST_VISUALIZATION]}`}
      description="Registro de búsquedas y visualizaciones de esta sesión de navegador. Se borra al cerrar sesión."
      className="max-w-2xl"
    >
      <div className="mb-3 rounded border border-border/60 bg-muted/20 px-2 py-1.5 text-xs text-muted-foreground">
        {entries.length} valor(es) en visualización · {log.length} evento(s) registrados
      </div>

      {log.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Aún no hay búsquedas ni visualizaciones en esta sesión.
        </p>
      ) : (
        <div className="scroll-area max-h-[min(50vh,420px)] overflow-auto rounded border border-border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-card text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-2 py-1.5 font-medium">Cuándo</th>
                <th className="px-2 py-1.5 font-medium">Valor</th>
                <th className="px-2 py-1.5 font-medium">Origen</th>
                <th className="px-2 py-1.5 font-medium">Búsqueda</th>
              </tr>
            </thead>
            <tbody>
              {log.map((entry) => (
                <tr key={entry.id} className="border-b border-border/50">
                  <td className="whitespace-nowrap px-2 py-1.5 tabular-nums text-muted-foreground">
                    {formatWhen(entry.viewedAt)}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="font-medium">{entry.symbol}</span>
                    <span className="ml-1 text-muted-foreground">{entry.name}</span>
                  </td>
                  <td className="px-2 py-1.5">{SOURCE_LABELS[entry.source]}</td>
                  <td className="px-2 py-1.5 text-muted-foreground">
                    {entry.searchQuery ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex justify-end border-t border-border pt-4">
        <Button type="button" onClick={close}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}

export function openVisualizationLog() {
  useUiStore.getState().openVisualizationLog();
}

export const VISUALIZATION_LIST_ID = VIRTUAL_LIST_VISUALIZATION;
