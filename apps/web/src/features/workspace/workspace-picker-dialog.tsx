/**
 * Gestor de espacios de trabajo (chip de la barra superior / Configuración → General).
 *
 * Es la **única** superficie para todo lo que pertenece al espacio:
 * - Catálogo: cambiar, renombrar, eliminar, nuevo en blanco, duplicar.
 * - Preferencias guardadas en el servidor: autoguardado, preferido al arrancar
 *   (`is_default`) y plantilla para gráficos nuevos.
 * - Diseño de este dispositivo: preset de paneles Mercado y restablecer.
 * - Exportar JSON (no guarda) y guardar ahora.
 *
 * Persistencia y arranque: `docs/WORKSPACE_PERSISTENCE.md`.
 * Store: `useWorkspaceStore` (`createWorkspace`, `duplicateWorkspace`, …).
 */

import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Pencil,
  Plus,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import { Dialog, FieldRow, inputClassName } from "@/components/ui/dialog";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  NAMED_LAYOUT_LABELS,
  type NamedLayoutId,
} from "@/features/command-palette/named-layout";

type DraftMode = "idle" | "create" | "rename" | "duplicate";

export function WorkspacePickerDialog() {
  const open = useUiStore((s) => s.workspacePickerOpen);
  const close = useUiStore((s) => s.closeWorkspacePicker);
  const summaries = useWorkspaceStore((s) => s.workspaceSummaries);
  const activeId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const workspace = useWorkspaceStore((s) => s.workspace);
  const activeName = workspace.name;
  const hydrated = useWorkspaceStore((s) => s.hydrated);
  const loadError = useWorkspaceStore((s) => s.loadError);
  const isDirty = useWorkspaceStore((s) => s.isDirty);
  const isSaving = useWorkspaceStore((s) => s.isSaving);
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace);
  const createWorkspace = useWorkspaceStore((s) => s.createWorkspace);
  const duplicateWorkspace = useWorkspaceStore((s) => s.duplicateWorkspace);
  const renameWorkspaceById = useWorkspaceStore((s) => s.renameWorkspaceById);
  const deleteWorkspaceById = useWorkspaceStore((s) => s.deleteWorkspaceById);
  const saveToServer = useWorkspaceStore((s) => s.saveToServer);
  const bootstrapWorkspaces = useWorkspaceStore((s) => s.bootstrapWorkspaces);
  const exportJson = useWorkspaceStore((s) => s.exportJson);
  const setPreferred = useWorkspaceStore((s) => s.setPreferred);
  const setAutoSave = useWorkspaceStore((s) => s.setAutoSave);
  const toggleNewChartTemplatePin = useWorkspaceStore(
    (s) => s.toggleNewChartTemplatePin,
  );

  const namedLayoutId = useTradingLayoutStore((s) => s.namedLayoutId);
  const applyNamedLayout = useTradingLayoutStore((s) => s.applyNamedLayout);
  const resetLayout = useTradingLayoutStore((s) => s.resetLayout);

  const [busy, setBusy] = useState(false);
  const [prefBusy, setPrefBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draftMode, setDraftMode] = useState<DraftMode>("idle");
  const [draftName, setDraftName] = useState("");
  const [renameId, setRenameId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setDraftMode("idle");
      setDraftName("");
      setRenameId(null);
      setError(null);
      setNotice(null);
    }
  }, [open]);

  const activeSummary = summaries.find((item) => item.id === activeId);
  const isPreferred = activeSummary?.isDefault ?? false;
  const autoSave = workspace.preferences.autoSave;
  const templateChartId = workspace.preferences.newChartTemplateChartId ?? null;
  const templateChart =
    workspace.charts.find((tab) => tab.id === templateChartId) ?? null;
  const activeChartId = workspace.activeChartId;
  const canPinActiveChart = Boolean(activeChartId);
  const activeChartIsTemplate = Boolean(
    templateChartId && templateChartId === activeChartId,
  );

  function startCreate() {
    setDraftMode("create");
    setDraftName("Nuevo espacio");
    setRenameId(null);
    setError(null);
  }

  function startDuplicate() {
    setDraftMode("duplicate");
    setDraftName(
      `${activeName.replace(/\s*\(copia(?:\s+\d+)?\)\s*$/i, "").trim()} (copia)`,
    );
    setRenameId(null);
    setError(null);
  }

  function startRename(id: string, current: string) {
    setDraftMode("rename");
    setRenameId(id);
    setDraftName(current);
    setError(null);
  }

  function cancelDraft() {
    setDraftMode("idle");
    setRenameId(null);
    setDraftName("");
  }

  async function submitDraft() {
    const name = draftName.trim();
    if (!name) {
      setError("Indica un nombre.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (draftMode === "create") {
        await createWorkspace(name);
        close();
      } else if (draftMode === "duplicate") {
        await duplicateWorkspace(name);
        close();
      } else if (draftMode === "rename" && renameId) {
        await renameWorkspaceById(renameId, name);
        cancelDraft();
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo completar la acción",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSwitch(id: string) {
    setBusy(true);
    setError(null);
    try {
      await switchWorkspace(id);
      // Si el usuario canceló la confirmación de cambios sin guardar, el store
      // no cambia de espacio: no cerramos el gestor.
      if (useWorkspaceStore.getState().activeWorkspaceId !== id) return;
      close();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo cambiar de espacio",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (
      !window.confirm(`¿Eliminar «${name}»? Esta acción no se puede deshacer.`)
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await deleteWorkspaceById(id);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo eliminar el espacio de trabajo.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handlePreferred(next: boolean) {
    setPrefBusy(true);
    setError(null);
    try {
      await setPreferred(next);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo marcar el espacio como preferido",
      );
    } finally {
      setPrefBusy(false);
    }
  }

  function handleAutoSave(next: boolean) {
    setAutoSave(next);
    setNotice(
      next
        ? "Autoguardado activado y guardado en el servidor."
        : "Autoguardado desactivado y guardado en el servidor. Usa «Guardar actual» para los próximos cambios.",
    );
  }

  function handleResetLayout() {
    if (
      !window.confirm(
        "¿Restablecer el diseño de paneles a «Trader»? Se perderán los anchos y alturas actuales.",
      )
    )
      return;
    resetLayout();
    setNotice("Diseño de paneles restablecido en este dispositivo.");
  }

  const showEmpty = hydrated && !loadError && summaries.length === 0;
  const showLoading = !hydrated && summaries.length === 0;

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (busy) return;
        close();
      }}
      title="Espacios de trabajo"
      description="Documentos en servidor: gráficos, listas, dibujos y preferencias. Al arrancar se abre el último espacio activo."
      className="max-w-lg"
    >
      <div aria-busy={busy} className="space-y-4">
        {isDirty ? (
          <p className="text-xs text-amber-500">
            Cambios sin guardar en el espacio activo.
          </p>
        ) : null}

        <div className="space-y-2">
          {showLoading && (
            <p className="text-sm text-muted-foreground">Cargando espacios…</p>
          )}
          {loadError && (
            <div className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-3">
              <p role="alert" className="text-sm text-destructive">
                No se pudieron cargar los espacios: {loadError}
              </p>
              <button
                type="button"
                disabled={busy}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
                onClick={() => {
                  void bootstrapWorkspaces();
                }}
              >
                <RefreshCw className="h-3 w-3" />
                Reintentar
              </button>
            </div>
          )}
          {showEmpty && (
            <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
              Aún no hay espacios. Crea uno en blanco para empezar.
            </p>
          )}
          {summaries.map((item) => {
            const isActive = item.id === activeId;
            const renaming = draftMode === "rename" && renameId === item.id;
            return (
              <div
                key={item.id}
                className={cn(
                  "rounded-lg border px-3 py-2",
                  isActive ? "border-primary/50 bg-primary/5" : "border-border",
                )}
              >
                {renaming ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      className={cn(inputClassName, "min-w-0 flex-1")}
                      aria-label={`Nuevo nombre para ${item.name}`}
                      value={draftName}
                      autoFocus
                      disabled={busy}
                      onChange={(e) => setDraftName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void submitDraft();
                        // Solo cancelar el renombrado: sin stopPropagation el
                        // `Dialog` también interpretaba Escape y cerraba todo.
                        if (e.key === "Escape") {
                          e.stopPropagation();
                          cancelDraft();
                        }
                      }}
                    />
                    <button
                      type="button"
                      disabled={busy}
                      className="rounded-md bg-primary px-2.5 py-1.5 text-xs text-primary-foreground disabled:opacity-50"
                      onClick={() => void submitDraft()}
                    >
                      Guardar
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      className="rounded-md border border-border px-2.5 py-1.5 text-xs"
                      onClick={cancelDraft}
                    >
                      Cancelar
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busy || isActive || draftMode !== "idle"}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm disabled:cursor-default"
                      onClick={() => void handleSwitch(item.id)}
                      title={isActive ? "Espacio activo" : "Abrir este espacio"}
                    >
                      {item.isDefault && (
                        <Star
                          className="h-3.5 w-3.5 shrink-0 text-amber-400"
                          aria-label="Preferido al arrancar"
                        />
                      )}
                      <span className="truncate font-medium">{item.name}</span>
                      {isActive && (
                        <Check className="h-3.5 w-3.5 shrink-0 text-primary" />
                      )}
                    </button>
                    <span className="hidden text-[10px] text-muted-foreground sm:inline">
                      {formatDate(item.updatedAt)}
                    </span>
                    <button
                      type="button"
                      aria-label={`Renombrar ${item.name}`}
                      disabled={busy || draftMode !== "idle"}
                      className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-40"
                      onClick={() => startRename(item.id, item.name)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {!isActive && summaries.length > 1 && (
                      <button
                        type="button"
                        aria-label={`Eliminar ${item.name}`}
                        disabled={busy || draftMode !== "idle"}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
                        onClick={() => void handleDelete(item.id, item.name)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <section
          aria-labelledby="workspace-prefs-heading"
          className="space-y-3 border-t border-border pt-4"
        >
          <h3 id="workspace-prefs-heading" className="text-sm font-medium">
            Preferencias del espacio activo
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Se guardan en el servidor con el documento del espacio.
          </p>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={autoSave}
              disabled={busy}
              onChange={(e) => handleAutoSave(e.target.checked)}
            />
            <span>
              Autoguardado al cambiar layout o gráficos
              <span className="block text-[11px] text-muted-foreground">
                Al desactivarlo, los cambios quedan sin guardar hasta que pulses
                «Guardar actual».
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={isPreferred}
              disabled={busy || prefBusy || !activeId}
              onChange={(e) => void handlePreferred(e.target.checked)}
            />
            <span>
              Preferido al arrancar
              <span className="block text-[11px] text-muted-foreground">
                Solo hay un preferido por cuenta; es la reserva cuando este
                dispositivo no tiene último espacio activo.
              </span>
            </span>
          </label>
          <div className="space-y-1.5 text-sm">
            <p className="font-medium">Plantilla para gráficos nuevos</p>
            <p className="text-[11px] text-muted-foreground">
              {templateChart
                ? `Plantilla activa: ${templateChart.label}. Los gráficos que abras después copiarán su configuración en vivo.`
                : "Sin plantilla: los gráficos nuevos usan los valores por defecto del espacio."}
            </p>
            <button
              type="button"
              disabled={busy || !canPinActiveChart}
              onClick={() => toggleNewChartTemplatePin()}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            >
              {activeChartIsTemplate
                ? "Quitar plantilla del gráfico activo"
                : "Usar el gráfico activo como plantilla"}
            </button>
            {!canPinActiveChart && (
              <p className="text-[11px] text-muted-foreground">
                Abre un gráfico en Trading para poder anclarlo como plantilla.
              </p>
            )}
          </div>
        </section>

        <section
          aria-labelledby="workspace-device-heading"
          className="space-y-3 border-t border-border pt-4"
        >
          <h3 id="workspace-device-heading" className="text-sm font-medium">
            Diseño en este dispositivo
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Paneles y anchos no viajan al servidor: escritorio y portátil no se
            pisan.
          </p>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Diseño de Mercado</span>
            <select
              value={namedLayoutId ?? ""}
              disabled={busy}
              onChange={(e) => {
                const value = e.target.value;
                if (
                  value === "simple" ||
                  value === "trader" ||
                  value === "analista"
                ) {
                  applyNamedLayout(value satisfies NamedLayoutId);
                }
              }}
              className="max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {namedLayoutId == null ? (
                <option value="" disabled>
                  Personalizado
                </option>
              ) : null}
              {(Object.keys(NAMED_LAYOUT_LABELS) as NamedLayoutId[]).map(
                (id) => (
                  <option key={id} value={id}>
                    {NAMED_LAYOUT_LABELS[id]}
                  </option>
                ),
              )}
            </select>
          </label>
          <button
            type="button"
            disabled={busy}
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            onClick={handleResetLayout}
          >
            Restablecer paneles Trading
          </button>
        </section>

        {notice && (
          <p className="text-xs text-muted-foreground" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        {(draftMode === "create" || draftMode === "duplicate") && (
          <div className="space-y-3 rounded-lg border border-border p-3">
            <p className="text-sm font-medium">
              {draftMode === "create"
                ? "Nuevo espacio (en blanco)"
                : "Duplicar espacio activo"}
            </p>
            <FieldRow
              label="Nombre"
              hint={
                draftMode === "create"
                  ? "Sin gráficos ni listas del actual"
                  : "Copia gráficos, listas y dibujos del activo"
              }
            >
              <input
                className={inputClassName}
                value={draftName}
                autoFocus
                disabled={busy}
                onChange={(e) => setDraftName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitDraft();
                  if (e.key === "Escape") {
                    e.stopPropagation();
                    cancelDraft();
                  }
                }}
              />
            </FieldRow>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
                onClick={() => void submitDraft()}
              >
                {draftMode === "create" ? "Crear" : "Duplicar"}
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1.5 text-sm"
                onClick={cancelDraft}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          <button
            type="button"
            disabled={busy || draftMode !== "idle"}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            onClick={startCreate}
          >
            <Plus className="h-4 w-4" />
            Nuevo (blanco)
          </button>
          <button
            type="button"
            disabled={busy || draftMode !== "idle" || !activeId}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            onClick={startDuplicate}
          >
            <Copy className="h-4 w-4" />
            Duplicar activo
          </button>
          <button
            type="button"
            disabled={busy || !activeId}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
            onClick={() => {
              exportJson();
              setNotice(
                "JSON descargado. Exportar no guarda: los cambios siguen sin guardar.",
              );
            }}
            title="Descargar .bolsa-workspace.json"
          >
            <Download className="h-4 w-4" />
            Exportar JSON
          </button>
          <button
            type="button"
            disabled={busy || isSaving || !activeId}
            className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
            onClick={() => void saveToServer()}
          >
            {isSaving ? "Guardando…" : "Guardar actual"}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
