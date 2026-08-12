import { DEFAULT_LIST_CONFIG } from "@bolsa/shared";
import {
  membershipFingerprint,
  reconcileWorkspaceChartMembership,
} from "@/lib/chart-list-membership";
import {
  type WorkspaceSlice,
  mergeListConfigPatch,
  scheduleWorkspaceSettingsPersist,
} from "./workspace-store-core";

export const listSlice: WorkspaceSlice = (get, set) => ({
  updateListConfig: (patch) => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        updatedAt: new Date().toISOString(),
        list: mergeListConfigPatch(state.workspace.list, patch),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
  resetListConfig: () => {
    set((state) => ({
      workspace: {
        ...state.workspace,
        list: { ...DEFAULT_LIST_CONFIG },
        updatedAt: new Date().toISOString(),
      },
      isDirty: true,
    }));
    scheduleWorkspaceSettingsPersist(get, set);
  },
  setChartListMembership: (membership) =>
    set((state) => {
      if (
        state.chartListMembership &&
        membershipFingerprint(state.chartListMembership) ===
          membershipFingerprint(membership)
      ) {
        return state;
      }
      return { chartListMembership: membership };
    }),
  syncChartListMembership: (membership) =>
    set((state) => {
      const sameMembership =
        state.chartListMembership &&
        membershipFingerprint(state.chartListMembership) ===
          membershipFingerprint(membership);
      const workspace = reconcileWorkspaceChartMembership(
        state.workspace,
        membership,
      );
      const workspaceChanged = workspace !== state.workspace;
      if (sameMembership && !workspaceChanged) return state;
      return {
        chartListMembership: membership,
        workspace: workspaceChanged
          ? { ...workspace, updatedAt: new Date().toISOString() }
          : state.workspace,
        isDirty: workspaceChanged ? true : state.isDirty,
      };
    }),
});
