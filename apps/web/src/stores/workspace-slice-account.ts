import { api, ApiError } from "@/lib/api";
import {
  mergeWorkspaceChartState,
  totalChartDrawings,
  totalSnapshotDrawings,
  workspaceTimestamp,
} from "@/lib/chart-list-snapshot";
import {
  buildWorkspacePayload,
  DEFAULT_DOCK_LAYOUT,
  readLegacyDockFromStorage,
  readLegacyWorkspaceFromStorage,
} from "@/lib/workspace-payload";
import {
  type WorkspaceSlice,
  DEFAULT_WORKSPACE,
  applyServerWorkspace,
  normalizeWorkspace,
  chartPersistBackupFrom,
  writeChartPersistBackupSync,
  buildBackupWorkspaceDoc,
  prepareWorkspaceForSave,
  requestWorkspaceAutoSave,
  scheduleWorkspaceServerSave,
  downloadJson,
  applyLocalDrawToolFavorites,
  applyLocalDrawToolSession,
  nextCopyName,
  workspaceBackupPatch,
} from "./workspace-store-core";

let saveQueued = false;

export const accountSlice: WorkspaceSlice = (get, set) => ({
  getActiveChartTab: () => {
    const { charts, activeChartId } = get().workspace;
    return charts.find((tab) => tab.id === activeChartId) ?? charts[0] ?? null;
  },
  bootstrapWorkspaces: async () => {
    try {
      const list = await api.getWorkspaces();
      let summaries = list.data;
      if (summaries.length === 0) {
        const legacyDoc = readLegacyWorkspaceFromStorage();
        const legacyDock = readLegacyDockFromStorage();
        const created = await api.createWorkspace({
          name: legacyDoc?.name ?? "Espacio de trabajo",
          document: legacyDoc ?? DEFAULT_WORKSPACE,
          dockLayout: legacyDock ?? DEFAULT_DOCK_LAYOUT,
          isDefault: true,
        });
        summaries = [
          {
            id: created.data.id,
            name: created.data.name,
            isDefault: created.data.isDefault,
            updatedAt: created.data.updatedAt,
          },
        ];
        const applied = applyServerWorkspace(created.data);
        set({
          ...applied,
          ...workspaceBackupPatch(
            applied.activeWorkspaceId,
            get().recents,
            applied.workspace,
          ),
          workspaceSummaries: summaries,
          hydrated: true,
          loadError: null,
        });
        return;
      }

      const { activeWorkspaceId } = get();
      const target =
        summaries.find((s) => s.id === activeWorkspaceId) ??
        summaries.find((s) => s.isDefault) ??
        summaries[0];
      if (!target) {
        set({ hydrated: true });
        return;
      }
      const detail = await api.getWorkspace(target.id);
      const applied = applyServerWorkspace(detail.data);
      let workspace = applied.workspace;
      const backup = get().chartPersistBackup;
      let backupWasNewer = false;
      if (backup) {
        const backupDoc = buildBackupWorkspaceDoc(backup);
        backupWasNewer =
          workspaceTimestamp(backupDoc) > workspaceTimestamp(workspace);
        workspace = mergeWorkspaceChartState(
          backupWasNewer ? backupDoc : workspace,
          backupWasNewer ? workspace : backupDoc,
        );
      }
      workspace = applyLocalDrawToolFavorites(workspace);
      workspace = applyLocalDrawToolSession(workspace);
      workspace.id = applied.workspace.id;
      workspace.name = applied.workspace.name;
      set({
        workspace,
        activeWorkspaceId: applied.activeWorkspaceId,
        chartPersistBackup: chartPersistBackupFrom(workspace),
        workspaceSummaries: summaries,
        hydrated: true,
        isDirty: backupWasNewer,
        loadError: null,
      });
    } catch (err) {
      const legacyDoc = readLegacyWorkspaceFromStorage();
      const backup = get().chartPersistBackup;
      const loadError =
        err instanceof Error ? err.message : "No se pudo cargar el espacio";
      if (legacyDoc) {
        let workspace = normalizeWorkspace(legacyDoc);
        if (backup) {
          const backupDoc = buildBackupWorkspaceDoc(backup);
          workspace = mergeWorkspaceChartState(backupDoc, workspace);
        }
        workspace = applyLocalDrawToolFavorites(workspace);
        workspace = applyLocalDrawToolSession(workspace);
        set({
          workspace,
          chartPersistBackup: chartPersistBackupFrom(workspace),
          hydrated: true,
          isDirty: true,
          loadError,
        });
      } else if (backup) {
        const backupDoc = buildBackupWorkspaceDoc(backup);
        set({
          workspace: backupDoc,
          chartPersistBackup: chartPersistBackupFrom(backupDoc),
          hydrated: true,
          isDirty: true,
          loadError,
        });
      } else {
        set({ hydrated: true, loadError });
      }
      if (err instanceof ApiError) {
        console.warn("Workspace bootstrap:", err.message);
      }
    }
  },
  refreshSummaries: async () => {
    const list = await api.getWorkspaces();
    set({ workspaceSummaries: list.data });
  },
  saveToServer: async () => {
    if (!get().hydrated) return;
    const id = get().activeWorkspaceId;
    if (!id) return;
    if (get().isSaving) {
      saveQueued = true;
      return;
    }

    set({ isSaving: true });
    try {
      const prepared = prepareWorkspaceForSave(get().workspace);
      const backup = chartPersistBackupFrom(prepared);
      writeChartPersistBackupSync(
        get().activeWorkspaceId,
        get().recents,
        backup,
      );
      // No sustituir `workspace` aquí: un set intermedio + await permite que un
      // sync/merge deje menos pestañas al volver. Solo enviamos `prepared`.
      const payload = buildWorkspacePayload(prepared);
      const response = await api.updateWorkspace(id, {
        name: prepared.name,
        document: payload.document,
        dockLayout: payload.dockLayout,
      });
      const live = get().workspace;
      // Autoridad post-PUT = pestañas vivas ahora. No reinyectar `prepared`
      // (si el usuario cerró tabs durante el await, la unión antigua las resucitaba).
      const preparedInstr = new Set(
        prepared.charts.map((c) => c.instrumentId).filter(Boolean),
      );
      const openedDuringSave = live.charts.some(
        (tab) => tab.instrumentId && !preparedInstr.has(tab.instrumentId),
      );
      const nextWorkspace = {
        ...live,
        name: response.data.name,
        updatedAt: response.data.updatedAt ?? live.updatedAt,
      };
      set({
        workspace: nextWorkspace,
        chartPersistBackup: chartPersistBackupFrom(nextWorkspace),
        activeWorkspaceId: response.data.id,
        isDirty: openedDuringSave,
        isSaving: false,
      });
      if (openedDuringSave) saveQueued = true;
      await get().refreshSummaries();
    } catch (err) {
      set({ isSaving: false });
      if (err instanceof ApiError) {
        window.alert(`No se pudo guardar: ${err.message}`);
      }
      throw err;
    } finally {
      if (saveQueued) {
        saveQueued = false;
        void get().saveToServer();
      }
    }
  },
  requestAutoSave: (immediate = false) => {
    requestWorkspaceAutoSave(get, immediate);
  },
  flushWorkspaceOnUnload: () => {
    const state = get();
    if (!state.hydrated || !state.activeWorkspaceId) return;
    const prepared = prepareWorkspaceForSave(state.workspace);
    const backup = chartPersistBackupFrom(prepared);
    writeChartPersistBackupSync(state.activeWorkspaceId, state.recents, backup);
    const payload = buildWorkspacePayload(prepared);
    api.updateWorkspaceKeepalive(state.activeWorkspaceId, {
      name: prepared.name,
      document: payload.document,
      dockLayout: payload.dockLayout,
    });
  },
  syncWorkspaceFromServer: async () => {
    const id = get().activeWorkspaceId;
    if (!id || !get().hydrated || get().isDirty || get().isSaving) return;
    try {
      const detail = await api.getWorkspace(id);
      const serverBase = normalizeWorkspace(detail.data.document);
      serverBase.id = detail.data.id;
      serverBase.name = detail.data.name;
      const local = get().workspace;
      const serverDrawings =
        totalChartDrawings(serverBase.charts) +
        totalSnapshotDrawings(serverBase.chartStateByListInstrument);
      const localDrawings =
        totalChartDrawings(local.charts) +
        totalSnapshotDrawings(local.chartStateByListInstrument);
      const serverTs = detail.data.updatedAt ?? serverBase.updatedAt;
      if (serverDrawings <= localDrawings && serverTs <= local.updatedAt)
        return;

      // Preferir el set de pestañas local en pulls en background (este dispositivo).
      const merged = mergeWorkspaceChartState(local, serverBase);
      merged.id = local.id;
      merged.name = local.name;
      if (
        local.activeChartId &&
        merged.charts.some((t) => t.id === local.activeChartId)
      ) {
        merged.activeChartId = local.activeChartId;
      }
      set({
        workspace: merged,
        chartPersistBackup: chartPersistBackupFrom(merged),
      });
    } catch {
      // Sin conexión o sesión — ignorar
    }
  },
  switchWorkspace: async (workspaceId) => {
    const { isDirty, activeWorkspaceId } = get();
    if (workspaceId === activeWorkspaceId) return;
    if (
      isDirty &&
      !window.confirm(
        "Hay cambios sin guardar. ¿Cambiar de espacio de trabajo?",
      )
    ) {
      return;
    }
    const detail = await api.getWorkspace(workspaceId);
    const applied = applyServerWorkspace(detail.data);
    const recents = [
      workspaceId,
      ...get().recents.filter((id) => id !== workspaceId),
    ].slice(0, 8);
    set({
      ...applied,
      ...workspaceBackupPatch(
        applied.activeWorkspaceId,
        recents,
        applied.workspace,
      ),
      recents,
      loadError: null,
    });
  },
  createWorkspace: async (name) => {
    const fresh = normalizeWorkspace({ ...DEFAULT_WORKSPACE, name });
    const payload = buildWorkspacePayload(fresh);
    const created = await api.createWorkspace({
      name,
      document: payload.document,
      dockLayout: payload.dockLayout,
    });
    const applied = applyServerWorkspace(created.data);
    set({
      ...applied,
      ...workspaceBackupPatch(
        applied.activeWorkspaceId,
        get().recents,
        applied.workspace,
      ),
      isDirty: false,
    });
    await get().refreshSummaries();
  },
  duplicateWorkspace: async (name) => {
    const prepared = prepareWorkspaceForSave(get().workspace);
    const newName =
      name?.trim() ||
      nextCopyName(
        prepared.name,
        get().workspaceSummaries.map((item) => item.name),
      );
    const cloneDoc = normalizeWorkspace({
      ...prepared,
      name: newName,
      updatedAt: new Date().toISOString(),
    });
    const payload = buildWorkspacePayload(cloneDoc);
    const created = await api.createWorkspace({
      name: newName,
      document: { ...payload.document, name: newName },
      dockLayout: payload.dockLayout,
      isDefault: false,
    });
    const applied = applyServerWorkspace(created.data);
    const recents = [
      created.data.id,
      ...get().recents.filter((id) => id !== created.data.id),
    ].slice(0, 8);
    set({
      ...applied,
      ...workspaceBackupPatch(
        applied.activeWorkspaceId,
        recents,
        applied.workspace,
      ),
      isDirty: false,
      recents,
    });
    await get().refreshSummaries();
  },
  renameWorkspaceById: async (workspaceId, name) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const response = await api.updateWorkspace(workspaceId, {
      name: trimmed,
    });
    if (workspaceId === get().activeWorkspaceId) {
      set((state) => ({
        workspace: {
          ...state.workspace,
          name: response.data.name,
          updatedAt: response.data.updatedAt ?? state.workspace.updatedAt,
        },
      }));
    }
    await get().refreshSummaries();
  },
  reloadActiveFromServer: async () => {
    const id = get().activeWorkspaceId;
    if (!id) return;
    if (
      get().isDirty &&
      !window.confirm(
        "Hay cambios sin guardar. ¿Recargar el espacio desde el servidor?",
      )
    ) {
      return;
    }
    const detail = await api.getWorkspace(id);
    const applied = applyServerWorkspace(detail.data);
    set({
      ...applied,
      ...workspaceBackupPatch(
        applied.activeWorkspaceId,
        get().recents,
        applied.workspace,
      ),
      isDirty: false,
    });
  },
  deleteWorkspaceById: async (workspaceId) => {
    await api.deleteWorkspace(workspaceId);
    // Un id borrado no puede seguir en `recents` (el bootstrap lo ignoraría,
    // pero ensucia el orden de arranque).
    const recents = get().recents.filter((id) => id !== workspaceId);
    set({ recents });
    await get().refreshSummaries();
    const { activeWorkspaceId } = get();
    if (workspaceId === activeWorkspaceId) {
      const defaultWs = await api.getDefaultWorkspace();
      const applied = applyServerWorkspace(defaultWs.data);
      set({
        ...applied,
        ...workspaceBackupPatch(
          applied.activeWorkspaceId,
          recents,
          applied.workspace,
        ),
      });
    }
  },
  rename: (name) =>
    set((state) => ({
      workspace: {
        ...state.workspace,
        name,
        updatedAt: new Date().toISOString(),
      },
      isDirty: true,
    })),
  markDirty: () => set({ isDirty: true }),
  touchWorkspace: () =>
    set((state) => ({
      isDirty: true,
      workspace: {
        ...state.workspace,
        updatedAt: new Date().toISOString(),
      },
    })),
  save: () => {
    scheduleWorkspaceServerSave(get);
  },
  exportJson: () => {
    const { workspace } = get();
    // Exportar NO es guardar: el punto ámbar debe seguir visible para que un
    // pull del servidor no pise cambios sin guardar.
    downloadJson(
      `${workspace.name.replace(/\s+/g, "-").toLowerCase()}.bolsa-workspace.json`,
      prepareWorkspaceForSave(workspace),
    );
  },
  reload: () => {
    void get().reloadActiveFromServer();
  },
  setAutoSave: (enabled) => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        preferences: { ...state.workspace.preferences, autoSave: enabled },
      },
      isDirty: true,
    }));
    // Es una acción explícita: se persiste aunque se acabe de apagar el
    // autoguardado (el debounce lo ignora justo en ese caso).
    void get().saveToServer();
  },
  setPreferred: async (enabled) => {
    const id = get().activeWorkspaceId;
    if (!id) return;
    await api.updateWorkspace(id, { isDefault: enabled });
    // Solo el flag de arranque: no tocamos `isDirty` para no ocultar cambios
    // reales del documento que siguen sin guardar.
    set((state) => ({
      workspace: {
        ...state.workspace,
        preferences: { ...state.workspace.preferences, openOnStartup: enabled },
      },
    }));
    await get().refreshSummaries();
  },
});
