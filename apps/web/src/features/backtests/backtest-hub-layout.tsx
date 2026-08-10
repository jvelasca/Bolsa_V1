import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import {
  clampWizardStackHeightPct,
  clampWizardWidthPct,
  loadBacktestSplitLayout,
  pxToPct,
  saveBacktestSplitLayout,
  type BacktestSplitLayoutPrefs,
} from "@/features/backtests/backtest-split-layout";
import { cn } from "@/lib/utils";

type Props = {
  wizard: ReactNode;
  result: ReactNode;
  /** Desktop side-by-side (≥ lg). Mobile stacks with vertical resize. */
  isWide: boolean;
  className?: string;
};

function ScrollPane({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "h-full min-h-0 overflow-auto overscroll-contain",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function BacktestHubLayout({
  wizard,
  result,
  isWide,
  className,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [prefs, setPrefs] = useState<BacktestSplitLayoutPrefs>(() =>
    loadBacktestSplitLayout(),
  );
  const [liveWizardPct, setLiveWizardPct] = useState(prefs.wizardWidthPct);
  const [liveStackPct, setLiveStackPct] = useState(prefs.wizardStackHeightPct);
  const pendingWizard = useRef(prefs.wizardWidthPct);
  const pendingStack = useRef(prefs.wizardStackHeightPct);

  useEffect(() => {
    pendingWizard.current = prefs.wizardWidthPct;
    setLiveWizardPct(prefs.wizardWidthPct);
  }, [prefs.wizardWidthPct]);

  useEffect(() => {
    pendingStack.current = prefs.wizardStackHeightPct;
    setLiveStackPct(prefs.wizardStackHeightPct);
  }, [prefs.wizardStackHeightPct]);

  const persist = useCallback((patch: Partial<BacktestSplitLayoutPrefs>) => {
    setPrefs((current) => {
      const next = { ...current, ...patch };
      saveBacktestSplitLayout(next);
      return next;
    });
  }, []);

  const adjustWizardWidth = useCallback((deltaPx: number) => {
    const width = rootRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    const next = clampWizardWidthPct(
      pendingWizard.current + pxToPct(deltaPx, width),
    );
    pendingWizard.current = next;
    setLiveWizardPct(next);
  }, []);

  const adjustStackHeight = useCallback((deltaPx: number) => {
    const height = rootRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampWizardStackHeightPct(
      pendingStack.current + pxToPct(deltaPx, height),
    );
    pendingStack.current = next;
    setLiveStackPct(next);
  }, []);

  const wizardPct = clampWizardWidthPct(liveWizardPct);
  const stackPct = clampWizardStackHeightPct(liveStackPct);

  if (!isWide) {
    return (
      <div
        ref={rootRef}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border",
          className,
        )}
      >
        <div
          className="min-h-0 shrink-0 overflow-hidden"
          style={{ height: `${stackPct}%` }}
        >
          <ScrollPane className="p-1">{wizard}</ScrollPane>
        </div>
        <PanelResizeHandle
          label="Redimensionar formulario y resultado"
          orientation="horizontal"
          onDrag={adjustStackHeight}
          onDragEnd={() =>
            persist({ wizardStackHeightPct: pendingStack.current })
          }
        />
        <div className="min-h-0 flex-1 overflow-hidden">
          <ScrollPane className="p-1">{result}</ScrollPane>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={rootRef}
      className={cn(
        "flex min-h-0 flex-1 overflow-hidden rounded-lg border border-border",
        className,
      )}
    >
      <div
        className="min-h-0 shrink-0 overflow-hidden"
        style={{ width: `${wizardPct}%` }}
      >
        <ScrollPane className="p-1">{wizard}</ScrollPane>
      </div>
      <PanelResizeHandle
        label="Redimensionar panel de prueba y resultado"
        orientation="vertical"
        onDrag={adjustWizardWidth}
        onDragEnd={() => persist({ wizardWidthPct: pendingWizard.current })}
      />
      <div className="min-h-0 flex-1 overflow-hidden">
        <ScrollPane className="p-1">{result}</ScrollPane>
      </div>
    </div>
  );
}
