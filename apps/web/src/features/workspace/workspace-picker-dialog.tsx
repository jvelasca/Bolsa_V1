/**
 * Gestor de espacios de trabajo (chip de la barra superior / Configuración → General).
 *
 * Operativa:
 * - Cambiar de espacio (confirma si dirty)
 * - Nuevo en blanco / Duplicar activo / Renombrar inline / Eliminar
 * - Autoguardado y «Preferido al arrancar» (estrella = `isDefault`)
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
  Star,
  Trash2,
} from "lucide-react";
import { Dialog, FieldRow, inputClassName } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

type DraftMode = "idle" | "create" | "rename" | "duplicate";

export function WorkspacePickerDialog() {
  const open = useUiStore((s) => s.workspacePickerOpen);
  const close = useUiStore((s) => s.closeWorkspacePicker);
  const summaries = useWorkspaceStore((s) => s.workspaceSummaries);
  const activeId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const activeName = useWorkspaceStore((s) => s.workspace.name);
  const hydrated = useWorkspaceStore((s) => s.hydrated);
  const isDirty = useWorkspaceStore((s) => s.isDirty);
  const isSaving = useWorkspaceStore((s) => s.isSaving);
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace);
  const createWorkspace = useWorkspaceStore((s) => s.createWorkspace);
  const duplicateWorkspace = useWorkspaceStore((s) => s.duplicateWorkspace);
  const renameWorkspaceById = useWorkspaceStore((s) => s.renameWorkspaceById);
  const deleteWorkspaceById = useWorkspaceStore((s) => s.deleteWorkspaceById);
  const saveToServer = useWorkspaceStore((s) => s.saveToServer);
  const exportJson = useWorkspaceStore((s) => s.exportJson);
  const setOpenOnStartup = useWorkspaceStore((s) => s.setOpenOnStartup);
  const openOnStartup = useWorkspaceStore(
    (s) => s.workspace.preferences.openOnStartup,
  );
  const autoSave = useWorkspaceStore((s) => s.workspace.preferences.autoSave);
  const setAutoSave = useWorkspaceStore((s) => s.setAutoSave);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftMode, setDraftMode] = useState<DraftMode>("idle");
  const [draftName, setDraftName] = useState("");
  const [renameId, setRenameId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setDraftMode("idle");
      setDraftName("");
      setRenameId(null);
      setError(null);
    }
  }, [open]);

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
        setDraftMode("idle");
        setRenameId(null);
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
    } catch {
      setError("No se pudo eliminar el espacio de trabajo.");
    } finally {
      setBusy(false);
    }
  }

  const showEmpty = hydrated && summaries.length === 0;
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
      <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
        <label className="inline-flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={autoSave}
            disabled={busy}
            onChange={(e) => setAutoSave(e.target.checked)}
          />
          Autoguardado
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={openOnStartup}
            disabled={busy}
            onChange={(e) => {
              setOpenOnStartup(e.target.checked);
              if (e.target.checked) void saveToServer();
            }}
          />
          Preferido al arrancar
          <span title="Si no hay último activo en este dispositivo, se abre este espacio">
            <Star className="inline h-3 w-3 text-amber-400" />
          </span>
        </label>
        {isDirty ? (
          <span className="text-amber-500">
            Cambios sin guardar en el activo
          </span>
        ) : null}
      </div>

      <div className="space-y-2">
        {showLoading && (
          <p className="text-sm text-muted-foreground">Cargando espacios…</p>
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
                    value={draftName}
                    autoFocus
                    disabled={busy}
                    onChange={(e) => setDraftName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void submitDraft();
                      if (e.key === "Escape") {
                        setDraftMode("idle");
                        setRenameId(null);
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
                    onClick={() => {
                      setDraftMode("idle");
                      setRenameId(null);
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={busy || isActive}
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
                    {new Date(item.updatedAt).toLocaleDateString("es-ES")}
                  </span>
                  <button
                    type="button"
                    title="Renombrar"
                    disabled={busy}
                    className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                    onClick={() => startRename(item.id, item.name)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  {!isActive && summaries.length > 1 && (
                    <button
                      type="button"
                      title="Eliminar"
                      disabled={busy}
                      className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
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

      {(draftMode === "create" || draftMode === "duplicate") && (
        <div className="mt-4 space-y-3 rounded-lg border border-border p-3">
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
              disabled={busy}
              className="rounded-md border border-border px-3 py-1.5 text-sm"
              onClick={() => setDraftMode("idle")}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
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
          onClick={() => exportJson()}
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
    </Dialog>
  );
}
