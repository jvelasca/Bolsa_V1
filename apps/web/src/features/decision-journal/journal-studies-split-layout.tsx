/**
 * Split lista | ficha — patrón hub Instrumentos (responsive · colapsable).
 */

import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import { cn } from "@/lib/utils";

export const MIN_JOURNAL_STUDIES_LIST_PCT = 32;
export const MAX_JOURNAL_STUDIES_LIST_PCT = 78;
export const DEFAULT_JOURNAL_STUDIES_LIST_PCT = 58;
export const MIN_JOURNAL_STUDIES_STACK_PCT = 28;
export const MAX_JOURNAL_STUDIES_STACK_PCT = 72;
export const DEFAULT_JOURNAL_STUDIES_STACK_PCT = 46;

export function clampJournalStudiesListPct(value: number): number {
  return Math.min(
    MAX_JOURNAL_STUDIES_LIST_PCT,
    Math.max(MIN_JOURNAL_STUDIES_LIST_PCT, Math.round(value)),
  );
}

export function clampJournalStudiesStackPct(value: number): number {
  return Math.min(
    MAX_JOURNAL_STUDIES_STACK_PCT,
    Math.max(MIN_JOURNAL_STUDIES_STACK_PCT, Math.round(value)),
  );
}

const SPLIT_STORAGE_KEY = "bolsa.journal-studies-split.v1";

export function loadJournalStudiesSplitPrefs(): {
  listWidthPct: number;
  stackHeightPct: number;
} {
  if (typeof window === "undefined") {
    return {
      listWidthPct: DEFAULT_JOURNAL_STUDIES_LIST_PCT,
      stackHeightPct: DEFAULT_JOURNAL_STUDIES_STACK_PCT,
    };
  }
  try {
    const raw = window.localStorage.getItem(SPLIT_STORAGE_KEY);
    if (!raw) {
      return {
        listWidthPct: DEFAULT_JOURNAL_STUDIES_LIST_PCT,
        stackHeightPct: DEFAULT_JOURNAL_STUDIES_STACK_PCT,
      };
    }
    const parsed = JSON.parse(raw) as {
      listWidthPct?: number;
      stackHeightPct?: number;
    };
    return {
      listWidthPct: clampJournalStudiesListPct(
        parsed.listWidthPct ?? DEFAULT_JOURNAL_STUDIES_LIST_PCT,
      ),
      stackHeightPct: clampJournalStudiesStackPct(
        parsed.stackHeightPct ?? DEFAULT_JOURNAL_STUDIES_STACK_PCT,
      ),
    };
  } catch {
    return {
      listWidthPct: DEFAULT_JOURNAL_STUDIES_LIST_PCT,
      stackHeightPct: DEFAULT_JOURNAL_STUDIES_STACK_PCT,
    };
  }
}

export function persistJournalStudiesSplitPrefs(prefs: {
  listWidthPct: number;
  stackHeightPct: number;
}): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    SPLIT_STORAGE_KEY,
    JSON.stringify({
      listWidthPct: clampJournalStudiesListPct(prefs.listWidthPct),
      stackHeightPct: clampJournalStudiesStackPct(prefs.stackHeightPct),
    }),
  );
}

function pxToPct(px: number, total: number): number {
  return total > 0 ? (px / total) * 100 : 0;
}

export function JournalStudiesSplitLayout({
  list,
  detail,
  showDetail,
  detailCollapsed = false,
  isWide,
  listWidthPct,
  stackHeightPct,
  onListWidthPctChange,
  onStackHeightPctChange,
  className,
}: {
  list: ReactNode;
  detail: ReactNode;
  showDetail: boolean;
  detailCollapsed?: boolean;
  isWide: boolean;
  listWidthPct: number;
  stackHeightPct: number;
  onListWidthPctChange: (pct: number) => void;
  onStackHeightPctChange: (pct: number) => void;
  className?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [liveListPct, setLiveListPct] = useState(listWidthPct);
  const [liveStackPct, setLiveStackPct] = useState(stackHeightPct);
  const [dragging, setDragging] = useState(false);
  const pendingList = useRef(listWidthPct);
  const pendingStack = useRef(stackHeightPct);

  useEffect(() => {
    if (dragging) return;
    pendingList.current = listWidthPct;
    setLiveListPct(listWidthPct);
  }, [listWidthPct, dragging]);

  useEffect(() => {
    if (dragging) return;
    pendingStack.current = stackHeightPct;
    setLiveStackPct(stackHeightPct);
  }, [stackHeightPct, dragging]);

  const adjustListWidth = useCallback((deltaPx: number) => {
    const width = rootRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    const next = clampJournalStudiesListPct(
      pendingList.current + pxToPct(deltaPx, width),
    );
    pendingList.current = next;
    setLiveListPct(next);
  }, []);

  const adjustStackHeight = useCallback((deltaPx: number) => {
    const height = rootRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampJournalStudiesStackPct(
      pendingStack.current + pxToPct(deltaPx, height),
    );
    pendingStack.current = next;
    setLiveStackPct(next);
  }, []);

  const listPct = clampJournalStudiesListPct(liveListPct);
  const stackPct = clampJournalStudiesStackPct(liveStackPct);

  if (!showDetail) {
    return (
      <div
        ref={rootRef}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-border/60",
          className,
        )}
      >
        <div className="h-full min-h-0 overflow-hidden">{list}</div>
      </div>
    );
  }

  if (detailCollapsed) {
    return (
      <div
        ref={rootRef}
        className={cn(
          "flex min-h-0 flex-1 overflow-hidden rounded-md border border-border/60",
          isWide ? "flex-row" : "flex-col",
          className,
        )}
      >
        <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{list}</div>
        <div
          className={cn(
            "shrink-0 overflow-hidden bg-muted/20",
            isWide ? "w-10" : "h-10 border-t border-border/60",
          )}
        >
          {detail}
        </div>
      </div>
    );
  }

  if (!isWide) {
    return (
      <div
        ref={rootRef}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-border/60",
          className,
        )}
      >
        <div
          className="min-h-0 shrink-0 overflow-hidden"
          style={{ height: `${stackPct}%` }}
        >
          {list}
        </div>
        <PanelResizeHandle
          label="Redimensionar lista y ficha"
          orientation="horizontal"
          className={cn(dragging && "bg-primary/70")}
          onDragStart={() => setDragging(true)}
          onDrag={adjustStackHeight}
          onDragEnd={() => {
            setDragging(false);
            onStackHeightPctChange(pendingStack.current);
          }}
        />
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-card">
          {detail}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={rootRef}
      className={cn(
        "flex min-h-0 flex-1 overflow-hidden rounded-md border border-border/60",
        className,
      )}
    >
      <div
        className="min-h-0 shrink-0 overflow-hidden"
        style={{ width: `${listPct}%` }}
      >
        {list}
      </div>
      <PanelResizeHandle
        label="Redimensionar lista y ficha"
        orientation="vertical"
        className={cn(dragging && "bg-primary/70")}
        onDragStart={() => setDragging(true)}
        onDrag={adjustListWidth}
        onDragEnd={() => {
          setDragging(false);
          onListWidthPctChange(pendingList.current);
        }}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-l border-border/40 bg-card">
        {detail}
      </div>
    </div>
  );
}
