import { Settings2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { PAPER_PATH_LAB, PAPER_PATH_RADAR, PAPER_PATHS_COMPARE } from '@/features/settings/paper-paths-copy';
import {
  BACKTEST_HISTORY_MAX_MAX,
  BACKTEST_HISTORY_MAX_MIN,
  MATRIX_LIST_HEIGHT_MAX,
  MATRIX_LIST_HEIGHT_MIN,
  clampHistoryMaxKept,
  clampListHeightPx,
  loadBacktestZonePrefs,
  saveBacktestZonePrefs,
  type BacktestZonePrefs,
} from '@/features/backtests/backtest-zone-prefs';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (prefs: BacktestZonePrefs) => void;
};

export function BacktestZoneSettingsDialog({ open, onOpenChange, onSaved }: Props) {
  const [historyMaxKept, setHistoryMaxKept] = useState(
    () => loadBacktestZonePrefs().historyMaxKept,
  );
  const [listHeightPx, setListHeightPx] = useState(
    () => loadBacktestZonePrefs().strategyMatrix.listHeightPx,
  );

  useEffect(() => {
    if (!open) return;
    const prefs = loadBacktestZonePrefs();
    setHistoryMaxKept(prefs.historyMaxKept);
    setListHeightPx(prefs.strategyMatrix.listHeightPx);
  }, [open]);

  function handleSave() {
    const current = loadBacktestZonePrefs();
    const next: BacktestZonePrefs = {
      ...current,
      historyMaxKept: clampHistoryMaxKept(historyMaxKept),
      strategyMatrix: {
        ...current.strategyMatrix,
        listHeightPx: clampListHeightPx(listHeightPx),
      },
    };
    saveBacktestZonePrefs(next);
    onSaved(next);
    onOpenChange(false);
  }

  return (
    <Dialog
      open={open}
      onClose={() => onOpenChange(false)}
      title="Configuración · Backtesting"
      description="Preferencias de esta zona. Se guardan en este dispositivo."
      className="max-w-md"
    >
      <div className="space-y-5">
        <section className="space-y-2">
          <h4 className="text-sm font-semibold text-foreground">Historial</h4>
          <label className="block text-sm">
            <span className="font-medium">Máximo de pruebas anteriores</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              Afecta la pestaña Pruebas anteriores. Si se supera, se borran las más antiguas de la BD.
            </span>
            <input
              type="number"
              min={BACKTEST_HISTORY_MAX_MIN}
              max={BACKTEST_HISTORY_MAX_MAX}
              value={historyMaxKept}
              onChange={(e) => setHistoryMaxKept(Number(e.target.value))}
              className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm tabular-nums"
            />
            <span className="mt-1 block text-[11px] text-muted-foreground">
              Rango {BACKTEST_HISTORY_MAX_MIN}–{BACKTEST_HISTORY_MAX_MAX} · por defecto 20
            </span>
          </label>
        </section>

        <section className="space-y-2 border-t border-border pt-4">
          <h4 className="text-sm font-semibold text-foreground">Matriz (Probar)</h4>
          <label className="block text-sm">
            <span className="font-medium">Altura del listado de estrategias</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              También se puede arrastrar el borde inferior de la matriz en Probar.
            </span>
            <input
              type="number"
              min={MATRIX_LIST_HEIGHT_MIN}
              max={MATRIX_LIST_HEIGHT_MAX}
              step={10}
              value={listHeightPx}
              onChange={(e) => setListHeightPx(Number(e.target.value))}
              className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm tabular-nums"
            />
            <span className="mt-1 block text-[11px] text-muted-foreground">
              Rango {MATRIX_LIST_HEIGHT_MIN}–{MATRIX_LIST_HEIGHT_MAX} px
            </span>
          </label>
        </section>

        <section className="space-y-2 border-t border-border pt-4">
          <h4 className="text-sm font-semibold text-foreground">Recordatorios</h4>
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            <li>
              <span className="font-medium text-foreground">{PAPER_PATH_LAB.shortTitle}:</span>{' '}
              {PAPER_PATH_LAB.blurb}
            </li>
            <li>
              <span className="font-medium text-foreground">{PAPER_PATH_RADAR.modeLabel}:</span>{' '}
              {PAPER_PATH_RADAR.warnLine}
            </li>
            <li>{PAPER_PATHS_COMPARE}</li>
          </ul>
        </section>

        <div className="flex justify-end gap-2 border-t border-border pt-3">
          <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="button" size="sm" onClick={handleSave}>
            Guardar
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export function BacktestZoneSettingsButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className="h-8 w-8 shrink-0 px-0"
      title="Configuración de Backtesting"
      aria-label="Configuración de Backtesting"
      onClick={onClick}
    >
      <Settings2 className="h-4 w-4" />
    </Button>
  );
}
