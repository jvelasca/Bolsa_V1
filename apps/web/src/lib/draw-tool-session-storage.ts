import type { ChartDrawTool } from "@bolsa/shared";
import type { DrawingToolGroupId } from "@bolsa/shared";
import { IMPLEMENTED_DRAW_TOOLS, drawToolGroup } from "@bolsa/shared";
import { useUiStore } from "@/stores/ui-store";

const STORAGE_KEY = "bolsa-chart-draw-tool-session";

export type DrawToolSession = {
  chartDrawTool: ChartDrawTool;
  lastDrawToolByGroup: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
};

function isImplementedDrawTool(tool: unknown): tool is ChartDrawTool {
  return (
    typeof tool === "string" &&
    IMPLEMENTED_DRAW_TOOLS.includes(tool as ChartDrawTool)
  );
}

function normalizeSession(raw: unknown): DrawToolSession | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as {
    state?: {
      chartDrawTool?: ChartDrawTool;
      lastDrawToolByGroup?: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
    };
    chartDrawTool?: ChartDrawTool;
    lastDrawToolByGroup?: Partial<Record<DrawingToolGroupId, ChartDrawTool>>;
  };
  const inner = record.state ?? record;
  const chartDrawTool = inner.chartDrawTool;
  if (!isImplementedDrawTool(chartDrawTool)) return null;
  const lastDrawToolByGroup: Partial<
    Record<DrawingToolGroupId, ChartDrawTool>
  > = {};
  for (const [group, tool] of Object.entries(inner.lastDrawToolByGroup ?? {})) {
    if (isImplementedDrawTool(tool)) {
      lastDrawToolByGroup[group as DrawingToolGroupId] = tool;
    }
  }
  return { chartDrawTool, lastDrawToolByGroup };
}

export function readDrawToolSessionLocal(): DrawToolSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return normalizeSession(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function writeDrawToolSessionLocal(session: DrawToolSession): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ state: session, version: 0 }),
    );
  } catch {
    // quota / private mode
  }
}

export function applyDrawToolSessionToUi(session: DrawToolSession): void {
  const cursorLast = session.lastDrawToolByGroup.cursor;
  const toolGroup = drawToolGroup(session.chartDrawTool);
  const restoreTool =
    toolGroup !== "cursor" && cursorLast
      ? cursorLast
      : session.chartDrawTool === "select" &&
          cursorLast &&
          cursorLast !== "select"
        ? cursorLast
        : session.chartDrawTool;
  useUiStore.setState({
    chartDrawTool: restoreTool,
    lastDrawToolByGroup: session.lastDrawToolByGroup,
  });
  writeDrawToolSessionLocal({
    chartDrawTool: restoreTool,
    lastDrawToolByGroup: session.lastDrawToolByGroup,
  });
}

export function drawToolSessionFromUi(): DrawToolSession {
  const { chartDrawTool, lastDrawToolByGroup } = useUiStore.getState();
  return { chartDrawTool, lastDrawToolByGroup };
}
