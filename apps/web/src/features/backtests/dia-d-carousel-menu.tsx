/**
 * Menú (…) del carrusel DÍA D — predeterminados (checkbox) + personalizados (editar/borrar).
 */

import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { checkboxClassName } from '@/components/ui/dialog';
import {
  DIA_D_PRESETS,
  formatDiaDDisplay,
  isPresetVisible,
  removeCustomDiaD,
  togglePresetVisible,
  updateCustomDiaD,
  type DiaDCarouselPrefs,
  type DiaDCustomEntry,
} from '@/features/backtests/dia-d-favorites';
import { todayIsoDate } from '@/features/backtests/backtest-period';
import { cn } from '@/lib/utils';

type Props = {
  prefs: DiaDCarouselPrefs;
  onPrefsChange: (next: DiaDCarouselPrefs) => void;
};

export function DiaDCarouselMenu({ prefs, onPrefsChange }: Props) {
  const [open, setOpen] = useState(false);
  const [editingIso, setEditingIso] = useState<string | null>(null);
  const [editIso, setEditIso] = useState('');
  const [editLabel, setEditLabel] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);
  const today = todayIsoDate();

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
        setEditingIso(null);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  function startEdit(entry: DiaDCustomEntry) {
    setEditingIso(entry.iso);
    setEditIso(entry.iso);
    setEditLabel(entry.label ?? '');
  }

  function commitEdit() {
    if (!editingIso) return;
    onPrefsChange(
      updateCustomDiaD(prefs, editingIso, {
        iso: editIso,
        label: editLabel || undefined,
      }),
    );
    setEditingIso(null);
  }

  return (
    <div
      ref={menuRef}
      className="relative shrink-0 border-l border-border/60 pl-0.5"
    >
      <button
        type="button"
        title="Configurar carrusel DÍA D"
        className="rounded p-1 hover:bg-accent"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-30 mt-1 w-[min(100vw-2rem,17rem)] rounded-md border border-border bg-background py-1 shadow-lg ring-1 ring-black/10 dark:bg-zinc-950 dark:ring-white/10">
          <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground">
            Predeterminados
          </p>
          <div className="scroll-area max-h-40 overflow-auto border-b border-border/60 pb-1">
            {DIA_D_PRESETS.map((preset) => (
              <label
                key={preset.id}
                className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-accent/50"
              >
                <input
                  type="checkbox"
                  className={checkboxClassName}
                  checked={isPresetVisible(prefs, preset.id)}
                  onChange={() =>
                    onPrefsChange(togglePresetVisible(prefs, preset.id))
                  }
                />
                <span className="min-w-0 flex-1 truncate">{preset.label}</span>
                <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                  {formatDiaDDisplay(preset.resolve())}
                </span>
              </label>
            ))}
          </div>

          <p className="px-2 py-1 text-[10px] font-medium text-muted-foreground">
            Personalizados
          </p>
          <div className="scroll-area max-h-44 overflow-auto">
            {prefs.customs.length === 0 ? (
              <p className="px-2 py-1.5 text-[10px] text-muted-foreground">
                Aún no hay fechas propias. Elige una fecha y pulsa Añadir ★.
              </p>
            ) : (
              prefs.customs.map((entry) => {
                const editing = editingIso === entry.iso;
                if (editing) {
                  return (
                    <div
                      key={entry.iso}
                      className="space-y-1 border-b border-border/40 px-2 py-1.5"
                    >
                      <input
                        type="date"
                        max={today}
                        value={editIso}
                        onChange={(e) => setEditIso(e.target.value)}
                        className="w-full rounded border border-border bg-background px-1.5 py-1 text-[11px] dark:bg-zinc-900"
                      />
                      <input
                        type="text"
                        value={editLabel}
                        placeholder="Nombre (opcional)"
                        onChange={(e) => setEditLabel(e.target.value)}
                        className="w-full rounded border border-border bg-background px-1.5 py-1 text-[11px] dark:bg-zinc-900"
                      />
                      <div className="flex gap-1">
                        <button
                          type="button"
                          className="rounded bg-primary px-2 py-0.5 text-[10px] text-primary-foreground"
                          onClick={commitEdit}
                        >
                          Guardar
                        </button>
                        <button
                          type="button"
                          className="rounded px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-muted"
                          onClick={() => setEditingIso(null)}
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  );
                }
                return (
                  <div
                    key={entry.iso}
                    className="flex items-center gap-1 px-2 py-1 text-xs hover:bg-accent/40"
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {entry.label?.trim() || formatDiaDDisplay(entry.iso)}
                      {entry.label ? (
                        <span className="ml-1 text-[10px] text-muted-foreground">
                          ({formatDiaDDisplay(entry.iso)})
                        </span>
                      ) : null}
                    </span>
                    <button
                      type="button"
                      title="Editar"
                      className={cn('rounded p-0.5 hover:bg-muted')}
                      onClick={() => startEdit(entry)}
                    >
                      <Pencil className="size-3 text-muted-foreground" />
                    </button>
                    <button
                      type="button"
                      title="Borrar"
                      className="rounded p-0.5 hover:bg-muted"
                      onClick={() =>
                        onPrefsChange(removeCustomDiaD(prefs, entry.iso))
                      }
                    >
                      <Trash2 className="size-3 text-muted-foreground" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
