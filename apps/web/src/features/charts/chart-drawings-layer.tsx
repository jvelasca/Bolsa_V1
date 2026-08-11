import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import type { IChartApi } from "lightweight-charts";
import {
  DEFAULT_CHART_DRAW_COLOR,
  DEFAULT_DOT_HALO_RADIUS,
  DEFAULT_LINE_WIDTH,
  DEFAULT_CHANNEL_FILL_OPACITY,
  DEFAULT_BRUSH_STROKE_OPACITY,
  DEFAULT_TEXT_FONT_SIZE,
  DEFAULT_TEXT_LABEL,
  DEFAULT_RECT_FILL_OPACITY,
  FIBONACCI_LEVELS,
  FIBONACCI_TREND_EXT_LEVELS,
  GANN_GRID_DIVISIONS,
  drawingLineStyle,
  drawingLineWidth,
  isDrawingVisible,
  isPointLineDrawing,
  newChartDrawingId,
  semanticIdForDrawTool,
  semanticIdForDrawingType,
  stylePatchFromTemplate,
  resolveDrawToolStyle,
  templateMatchesDrawingType,
  drawingTypeForTool,
  DEFAULT_DRAWING_TEMPLATES,
  type ChartDrawTool,
  type ChartDrawing,
  type ChartDrawingPoint,
  type ChartDrawingVertexPatch,
  type ChartMarkerDirection,
} from "@bolsa/shared";
import type { OhlcvBarDto } from "@bolsa/shared";
import {
  channelParallelEnd,
  drawingPointToChartTime,
  drawingVertices,
  extendedLinePixels,
  fibPriceAtLevel,
  fibTimeSpan,
  fibTimeZoneLineXs,
  findDrawingVertexHit,
  gannFanRays,
  gannGridPixelBounds,
  gannSquarePixelBounds,
  hitTestDrawing,
  horzTimeToString,
  markerDirectionFromDelta,
  markerRotation,
  normalizeRect,
  rayLinePixels,
  snapGannSquareP2,
  timeToPixelX,
  priceToPixelY,
  strokeDasharray,
  wholeDrawingPatch,
  pitchforkRays,
  type ChartPriceSeries,
} from "@/features/charts/chart-drawing-utils";
import {
  THREE_POINT_DRAW_TOOLS,
  TWO_POINT_DRAW_TOOLS,
} from "@/features/charts/chart-drawing-tools";
import {
  canInteractWithDrawings,
  isShapeDrawTool,
  shouldCaptureDrawingPointer,
} from "@/features/charts/chart-draw-tool-utils";
import {
  computeRegressionLine,
  defaultInfoLineLabel,
  lineAngleDegrees,
} from "@/features/charts/chart-drawing-regression";
import { useWorkspaceStore } from "@/stores/workspace-store";

interface ChartDrawingsLayerProps {
  chart: IChartApi | null;
  series: ChartPriceSeries | null;
  container: HTMLDivElement | null;
  height: number;
  bars?: OhlcvBarDto[];
  drawings: ChartDrawing[];
  tool: ChartDrawTool;
  selectedId: string | null;
  layerHidden?: boolean;
  layerLocked?: boolean;
  onAdd: (drawing: ChartDrawing) => void;
  onUpdate: (drawingId: string, patch: ChartDrawingVertexPatch) => void;
  onSelect: (id: string | null) => void;
  onDrawingAdded?: (drawingId: string) => void;
  onDrawingDragEnd?: () => void;
  onOpenDrawingEditor?: (drawingId: string | null) => void;
  /** Doble clic en el fondo del gráfico (sin dibujo bajo el cursor). */
  onBackgroundDoubleClick?: (clientX: number, clientY: number) => void;
  /** true cuando la capa captura el puntero (dibujo bajo cursor o arrastre). */
  onInteractionCaptureChange?: (captures: boolean) => void;
}

type VertexKey = "p1" | "p2" | "p3";

function getVertexPoint(
  drawing: ChartDrawing,
  key: VertexKey,
): ChartDrawingPoint | undefined {
  if (key === "p3") {
    return drawing.type === "channel" || drawing.type === "pitchfork"
      ? drawing.p3
      : undefined;
  }
  if (!isPointLineDrawing(drawing)) {
    return undefined;
  }
  return drawing[key];
}

function markerPoint(drawing: ChartDrawing): ChartDrawingPoint | undefined {
  if (
    drawing.type === "cross-marker" ||
    drawing.type === "dot-marker" ||
    drawing.type === "dot-halo-marker" ||
    drawing.type === "arrow-marker" ||
    drawing.type === "arrow-circle-marker" ||
    drawing.type === "text-label" ||
    drawing.type === "hray"
  ) {
    return drawing.point;
  }
  return undefined;
}

function textOnChart(
  drawing: Extract<ChartDrawing, { type: "text-label" }>,
): string {
  return drawing.label?.trim() || drawing.text?.trim() || DEFAULT_TEXT_LABEL;
}

export function ChartDrawingsLayer({
  chart,
  series,
  container,
  height,
  bars = [],
  drawings,
  tool,
  selectedId,
  layerHidden = false,
  layerLocked = false,
  onAdd,
  onUpdate,
  onSelect,
  onDrawingAdded,
  onDrawingDragEnd,
  onOpenDrawingEditor,
  onBackgroundDoubleClick,
  onInteractionCaptureChange,
}: ChartDrawingsLayerProps) {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const stepRef = useRef(0);
  const [draftStart, setDraftStart] = useState<ChartDrawingPoint | null>(null);
  const [draftEnd, setDraftEnd] = useState<ChartDrawingPoint | null>(null);
  const [dragRect, setDragRect] = useState<{
    start: ChartDrawingPoint;
    end: ChartDrawingPoint;
  } | null>(null);
  const [hoverPoint, setHoverPoint] = useState<ChartDrawingPoint | null>(null);
  const dragVertexRef = useRef<{ id: string; key: VertexKey } | null>(null);
  const dragHlineRef = useRef<string | null>(null);
  const dragVlineRef = useRef<string | null>(null);
  const dragMarkerRef = useRef<string | null>(null);
  const dragHrayRef = useRef<string | null>(null);
  const dragWholeRef = useRef<{
    id: string;
    snapshot: ChartDrawing;
    anchor: ChartDrawingPoint;
  } | null>(null);
  const pendingDragRef = useRef<{
    mode:
      | { kind: "vertex"; id: string; key: VertexKey }
      | { kind: "marker"; id: string }
      | { kind: "hline"; id: string }
      | { kind: "vline"; id: string }
      | {
          kind: "whole";
          id: string;
          snapshot: ChartDrawing;
          anchor: ChartDrawingPoint;
        };
    startX: number;
    startY: number;
    pointerId: number;
    target: HTMLDivElement;
  } | null>(null);
  const arrowDraftRef = useRef<ChartDrawingPoint | null>(null);
  const arrowDraftToolRef = useRef<"arrow" | "arrow-circle">("arrow");
  const [arrowDraftEnd, setArrowDraftEnd] = useState<ChartDrawingPoint | null>(
    null,
  );
  const brushDraftRef = useRef<ChartDrawingPoint[] | null>(null);
  const [brushDraftPoints, setBrushDraftPoints] = useState<ChartDrawingPoint[]>(
    [],
  );
  const layerRef = useRef<HTMLDivElement>(null);
  const draggedRef = useRef(false);
  const dragTextSizeRef = useRef<{
    id: string;
    startY: number;
    startSize: number;
  } | null>(null);
  const [inlineTextEditId, setInlineTextEditId] = useState<string | null>(null);
  const [inlineTextDraft, setInlineTextDraft] = useState("");
  const [hoveringDrawing, setHoveringDrawing] = useState(false);
  const [interactionDragging, setInteractionDragging] = useState(false);

  const activeTemplateId = useWorkspaceStore(
    (s) => s.workspace.activeDrawingTemplateByTool?.[tool] ?? null,
  );
  const drawingTemplates = useWorkspaceStore(
    (s) => s.workspace.drawingTemplates,
  );

  const activeTemplatePatch = useMemo(() => {
    if (!activeTemplateId) return null;
    const pool = drawingTemplates?.length
      ? drawingTemplates
      : DEFAULT_DRAWING_TEMPLATES;
    const template = pool.find((item) => item.id === activeTemplateId);
    if (!template) return null;
    const drawingType = drawingTypeForTool(tool);
    if (drawingType && !templateMatchesDrawingType(template, drawingType))
      return null;
    return stylePatchFromTemplate(template);
  }, [activeTemplateId, drawingTemplates, tool]);

  const lastStyleMemory = useWorkspaceStore(
    (s) => s.workspace.chartToolbarGlobal?.lastDrawStyleByTool?.[tool],
  );
  const resolvedStyle = useMemo(
    () =>
      resolveDrawToolStyle(tool, {
        memory: lastStyleMemory,
        templatePatch: activeTemplatePatch,
      }),
    [activeTemplatePatch, lastStyleMemory, tool],
  );
  const rememberDrawStyleFromDrawing = useWorkspaceStore(
    (s) => s.rememberDrawStyleFromDrawing,
  );

  const newDrawingBase = (drawingType?: ChartDrawing["type"]) => {
    const semanticId = drawingType
      ? semanticIdForDrawingType(drawingType)
      : semanticIdForDrawTool(tool);
    return {
      id: newChartDrawingId(),
      ...resolvedStyle,
      ...(semanticId ? { semanticId } : {}),
    };
  };

  const toPx = useCallback(
    (point: ChartDrawingPoint): { x: number; y: number } | null => {
      if (!chart || !series) return null;
      const x = chart
        .timeScale()
        .timeToCoordinate(drawingPointToChartTime(point.time));
      const y = series.priceToCoordinate(point.price);
      if (x == null || y == null) return null;
      return { x, y };
    },
    [chart, series],
  );

  const pointerToPoint = useCallback(
    (clientX: number, clientY: number): ChartDrawingPoint | null => {
      if (!chart || !series) return null;
      const bounds =
        layerRef.current?.getBoundingClientRect() ??
        container?.getBoundingClientRect();
      if (!bounds) return null;
      const x = clientX - bounds.left;
      const y = clientY - bounds.top;
      const price = series.coordinateToPrice(y);
      const time = chart.timeScale().coordinateToTime(x);
      if (price == null || time == null) return null;
      return { time: horzTimeToString(time), price };
    },
    [chart, container, series],
  );

  const layerPointerPx = useCallback(
    (clientX: number, clientY: number): { px: number; py: number } | null => {
      const bounds =
        layerRef.current?.getBoundingClientRect() ??
        container?.getBoundingClientRect();
      if (!bounds) return null;
      return { px: clientX - bounds.left, py: clientY - bounds.top };
    },
    [container],
  );

  const hitTestDrawingsAt = useCallback(
    (px: number, py: number, hitThreshold = 10): string | null => {
      const containerW =
        layerRef.current?.clientWidth ?? container?.clientWidth ?? 2000;
      for (let i = drawings.length - 1; i >= 0; i -= 1) {
        const candidate = drawings[i]!;
        if (!isDrawingVisible(candidate)) continue;
        if (
          hitTestDrawing(
            candidate,
            px,
            py,
            toPx,
            hitThreshold,
            containerW,
            chart,
            series,
          )
        ) {
          return candidate.id;
        }
      }
      return null;
    },
    [chart, container, drawings, series, toPx],
  );

  useEffect(() => {
    if (!chart) return;
    const redraw = () => bump();
    chart.timeScale().subscribeVisibleLogicalRangeChange(redraw);
    chart.subscribeCrosshairMove(redraw);
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw);
      chart.unsubscribeCrosshairMove(redraw);
    };
  }, [chart]);

  useEffect(() => {
    stepRef.current = 0;
    setDraftStart(null);
    setDraftEnd(null);
    setDragRect(null);
    dragVertexRef.current = null;
    dragHlineRef.current = null;
    dragVlineRef.current = null;
    dragHrayRef.current = null;
    dragMarkerRef.current = null;
    dragHrayRef.current = null;
    dragWholeRef.current = null;
    pendingDragRef.current = null;
    arrowDraftRef.current = null;
    setArrowDraftEnd(null);
    setInteractionDragging(false);
  }, [tool]);

  useEffect(() => {
    if (!chart || !canInteractWithDrawings(tool) || drawings.length === 0)
      return;

    const handler = (param: { point?: { x: number; y: number } }) => {
      if (
        pendingDragRef.current ||
        dragVertexRef.current ||
        dragWholeRef.current
      )
        return;
      if (!param.point) {
        onSelect(null);
        return;
      }
      const { x, y } = param.point;
      const containerW = container?.clientWidth ?? 2000;
      for (let i = drawings.length - 1; i >= 0; i -= 1) {
        const drawing = drawings[i]!;
        if (!isDrawingVisible(drawing)) continue;
        if (
          hitTestDrawing(drawing, x, y, toPx, 10, containerW, chart, series)
        ) {
          onSelect(drawing.id);
          return;
        }
      }
      onSelect(null);
    };

    chart.subscribeClick(handler);
    return () => chart.unsubscribeClick(handler);
  }, [chart, container, drawings, onSelect, series, tool, toPx]);

  useEffect(() => {
    if ((tool !== "cross" && tool !== "select") || !container || layerHidden) {
      setHoveringDrawing(false);
      return;
    }

    const onMove = (event: MouseEvent) => {
      const coords = layerPointerPx(event.clientX, event.clientY);
      if (!coords) {
        setHoveringDrawing(false);
        return;
      }
      const hitId = hitTestDrawingsAt(coords.px, coords.py, 12);
      const vertexHit = findDrawingVertexHit(
        drawings,
        coords.px,
        coords.py,
        toPx,
        {
          threshold: 16,
          chart,
          series,
          containerWidth: container.clientWidth,
          priorityDrawingId: selectedId,
        },
      );
      setHoveringDrawing(Boolean(hitId || vertexHit));
    };

    const onLeave = () => setHoveringDrawing(false);

    container.addEventListener("mousemove", onMove);
    container.addEventListener("mouseleave", onLeave);
    return () => {
      container.removeEventListener("mousemove", onMove);
      container.removeEventListener("mouseleave", onLeave);
    };
  }, [
    chart,
    container,
    drawings,
    hitTestDrawingsAt,
    layerHidden,
    layerPointerPx,
    selectedId,
    series,
    toPx,
    tool,
  ]);

  const activatePendingDrag = () => {
    const pending = pendingDragRef.current;
    if (!pending) return;
    const { mode, pointerId, target } = pending;
    setInteractionDragging(true);
    if (mode.kind === "vertex") {
      dragVertexRef.current = { id: mode.id, key: mode.key };
    } else if (mode.kind === "marker") {
      dragMarkerRef.current = mode.id;
    } else if (mode.kind === "hline") {
      dragHlineRef.current = mode.id;
    } else if (mode.kind === "vline") {
      dragVlineRef.current = mode.id;
    } else {
      dragWholeRef.current = {
        id: mode.id,
        snapshot: mode.snapshot,
        anchor: mode.anchor,
      };
    }
    target.setPointerCapture(pointerId);
    pendingDragRef.current = null;
  };

  const placeDrawing = (drawing: ChartDrawing) => {
    onAdd(drawing);
    rememberDrawStyleFromDrawing(drawing, tool);
    onDrawingAdded?.(drawing.id);
  };

  const finishInteraction = () => {
    onDrawingDragEnd?.();
  };

  const finishTwoPoint = (
    toolType: ChartDrawTool,
    start: ChartDrawingPoint,
    end: ChartDrawingPoint,
  ) => {
    if (toolType === "regression") {
      const fitted = computeRegressionLine(bars, start, end);
      placeDrawing({
        ...newDrawingBase("regression"),
        type: "regression",
        p1: fitted?.p1 ?? start,
        p2: fitted?.p2 ?? end,
      });
    } else if (toolType === "info-line") {
      const base = newDrawingBase("info-line");
      placeDrawing({
        ...base,
        type: "info-line",
        p1: start,
        p2: end,
        label: defaultInfoLineLabel(start, end),
      });
    } else if (toolType === "ext-line") {
      placeDrawing({
        ...newDrawingBase("ext-line"),
        type: "ext-line",
        p1: start,
        p2: end,
      });
    } else if (toolType === "trend-angle") {
      placeDrawing({
        ...newDrawingBase("trend-angle"),
        type: "trend-angle",
        p1: start,
        p2: end,
      });
    } else if (
      toolType === "line" ||
      toolType === "ray" ||
      toolType === "fibonacci" ||
      toolType === "fib-trend-ext" ||
      toolType === "fib-time-zone" ||
      toolType === "gann-fan" ||
      toolType === "gann-grid"
    ) {
      placeDrawing({
        ...newDrawingBase(toolType),
        type: toolType,
        p1: start,
        p2: end,
      });
    } else if (toolType === "gann-square") {
      const p2 =
        chart && series ? snapGannSquareP2(start, end, chart, series) : end;
      placeDrawing({
        ...newDrawingBase("gann-square"),
        type: "gann-square",
        p1: start,
        p2,
      });
    }

    setDraftStart(null);
    setDraftEnd(null);
    setHoverPoint(null);
    stepRef.current = 0;
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (tool === "crosshair") return;
    if (!chart || !series || event.button !== 0) return;
    if (layerLocked && !canInteractWithDrawings(tool)) return;

    if (isShapeDrawTool(tool)) {
      event.preventDefault();
      event.stopPropagation();
    }

    if (canInteractWithDrawings(tool)) {
      const coords = layerPointerPx(event.clientX, event.clientY);
      if (!coords) return;
      const { px, py } = coords;
      const containerW =
        layerRef.current?.clientWidth ?? container?.clientWidth ?? 2000;

      draggedRef.current = false;

      const vertexHit = findDrawingVertexHit(drawings, px, py, toPx, {
        threshold: selectedId ? 20 : 16,
        chart,
        series,
        containerWidth: containerW,
        priorityDrawingId: selectedId,
      });

      if (vertexHit) {
        const target = drawings.find(
          (drawing) => drawing.id === vertexHit.drawingId,
        );
        onSelect(vertexHit.drawingId);
        if (target && !target.locked && !layerLocked) {
          event.preventDefault();
          event.stopPropagation();
          setInteractionDragging(true);
          event.currentTarget.setPointerCapture(event.pointerId);
          if (vertexHit.kind === "vertex") {
            dragVertexRef.current = {
              id: vertexHit.drawingId,
              key: vertexHit.key,
            };
          } else if (vertexHit.kind === "hline") {
            dragHlineRef.current = vertexHit.drawingId;
          } else {
            dragVlineRef.current = vertexHit.drawingId;
          }
        }
        return;
      }

      const hitId = hitTestDrawingsAt(px, py, 10);

      if (!hitId) {
        onSelect(null);
        onOpenDrawingEditor?.(null);
        setInlineTextEditId(null);
        return;
      }

      event.stopPropagation();
      onSelect(hitId);
      const selected = drawings.find((d) => d.id === hitId);
      if (!selected || selected.locked || layerLocked) {
        return;
      }

      const point = pointerToPoint(event.clientX, event.clientY);

      if (selected.type === "text-label") {
        const textPx = toPx(selected.point);
        const fontSize = selected.fontSize ?? DEFAULT_TEXT_FONT_SIZE;
        if (
          textPx &&
          py >= textPx.y + fontSize - 4 &&
          py <= textPx.y + fontSize + 14
        ) {
          setInteractionDragging(true);
          event.currentTarget.setPointerCapture(event.pointerId);
          dragTextSizeRef.current = {
            id: hitId,
            startY: py,
            startSize: fontSize,
          };
          return;
        }
      }

      if (
        selected.type === "cross-marker" ||
        selected.type === "dot-marker" ||
        selected.type === "dot-halo-marker" ||
        selected.type === "arrow-marker" ||
        selected.type === "arrow-circle-marker" ||
        selected.type === "text-label" ||
        selected.type === "hray"
      ) {
        setInteractionDragging(true);
        event.currentTarget.setPointerCapture(event.pointerId);
        dragMarkerRef.current = hitId;
        return;
      }

      if (!point) return;

      setInteractionDragging(true);
      event.currentTarget.setPointerCapture(event.pointerId);
      pendingDragRef.current = {
        mode: { kind: "whole", id: hitId, snapshot: selected, anchor: point },
        startX: px,
        startY: py,
        pointerId: event.pointerId,
        target: event.currentTarget,
      };
      return;
    }

    const point = pointerToPoint(event.clientX, event.clientY);
    if (!point) return;

    if (tool === "text") {
      const base = newDrawingBase("text-label");
      const content = DEFAULT_TEXT_LABEL;
      const drawing = {
        ...base,
        type: "text-label" as const,
        point,
        label: content,
        text: content,
        fontSize:
          base.fontSize ?? resolvedStyle.fontSize ?? DEFAULT_TEXT_FONT_SIZE,
      };
      placeDrawing(drawing);
      onSelect(drawing.id);
      setInlineTextEditId(drawing.id);
      setInlineTextDraft(content);
      return;
    }

    if (tool === "arrow-up") {
      placeDrawing({
        ...newDrawingBase("arrow-marker"),
        type: "arrow-marker",
        point,
        direction: "up",
      });
      return;
    }

    if (tool === "arrow-down") {
      placeDrawing({
        ...newDrawingBase("arrow-marker"),
        type: "arrow-marker",
        point,
        direction: "down",
      });
      return;
    }

    if (tool === "brush" || tool === "highlighter") {
      brushDraftRef.current = [point];
      setBrushDraftPoints([point]);
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }

    if (tool === "arrow-circle") {
      arrowDraftToolRef.current = tool;
      arrowDraftRef.current = point;
      setArrowDraftEnd(point);
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }

    if (tool === "hray") {
      placeDrawing({ ...newDrawingBase("hray"), type: "hray", point });
      return;
    }

    if (tool === "rectangle") {
      setDragRect({ start: point, end: point });
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }

    if (tool === "vline") {
      placeDrawing({
        ...newDrawingBase("vline"),
        type: "vline",
        time: point.time,
      });
      return;
    }

    if (tool === "hline") {
      placeDrawing({
        ...newDrawingBase("hline"),
        type: "hline",
        price: point.price,
      });
      return;
    }

    if (TWO_POINT_DRAW_TOOLS.includes(tool)) {
      if (!draftStart) {
        setDraftStart(point);
        setDraftEnd(point);
        stepRef.current = 1;
      } else {
        finishTwoPoint(tool, draftStart, point);
      }
      return;
    }

    if (tool === "channel") {
      if (stepRef.current === 0) {
        setDraftStart(point);
        setDraftEnd(point);
        stepRef.current = 1;
      } else if (stepRef.current === 1 && draftStart) {
        setDraftEnd(point);
        stepRef.current = 2;
      } else if (stepRef.current === 2 && draftStart && draftEnd) {
        placeDrawing({
          ...newDrawingBase("channel"),
          type: "channel",
          p1: draftStart,
          p2: draftEnd,
          p3: point,
          fillOpacity:
            resolvedStyle.fillOpacity ?? DEFAULT_CHANNEL_FILL_OPACITY,
        });
        stepRef.current = 0;
        setDraftStart(null);
        setDraftEnd(null);
      }
      return;
    }

    if (tool === "pitchfork") {
      if (stepRef.current === 0) {
        setDraftStart(point);
        setDraftEnd(point);
        stepRef.current = 1;
      } else if (stepRef.current === 1 && draftStart) {
        setDraftEnd(point);
        stepRef.current = 2;
      } else if (stepRef.current === 2 && draftStart && draftEnd) {
        placeDrawing({
          ...newDrawingBase("pitchfork"),
          type: "pitchfork",
          p1: draftStart,
          p2: draftEnd,
          p3: point,
        });
        stepRef.current = 0;
        setDraftStart(null);
        setDraftEnd(null);
      }
      return;
    }
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const point = pointerToPoint(event.clientX, event.clientY);
    const moveCoords = layerPointerPx(event.clientX, event.clientY);
    const moveX = moveCoords?.px ?? event.nativeEvent.offsetX;
    const moveY = moveCoords?.py ?? event.nativeEvent.offsetY;

    if (pendingDragRef.current?.mode.kind === "whole") {
      const pending = pendingDragRef.current;
      if (Math.hypot(moveX - pending.startX, moveY - pending.startY) >= 6) {
        activatePendingDrag();
        draggedRef.current = true;
      }
    }

    if (dragTextSizeRef.current) {
      const { id, startY, startSize } = dragTextSizeRef.current;
      const delta = moveY - startY;
      const nextSize = Math.max(
        8,
        Math.min(72, Math.round(startSize + delta * 0.35)),
      );
      onUpdate(id, { fontSize: nextSize, templateId: undefined });
      draggedRef.current = true;
      return;
    }

    if (
      dragVertexRef.current ||
      dragWholeRef.current ||
      dragMarkerRef.current ||
      dragHlineRef.current ||
      dragVlineRef.current ||
      dragHrayRef.current
    ) {
      draggedRef.current = true;
    }

    if (dragWholeRef.current && point && chart && series) {
      const { id, snapshot, anchor } = dragWholeRef.current;
      const patch = wholeDrawingPatch(
        snapshot,
        anchor,
        point,
        chart,
        series,
        toPx,
      );
      if (Object.keys(patch).length > 0) {
        onUpdate(id, patch);
      }
      return;
    }

    if (dragMarkerRef.current && point) {
      onUpdate(dragMarkerRef.current, { point });
      return;
    }

    if (dragHrayRef.current && point) {
      onUpdate(dragHrayRef.current, { point });
      return;
    }

    if (dragVlineRef.current && point) {
      onUpdate(dragVlineRef.current, { time: point.time });
      return;
    }

    if (dragHlineRef.current && point) {
      onUpdate(dragHlineRef.current, { price: point.price });
      return;
    }

    if (dragVertexRef.current && point) {
      event.preventDefault();
      const { id, key } = dragVertexRef.current;
      onUpdate(id, { [key]: point });
      return;
    }

    if (arrowDraftRef.current && point) {
      setArrowDraftEnd(point);
      return;
    }

    if (brushDraftRef.current && point) {
      const last = brushDraftRef.current[brushDraftRef.current.length - 1]!;
      const lastPx = toPx(last);
      const curPx = toPx(point);
      if (
        lastPx &&
        curPx &&
        Math.hypot(curPx.x - lastPx.x, curPx.y - lastPx.y) >= 3
      ) {
        const next = [...brushDraftRef.current, point];
        brushDraftRef.current = next;
        setBrushDraftPoints(next);
      }
      return;
    }

    if (tool === "rectangle" && dragRect && point) {
      setDragRect({ start: dragRect.start, end: point });
      return;
    }

    if (point) setHoverPoint(point);
    if (
      draftStart &&
      (TWO_POINT_DRAW_TOOLS.includes(tool) ||
        THREE_POINT_DRAW_TOOLS.includes(tool))
    ) {
      setDraftEnd(point);
    }
  };

  const finishArrow = (start: ChartDrawingPoint, end: ChartDrawingPoint) => {
    const a = toPx(start);
    const b = toPx(end);
    let direction: ChartMarkerDirection = "up";
    if (a && b) {
      direction = markerDirectionFromDelta(b.x - a.x, b.y - a.y);
    }
    const markerType =
      arrowDraftToolRef.current === "arrow-circle"
        ? "arrow-circle-marker"
        : "arrow-marker";
    const base = {
      ...newDrawingBase(markerType),
      point: start,
      direction,
    };
    if (arrowDraftToolRef.current === "arrow-circle") {
      placeDrawing({ ...base, type: "arrow-circle-marker" });
    } else {
      placeDrawing({ ...base, type: "arrow-marker" });
    }
    arrowDraftRef.current = null;
    setArrowDraftEnd(null);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (pendingDragRef.current) {
      pendingDragRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }

    if (dragTextSizeRef.current) {
      const drawing = drawings.find(
        (d) => d.id === dragTextSizeRef.current?.id,
      );
      if (drawing) rememberDrawStyleFromDrawing(drawing);
      dragTextSizeRef.current = null;
      setInteractionDragging(false);
      finishInteraction();
      event.currentTarget.releasePointerCapture(event.pointerId);
      draggedRef.current = false;
      return;
    }

    if ((tool === "brush" || tool === "highlighter") && brushDraftRef.current) {
      const points = brushDraftRef.current;
      if (points.length >= 2) {
        placeDrawing({
          ...newDrawingBase("brush-stroke"),
          type: "brush-stroke",
          points,
        });
      }
      brushDraftRef.current = null;
      setBrushDraftPoints([]);
      event.currentTarget.releasePointerCapture(event.pointerId);
      return;
    }

    if (arrowDraftRef.current && tool === "arrow-circle") {
      const point = pointerToPoint(event.clientX, event.clientY);
      if (point) {
        finishArrow(arrowDraftRef.current, point);
      }
      event.currentTarget.releasePointerCapture(event.pointerId);
      return;
    }

    let dragged = false;
    if (dragWholeRef.current) {
      dragWholeRef.current = null;
      dragged = true;
    }
    if (dragMarkerRef.current) {
      dragMarkerRef.current = null;
      dragged = true;
    }
    if (dragHrayRef.current) {
      dragHrayRef.current = null;
      dragged = true;
    }
    if (dragVlineRef.current) {
      dragVlineRef.current = null;
      dragged = true;
    }
    if (dragHlineRef.current) {
      dragHlineRef.current = null;
      dragged = true;
    }
    if (dragVertexRef.current) {
      const drawing = drawings.find((d) => d.id === dragVertexRef.current?.id);
      if (drawing) rememberDrawStyleFromDrawing(drawing);
      dragVertexRef.current = null;
      dragged = true;
    }
    if (dragged) {
      setInteractionDragging(false);
      finishInteraction();
      event.currentTarget.releasePointerCapture(event.pointerId);
      draggedRef.current = false;
      return;
    }

    draggedRef.current = false;

    if (tool !== "rectangle" || !dragRect) return;
    const { p1, p2 } = normalizeRect(dragRect.start, dragRect.end);
    if (p1.time !== p2.time || p1.price !== p2.price) {
      placeDrawing({
        ...newDrawingBase("rectangle"),
        type: "rectangle",
        p1,
        p2,
        fillOpacity: resolvedStyle.fillOpacity ?? DEFAULT_RECT_FILL_OPACITY,
      });
    }
    setDragRect(null);
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const renderLine = (
    p1: ChartDrawingPoint,
    p2: ChartDrawingPoint,
    color: string,
    lineWidth = DEFAULT_LINE_WIDTH,
    options: {
      dashed?: boolean;
      extendRay?: boolean;
      extendBoth?: boolean;
      lineStyle?: import("@bolsa/shared").ChartLineStyle;
    } = {},
  ) => {
    const w = container?.clientWidth ?? 2000;
    let seg: { x1: number; y1: number; x2: number; y2: number } | null;
    if (options.extendBoth) {
      seg = extendedLinePixels(p1, p2, toPx, w);
    } else if (options.extendRay) {
      seg = rayLinePixels(p1, p2, toPx);
    } else {
      const a = toPx(p1);
      const b = toPx(p2);
      seg = a && b ? { x1: a.x, y1: a.y, x2: b.x, y2: b.y } : null;
    }
    if (!seg) return null;
    const dash = options.dashed
      ? "4 4"
      : strokeDasharray(options.lineStyle ?? "solid");
    return (
      <line
        key={`${p1.time}-${p2.time}-${options.extendRay ? "r" : options.extendBoth ? "e" : "s"}`}
        x1={seg.x1}
        y1={seg.y1}
        x2={seg.x2}
        y2={seg.y2}
        stroke={color}
        strokeWidth={lineWidth}
        strokeDasharray={dash}
      />
    );
  };

  const renderVLine = (
    drawing: Extract<ChartDrawing, { type: "vline" }>,
    selected: boolean,
  ) => {
    if (!chart) return null;
    const x = timeToPixelX(chart, drawing.time);
    if (x == null) return null;
    const h = container?.clientHeight ?? height;
    const width = drawingLineWidth(drawing);
    return (
      <line
        key={drawing.id}
        x1={x}
        y1={0}
        x2={x}
        y2={h}
        stroke={drawing.color}
        strokeWidth={selected ? width + 0.5 : width}
        strokeDasharray={strokeDasharray(drawingLineStyle(drawing))}
      />
    );
  };

  const renderHLine = (
    drawing: Extract<ChartDrawing, { type: "hline" }>,
    selected: boolean,
  ) => {
    if (!series) return null;
    const y = priceToPixelY(series, drawing.price);
    if (y == null) return null;
    const w = container?.clientWidth ?? 2000;
    const width = drawingLineWidth(drawing);
    return (
      <line
        key={drawing.id}
        x1={0}
        y1={y}
        x2={w}
        y2={y}
        stroke={drawing.color}
        strokeWidth={selected ? width + 0.5 : width}
        strokeDasharray={strokeDasharray(drawingLineStyle(drawing))}
      />
    );
  };

  const renderHRay = (
    drawing: Extract<ChartDrawing, { type: "hray" }>,
    selected: boolean,
  ) => {
    const anchor = toPx(drawing.point);
    if (!anchor) return null;
    const w = container?.clientWidth ?? 2000;
    const width = drawingLineWidth(drawing);
    return (
      <g key={drawing.id}>
        <line
          x1={anchor.x}
          y1={anchor.y}
          x2={w}
          y2={anchor.y}
          stroke={drawing.color}
          strokeWidth={selected ? width + 0.5 : width}
          strokeDasharray={strokeDasharray(drawingLineStyle(drawing))}
        />
        <circle cx={anchor.x} cy={anchor.y} r={3} fill={drawing.color} />
      </g>
    );
  };

  const renderFibonacci = (
    drawing: Extract<ChartDrawing, { type: "fibonacci" }>,
    selected: boolean,
  ) => {
    const { t1, t2 } = fibTimeSpan(drawing.p1, drawing.p2);
    const left = toPx({ time: t1, price: drawing.p1.price });
    const right = toPx({ time: t2, price: drawing.p2.price });
    if (!left || !right) return null;
    const x1 = Math.min(left.x, right.x);
    const x2 = Math.max(left.x, right.x);

    return (
      <g key={drawing.id}>
        {FIBONACCI_LEVELS.map((level) => {
          const price = fibPriceAtLevel(drawing.p1, drawing.p2, level);
          const y = toPx({ time: t1, price })?.y;
          if (y == null) return null;
          const pct = `${(level * 100).toFixed(1)}%`;
          return (
            <g key={level}>
              <line
                x1={x1}
                y1={y}
                x2={x2}
                y2={y}
                stroke={drawing.color}
                strokeWidth={selected ? 2 : 1.5}
                opacity={0.9}
              />
              <text x={x2 + 4} y={y + 4} fill={drawing.color} fontSize={10}>
                {pct}
              </text>
            </g>
          );
        })}
      </g>
    );
  };

  const renderFibTrendExt = (
    drawing: Extract<ChartDrawing, { type: "fib-trend-ext" }>,
    selected: boolean,
  ) => {
    const { t1, t2 } = fibTimeSpan(drawing.p1, drawing.p2);
    const left = toPx({ time: t1, price: drawing.p1.price });
    const right = toPx({ time: t2, price: drawing.p2.price });
    if (!left || !right) return null;
    const x1 = Math.min(left.x, right.x);
    const x2 = Math.max(left.x, right.x);

    return (
      <g key={drawing.id}>
        {FIBONACCI_TREND_EXT_LEVELS.map((level) => {
          const price = fibPriceAtLevel(drawing.p1, drawing.p2, level);
          const y = toPx({ time: t1, price })?.y;
          if (y == null) return null;
          const pct = `${(level * 100).toFixed(1)}%`;
          const isExt = level > 1;
          return (
            <g key={level}>
              <line
                x1={x1}
                y1={y}
                x2={x2}
                y2={y}
                stroke={drawing.color}
                strokeWidth={selected ? 2 : 1.5}
                opacity={isExt ? 1 : 0.75}
                strokeDasharray={isExt ? "4 3" : undefined}
              />
              <text x={x2 + 4} y={y + 4} fill={drawing.color} fontSize={10}>
                {pct}
              </text>
            </g>
          );
        })}
      </g>
    );
  };

  const renderFibTimeZone = (
    drawing: Extract<ChartDrawing, { type: "fib-time-zone" }>,
    selected: boolean,
  ) => {
    const xs = fibTimeZoneLineXs(drawing.p1, drawing.p2, toPx);
    if (!xs.length) return null;
    const a = toPx(drawing.p1);
    const b = toPx(drawing.p2);
    if (!a || !b) return null;
    const y1 = Math.min(a.y, b.y);
    const y2 = Math.max(a.y, b.y);
    const pad = 120;
    const top = y1 - pad;
    const bottom = y2 + pad;
    const width = selected ? 2 : 1.5;

    return (
      <g key={drawing.id} stroke={drawing.color} strokeWidth={width}>
        {xs.map((x, index) => (
          <line
            key={index}
            x1={x}
            y1={top}
            x2={x}
            y2={bottom}
            opacity={index <= 1 ? 0.9 : 0.7}
          />
        ))}
      </g>
    );
  };

  const renderGannFan = (
    drawing: Extract<ChartDrawing, { type: "gann-fan" }>,
    selected: boolean,
  ) => {
    const color = drawing.color;
    const width = selected ? 2 : drawingLineWidth(drawing);
    const rays = gannFanRays(drawing, toPx);
    if (!rays.length) return null;
    return (
      <g key={drawing.id} stroke={color} strokeWidth={width}>
        {rays.map((seg, index) => (
          <line
            key={index}
            x1={seg.x1}
            y1={seg.y1}
            x2={seg.x2}
            y2={seg.y2}
            opacity={index === 4 ? 1 : 0.75}
          />
        ))}
      </g>
    );
  };

  const renderGannGrid = (
    drawing: Extract<ChartDrawing, { type: "gann-grid" }>,
    selected: boolean,
  ) => {
    const bounds = gannGridPixelBounds(drawing, toPx);
    if (!bounds) return null;
    const { left, top, right, bottom } = bounds;
    const color = drawing.color;
    const width = selected ? 2 : drawingLineWidth(drawing);
    const fillOpacity = drawing.fillOpacity ?? 0.08;
    const w = right - left;
    const h = bottom - top;

    return (
      <g key={drawing.id}>
        {fillOpacity > 0 && (
          <rect
            x={left}
            y={top}
            width={w}
            height={h}
            fill={color}
            fillOpacity={fillOpacity}
            stroke="none"
          />
        )}
        <rect
          x={left}
          y={top}
          width={w}
          height={h}
          stroke={color}
          strokeWidth={width}
          fill="none"
        />
        {Array.from({ length: GANN_GRID_DIVISIONS - 1 }, (_, i) => {
          const t = (i + 1) / GANN_GRID_DIVISIONS;
          const x = left + w * t;
          const y = top + h * t;
          return (
            <g key={i} stroke={color} strokeWidth={1} opacity={0.65}>
              <line x1={x} y1={top} x2={x} y2={bottom} />
              <line x1={left} y1={y} x2={right} y2={y} />
            </g>
          );
        })}
      </g>
    );
  };

  const renderGannSquare = (
    drawing: Extract<ChartDrawing, { type: "gann-square" }>,
    selected: boolean,
  ) => {
    if (!chart || !series) return null;
    const bounds = gannSquarePixelBounds(drawing, chart, series);
    if (!bounds) return null;
    const color = drawing.color;
    const width = selected ? 2 : drawingLineWidth(drawing);
    const fillOpacity = drawing.fillOpacity ?? 0.08;

    return (
      <g key={drawing.id}>
        {fillOpacity > 0 && (
          <rect
            x={bounds.x}
            y={bounds.y}
            width={bounds.w}
            height={bounds.h}
            fill={color}
            fillOpacity={fillOpacity}
            stroke="none"
          />
        )}
        <rect
          x={bounds.x}
          y={bounds.y}
          width={bounds.w}
          height={bounds.h}
          stroke={color}
          strokeWidth={width}
          fill="none"
        />
        <line
          x1={bounds.x}
          y1={bounds.y}
          x2={bounds.x + bounds.w}
          y2={bounds.y + bounds.h}
          stroke={color}
          strokeWidth={1}
          opacity={0.5}
        />
      </g>
    );
  };

  const renderChannel = (
    drawing: Extract<ChartDrawing, { type: "channel" }>,
    selected: boolean,
  ) => {
    const p4 = channelParallelEnd(drawing.p1, drawing.p2, drawing.p3);
    const color = drawing.color;
    const width = selected ? 2 : drawingLineWidth(drawing);
    const a = toPx(drawing.p1);
    const b = toPx(drawing.p2);
    const c = toPx(drawing.p3);
    const d = toPx(p4);
    if (!a || !b || !c || !d) return null;
    const fillOpacity = drawing.fillOpacity ?? DEFAULT_CHANNEL_FILL_OPACITY;
    return (
      <g key={drawing.id}>
        {fillOpacity > 0 && (
          <polygon
            points={`${a.x},${a.y} ${b.x},${b.y} ${d.x},${d.y} ${c.x},${c.y}`}
            fill={color}
            fillOpacity={fillOpacity}
            stroke="none"
          />
        )}
        <line
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          stroke={color}
          strokeWidth={width}
        />
        <line
          x1={c.x}
          y1={c.y}
          x2={d.x}
          y2={d.y}
          stroke={color}
          strokeWidth={width}
        />
      </g>
    );
  };

  const renderPitchfork = (
    drawing: Extract<ChartDrawing, { type: "pitchfork" }>,
    selected: boolean,
  ) => {
    if (!chart || !series) return null;
    const color = drawing.color;
    const width = selected ? 2 : drawingLineWidth(drawing);
    const rays = pitchforkRays(drawing, chart, series, toPx);
    if (!rays.length) return null;
    return (
      <g key={drawing.id} stroke={color} strokeWidth={width}>
        {rays.map((seg, index) => (
          <line key={index} x1={seg.x1} y1={seg.y1} x2={seg.x2} y2={seg.y2} />
        ))}
      </g>
    );
  };

  const renderTextLabel = (
    drawing: Extract<ChartDrawing, { type: "text-label" }>,
    selected: boolean,
  ) => {
    if (inlineTextEditId === drawing.id) return null;
    const px = toPx(drawing.point);
    if (!px) return null;
    const fontSize = drawing.fontSize ?? DEFAULT_TEXT_FONT_SIZE;
    const content = textOnChart(drawing);
    if (!content) return null;
    return (
      <text
        key={drawing.id}
        x={px.x}
        y={px.y}
        fill={drawing.color}
        fontSize={fontSize}
        fontFamily="system-ui, sans-serif"
        dominantBaseline="hanging"
        textAnchor="start"
        paintOrder="stroke fill"
        stroke={selected ? "#facc15" : "hsl(var(--background))"}
        strokeWidth={selected ? 1.25 : 3}
      >
        {content}
      </text>
    );
  };

  const renderBrushStroke = (
    drawing: Extract<ChartDrawing, { type: "brush-stroke" }>,
    selected: boolean,
  ) => {
    const width = selected
      ? (drawing.lineWidth ?? DEFAULT_LINE_WIDTH) + 0.5
      : (drawing.lineWidth ?? DEFAULT_LINE_WIDTH);
    const opacity = drawing.strokeOpacity ?? DEFAULT_BRUSH_STROKE_OPACITY;
    const path = drawing.points
      .map((point, index) => {
        const px = toPx(point);
        if (!px) return null;
        return `${index === 0 ? "M" : "L"} ${px.x} ${px.y}`;
      })
      .filter((segment): segment is string => segment != null)
      .join(" ");
    if (!path) return null;
    return (
      <path
        key={drawing.id}
        d={path}
        fill="none"
        stroke={drawing.color}
        strokeWidth={width}
        strokeOpacity={opacity}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    );
  };

  const renderCrossMarker = (
    drawing: Extract<ChartDrawing, { type: "cross-marker" }>,
    selected: boolean,
  ) => {
    const px = toPx(drawing.point);
    if (!px) return null;
    const size = selected ? 9 : 7;
    const width = drawingLineWidth(drawing);
    return (
      <g key={drawing.id} stroke={drawing.color} strokeWidth={width}>
        <line x1={px.x - size} y1={px.y} x2={px.x + size} y2={px.y} />
        <line x1={px.x} y1={px.y - size} x2={px.x} y2={px.y + size} />
      </g>
    );
  };

  const renderDotMarker = (
    drawing: Extract<ChartDrawing, { type: "dot-marker" }>,
    selected: boolean,
  ) => {
    const px = toPx(drawing.point);
    if (!px) return null;
    return (
      <circle
        key={drawing.id}
        cx={px.x}
        cy={px.y}
        r={selected ? 5 : 4}
        fill={drawing.color}
        stroke={selected ? "#facc15" : drawing.color}
        strokeWidth={selected ? 1.5 : 0}
      />
    );
  };

  const renderArrowMarker = (
    drawing: Extract<ChartDrawing, { type: "arrow-marker" }>,
    selected: boolean,
  ) => {
    const px = toPx(drawing.point);
    if (!px) return null;
    const rotation = markerRotation(drawing.direction);
    return (
      <g
        key={drawing.id}
        transform={`translate(${px.x}, ${px.y}) rotate(${rotation})`}
        fill={drawing.color}
      >
        <path
          d="M0,-10 L-6,4 L0,0 L6,4 Z"
          stroke={selected ? "#facc15" : "none"}
          strokeWidth={1}
        />
      </g>
    );
  };

  const renderArrowCircleMarker = (
    drawing: Extract<ChartDrawing, { type: "arrow-circle-marker" }>,
    selected: boolean,
  ) => {
    const px = toPx(drawing.point);
    if (!px) return null;
    const rotation = markerRotation(drawing.direction);
    return (
      <g key={drawing.id} transform={`translate(${px.x}, ${px.y})`}>
        <circle
          r={11}
          fill="none"
          stroke={drawing.color}
          strokeWidth={selected ? 2 : 1.5}
        />
        <g transform={`rotate(${rotation})`} fill={drawing.color}>
          <path
            d="M0,-7 L-4,3 L0,0 L4,3 Z"
            stroke={selected ? "#facc15" : "none"}
            strokeWidth={1}
          />
        </g>
      </g>
    );
  };

  const renderDotHaloMarker = (
    drawing: Extract<ChartDrawing, { type: "dot-halo-marker" }>,
    selected: boolean,
  ) => {
    const px = toPx(drawing.point);
    if (!px) return null;
    const haloR = drawing.haloRadius ?? DEFAULT_DOT_HALO_RADIUS;
    const dotR = selected ? 5 : 4;
    return (
      <g key={drawing.id}>
        <circle
          cx={px.x}
          cy={px.y}
          r={haloR}
          fill={drawing.color}
          fillOpacity={0.22}
          stroke={drawing.color}
          strokeOpacity={0.45}
          strokeWidth={selected ? 2 : 1}
        />
        <circle
          cx={px.x}
          cy={px.y}
          r={dotR}
          fill={drawing.color}
          stroke={selected ? "#facc15" : drawing.color}
          strokeWidth={selected ? 1.5 : 0}
        />
      </g>
    );
  };

  const renderLineLabel = (
    p1: ChartDrawingPoint,
    p2: ChartDrawingPoint,
    label: string | undefined,
    color: string,
  ) => {
    const trimmed = label?.trim();
    if (!trimmed) return null;
    const mid = {
      time: p1.time,
      price: (p1.price + p2.price) / 2,
    };
    const labelPx = toPx(mid);
    if (!labelPx) return null;
    return (
      <text
        x={labelPx.x + 6}
        y={labelPx.y - 4}
        fill={color}
        fontSize={10}
        paintOrder="stroke fill"
        stroke="hsl(var(--background))"
        strokeWidth={3}
      >
        {trimmed}
      </text>
    );
  };

  const commitInlineTextEdit = () => {
    if (!inlineTextEditId) return;
    const value = inlineTextDraft.trim() || DEFAULT_TEXT_LABEL;
    onUpdate(inlineTextEditId, {
      label: value,
      text: value,
      templateId: undefined,
    });
    const drawing = drawings.find((d) => d.id === inlineTextEditId);
    if (drawing)
      rememberDrawStyleFromDrawing({ ...drawing, label: value, text: value });
    setInlineTextEditId(null);
    setInlineTextDraft("");
  };

  const renderDrawing = (drawing: ChartDrawing) => {
    if (!isDrawingVisible(drawing)) return null;
    const selected = drawing.id === selectedId;
    const width = drawingLineWidth(drawing);
    const style = drawingLineStyle(drawing);
    if (drawing.type === "cross-marker")
      return renderCrossMarker(drawing, selected);
    if (drawing.type === "dot-marker")
      return renderDotMarker(drawing, selected);
    if (drawing.type === "dot-halo-marker")
      return renderDotHaloMarker(drawing, selected);
    if (drawing.type === "arrow-marker")
      return renderArrowMarker(drawing, selected);
    if (drawing.type === "arrow-circle-marker")
      return renderArrowCircleMarker(drawing, selected);
    if (drawing.type === "hline") return renderHLine(drawing, selected);
    if (drawing.type === "hray") return renderHRay(drawing, selected);
    if (drawing.type === "vline") return renderVLine(drawing, selected);
    if (drawing.type === "line") {
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            lineStyle: style,
          })}
          {renderLineLabel(
            drawing.p1,
            drawing.p2,
            drawing.label ?? drawing.text,
            drawing.color,
          )}
        </g>
      );
    }
    if (drawing.type === "ext-line") {
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            extendBoth: true,
            lineStyle: style,
          })}
          {renderLineLabel(
            drawing.p1,
            drawing.p2,
            drawing.label ?? drawing.text,
            drawing.color,
          )}
        </g>
      );
    }
    if (drawing.type === "info-line") {
      const mid = {
        time: drawing.p1.time,
        price: (drawing.p1.price + drawing.p2.price) / 2,
      };
      const labelPx = toPx(mid);
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            lineStyle: style,
          })}
          {labelPx && (
            <text
              x={labelPx.x + 6}
              y={labelPx.y - 4}
              fill={drawing.color}
              fontSize={10}
            >
              {drawing.label}
            </text>
          )}
        </g>
      );
    }
    if (drawing.type === "trend-angle") {
      const angle = lineAngleDegrees(drawing.p1, drawing.p2);
      const labelPx = toPx(drawing.p1);
      const chartLabel = drawing.label?.trim() || drawing.text?.trim();
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            lineStyle: style,
          })}
          {labelPx && (
            <text
              x={labelPx.x + 6}
              y={labelPx.y - 6}
              fill={drawing.color}
              fontSize={10}
            >
              {chartLabel || `${angle.toFixed(1)}°`}
            </text>
          )}
        </g>
      );
    }
    if (drawing.type === "regression") {
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            lineStyle: style === "solid" ? "dashed" : style,
          })}
          {renderLineLabel(
            drawing.p1,
            drawing.p2,
            drawing.label ?? drawing.text,
            drawing.color,
          )}
        </g>
      );
    }
    if (drawing.type === "ray") {
      return (
        <g key={drawing.id}>
          {renderLine(drawing.p1, drawing.p2, drawing.color, width, {
            extendRay: true,
            lineStyle: style,
          })}
          {renderLineLabel(
            drawing.p1,
            drawing.p2,
            drawing.label ?? drawing.text,
            drawing.color,
          )}
        </g>
      );
    }
    if (drawing.type === "rectangle") {
      const a = toPx(drawing.p1);
      const b = toPx(drawing.p2);
      if (!a || !b) return null;
      const x = Math.min(a.x, b.x);
      const y = Math.min(a.y, b.y);
      const w = Math.abs(b.x - a.x);
      const h = Math.abs(b.y - a.y);
      return (
        <rect
          key={drawing.id}
          x={x}
          y={y}
          width={w}
          height={h}
          stroke={drawing.color}
          strokeWidth={selected ? 2 : 1.5}
          fill={drawing.color}
          fillOpacity={drawing.fillOpacity}
        />
      );
    }
    if (drawing.type === "fibonacci") return renderFibonacci(drawing, selected);
    if (drawing.type === "fib-trend-ext")
      return renderFibTrendExt(drawing, selected);
    if (drawing.type === "fib-time-zone")
      return renderFibTimeZone(drawing, selected);
    if (drawing.type === "gann-fan") return renderGannFan(drawing, selected);
    if (drawing.type === "gann-grid") return renderGannGrid(drawing, selected);
    if (drawing.type === "gann-square")
      return renderGannSquare(drawing, selected);
    if (drawing.type === "channel") return renderChannel(drawing, selected);
    if (drawing.type === "pitchfork") return renderPitchfork(drawing, selected);
    if (drawing.type === "text-label")
      return renderTextLabel(drawing, selected);
    if (drawing.type === "brush-stroke")
      return renderBrushStroke(drawing, selected);
    return null;
  };

  const renderVertexHandle = (cx: number, cy: number, key: string) => (
    <g key={key}>
      <circle
        cx={cx}
        cy={cy}
        r={8}
        fill="hsl(var(--background))"
        fillOpacity={0.85}
        stroke="none"
      />
      <circle
        cx={cx}
        cy={cy}
        r={5.5}
        fill="#f8fafc"
        stroke="#14b8a6"
        strokeWidth={2}
      />
    </g>
  );

  const renderVertices = (drawing: ChartDrawing) => {
    if (drawing.id !== selectedId) return null;

    if (drawing.type === "hline" && series) {
      const y = priceToPixelY(series, drawing.price);
      const containerW =
        container?.clientWidth ?? layerRef.current?.clientWidth ?? 2000;
      if (y == null) return null;
      return renderVertexHandle(containerW / 2, y, "hline-handle");
    }

    if (drawing.type === "vline" && chart) {
      const x = timeToPixelX(chart, drawing.time);
      if (x == null) return null;
      return renderVertexHandle(x, height / 2, "vline-handle");
    }

    if (drawing.type === "text-label") {
      const px = toPx(drawing.point);
      if (!px) return null;
      const fontSize = drawing.fontSize ?? DEFAULT_TEXT_FONT_SIZE;
      return (
        <>
          {renderVertexHandle(px.x, px.y, "text-anchor")}
          {renderVertexHandle(px.x + 48, px.y + fontSize, "text-size")}
        </>
      );
    }

    const marker = markerPoint(drawing);
    if (marker) {
      const px = toPx(marker);
      if (!px) return null;
      return renderVertexHandle(px.x, px.y, "marker-handle");
    }

    return drawingVertices(drawing).map((key) => {
      const point = getVertexPoint(drawing, key);
      if (!point) return null;
      const px = toPx(point);
      if (!px) return null;
      return renderVertexHandle(px.x, px.y, key);
    });
  };

  const renderDraft = () => {
    const draftColor = resolvedStyle.color ?? DEFAULT_CHART_DRAW_COLOR;
    const draftLineWidth = resolvedStyle.lineWidth ?? DEFAULT_LINE_WIDTH;
    const draftFillOpacity =
      resolvedStyle.fillOpacity ?? DEFAULT_RECT_FILL_OPACITY;
    const draftStrokeOpacity =
      resolvedStyle.strokeOpacity ?? DEFAULT_BRUSH_STROKE_OPACITY;

    if (tool === "arrow-circle" && arrowDraftRef.current && arrowDraftEnd) {
      const a = toPx(arrowDraftRef.current);
      const b = toPx(arrowDraftEnd);
      if (!a || !b) return null;
      const direction = markerDirectionFromDelta(b.x - a.x, b.y - a.y);
      return (
        <g
          transform={`translate(${a.x}, ${a.y}) rotate(${markerRotation(direction)})`}
          opacity={0.7}
        >
          <path d="M0,-10 L-6,4 L0,0 L6,4 Z" fill={draftColor} />
          <line
            x1={0}
            y1={0}
            x2={b.x - a.x}
            y2={b.y - a.y}
            stroke={draftColor}
            strokeDasharray="4 4"
          />
        </g>
      );
    }

    if (tool === "rectangle" && dragRect) {
      const { p1, p2 } = normalizeRect(dragRect.start, dragRect.end);
      const a = toPx(p1);
      const b = toPx(p2);
      if (!a || !b) return null;
      return (
        <rect
          x={Math.min(a.x, b.x)}
          y={Math.min(a.y, b.y)}
          width={Math.abs(b.x - a.x)}
          height={Math.abs(b.y - a.y)}
          stroke={draftColor}
          strokeDasharray="4 4"
          fill={draftColor}
          fillOpacity={draftFillOpacity}
        />
      );
    }

    if (
      (tool === "brush" || tool === "highlighter") &&
      brushDraftPoints.length >= 2
    ) {
      const path = brushDraftPoints
        .map((point, index) => {
          const px = toPx(point);
          if (!px) return null;
          return `${index === 0 ? "M" : "L"} ${px.x} ${px.y}`;
        })
        .filter((segment): segment is string => segment != null)
        .join(" ");
      if (!path) return null;
      return (
        <path
          d={path}
          fill="none"
          stroke={draftColor}
          strokeWidth={draftLineWidth}
          strokeOpacity={draftStrokeOpacity}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      );
    }

    if (!draftStart || !draftEnd) {
      if (tool === "pitchfork" && draftStart && stepRef.current === 1) {
        return renderLine(
          draftStart,
          hoverPoint ?? draftStart,
          draftColor,
          draftLineWidth,
          {
            dashed: true,
          },
        );
      }
      return null;
    }

    if (tool === "fibonacci" && draftStart && draftEnd) {
      return renderFibonacci(
        {
          id: "draft",
          type: "fibonacci",
          p1: draftStart,
          p2: draftEnd,
          color: draftColor,
        },
        false,
      );
    }

    if (tool === "fib-trend-ext" && draftStart && draftEnd) {
      return renderFibTrendExt(
        {
          id: "draft",
          type: "fib-trend-ext",
          p1: draftStart,
          p2: draftEnd,
          color: draftColor,
        },
        false,
      );
    }

    if (tool === "fib-time-zone" && draftStart && draftEnd) {
      return renderFibTimeZone(
        {
          id: "draft",
          type: "fib-time-zone",
          p1: draftStart,
          p2: draftEnd,
          color: draftColor,
        },
        false,
      );
    }

    if (tool === "gann-fan" && draftStart && draftEnd) {
      return renderGannFan(
        {
          id: "draft",
          type: "gann-fan",
          p1: draftStart,
          p2: draftEnd,
          color: draftColor,
        },
        false,
      );
    }

    if (tool === "gann-grid" && draftStart && draftEnd) {
      return renderGannGrid(
        {
          id: "draft",
          type: "gann-grid",
          p1: draftStart,
          p2: draftEnd,
          color: draftColor,
          fillOpacity: draftFillOpacity,
        },
        false,
      );
    }

    if (tool === "gann-square" && draftStart && draftEnd && chart && series) {
      const p2 = snapGannSquareP2(draftStart, draftEnd, chart, series);
      return renderGannSquare(
        {
          id: "draft",
          type: "gann-square",
          p1: draftStart,
          p2,
          color: draftColor,
          fillOpacity: draftFillOpacity,
        },
        false,
      );
    }

    if (TWO_POINT_DRAW_TOOLS.includes(tool)) {
      const dashed = true;
      if (tool === "ext-line") {
        return renderLine(draftStart, draftEnd, draftColor, draftLineWidth, {
          dashed,
          extendBoth: true,
        });
      }
      if (tool === "ray") {
        return renderLine(draftStart, draftEnd, draftColor, draftLineWidth, {
          dashed,
          extendRay: true,
        });
      }
      return renderLine(draftStart, draftEnd, draftColor, draftLineWidth, {
        dashed,
      });
    }

    if (tool === "channel") {
      if (stepRef.current >= 1) {
        const base = renderLine(
          draftStart,
          draftEnd,
          draftColor,
          draftLineWidth,
          {
            dashed: true,
          },
        );
        if (stepRef.current === 2 && hoverPoint) {
          const p4 = channelParallelEnd(draftStart, draftEnd, hoverPoint);
          const parallel = renderLine(
            hoverPoint,
            p4,
            draftColor,
            draftLineWidth,
            {
              dashed: true,
            },
          );
          return (
            <g>
              {base}
              {parallel}
            </g>
          );
        }
        return base;
      }
    }

    if (tool === "pitchfork" && chart && series && stepRef.current >= 1) {
      const base = renderLine(
        draftStart,
        draftEnd,
        draftColor,
        draftLineWidth,
        {
          dashed: true,
        },
      );
      if (stepRef.current === 2 && hoverPoint) {
        const preview = renderPitchfork(
          {
            id: "draft",
            type: "pitchfork",
            p1: draftStart,
            p2: draftEnd,
            p3: hoverPoint,
            color: draftColor,
          },
          false,
        );
        return (
          <g>
            {base}
            {preview}
          </g>
        );
      }
      return base;
    }

    return null;
  };

  const handleDoubleClick = useCallback(
    (px: number, py: number): boolean => {
      if (!canInteractWithDrawings(tool) || !chart || !container) return false;
      const containerW = container.clientWidth;
      for (let i = drawings.length - 1; i >= 0; i -= 1) {
        const drawing = drawings[i]!;
        if (!isDrawingVisible(drawing)) continue;
        if (
          hitTestDrawing(drawing, px, py, toPx, 12, containerW, chart, series)
        ) {
          onSelect(drawing.id);
          if (drawing.type === "text-label") {
            setInlineTextEditId(drawing.id);
            setInlineTextDraft(textOnChart(drawing));
            return true;
          }
          onOpenDrawingEditor?.(drawing.id);
          return true;
        }
      }
      return false;
    },
    [
      chart,
      container,
      drawings,
      onOpenDrawingEditor,
      onSelect,
      series,
      tool,
      toPx,
    ],
  );

  useEffect(() => {
    if (!container || !canInteractWithDrawings(tool)) return;

    const onDblClick = (event: MouseEvent) => {
      const coords = layerPointerPx(event.clientX, event.clientY);
      if (!coords) return;
      const handled = handleDoubleClick(coords.px, coords.py);
      if (handled) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      onBackgroundDoubleClick?.(event.clientX, event.clientY);
    };

    container.addEventListener("dblclick", onDblClick);
    return () => container.removeEventListener("dblclick", onDblClick);
  }, [
    container,
    handleDoubleClick,
    layerPointerPx,
    onBackgroundDoubleClick,
    tool,
  ]);

  const capturePointer = shouldCaptureDrawingPointer(
    tool,
    hoveringDrawing,
    interactionDragging,
  );

  useEffect(() => {
    onInteractionCaptureChange?.(layerHidden ? false : capturePointer);
  }, [capturePointer, layerHidden, onInteractionCaptureChange]);

  if (layerHidden) {
    return null;
  }

  return (
    <div
      ref={layerRef}
      className="absolute inset-0 z-10"
      style={{
        height,
        pointerEvents: capturePointer ? "auto" : "none",
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onDoubleClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        const coords = layerPointerPx(event.clientX, event.clientY);
        if (coords) {
          handleDoubleClick(coords.px, coords.py);
        }
      }}
    >
      <svg className="h-full w-full" style={{ pointerEvents: "none" }}>
        {drawings.map((drawing) => (
          <g key={drawing.id}>
            {renderDrawing(drawing)}
            {renderVertices(drawing)}
          </g>
        ))}
        {renderDraft()}
      </svg>

      {inlineTextEditId &&
        (() => {
          const drawing = drawings.find(
            (item): item is Extract<ChartDrawing, { type: "text-label" }> =>
              item.id === inlineTextEditId && item.type === "text-label",
          );
          if (!drawing) return null;
          const px = toPx(drawing.point);
          if (!px) return null;
          return (
            <textarea
              className="absolute z-20 min-w-[8rem] resize-none rounded border border-primary bg-card/95 px-1 py-0.5 text-foreground shadow-md outline-none"
              style={{
                left: px.x,
                top: px.y,
                fontSize: drawing.fontSize ?? DEFAULT_TEXT_FONT_SIZE,
                color: drawing.color,
              }}
              value={inlineTextDraft}
              autoFocus
              rows={2}
              onChange={(event) => setInlineTextDraft(event.target.value)}
              onBlur={commitInlineTextEdit}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  commitInlineTextEdit();
                }
                if (event.key === "Escape") {
                  setInlineTextEditId(null);
                  setInlineTextDraft("");
                }
              }}
              onPointerDown={(event) => event.stopPropagation()}
            />
          );
        })()}

      {canInteractWithDrawings(tool) &&
        selectedId &&
        !inlineTextEditId &&
        (() => {
          const drawing = drawings.find(
            (item): item is Extract<ChartDrawing, { type: "text-label" }> =>
              item.id === selectedId && item.type === "text-label",
          );
          if (!drawing) return null;
          const px = toPx(drawing.point);
          if (!px) return null;
          return (
            <div
              className="absolute z-20 flex items-center gap-1.5 rounded-md border border-border bg-card/95 px-2 py-1 shadow-md"
              style={{ left: px.x, top: Math.max(4, px.y - 34) }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <input
                type="color"
                title="Color"
                value={drawing.color}
                className="h-5 w-5 cursor-pointer border-0 bg-transparent p-0"
                onChange={(event) =>
                  onUpdate(drawing.id, {
                    color: event.target.value,
                    templateId: undefined,
                  })
                }
              />
              <input
                type="range"
                min={8}
                max={72}
                title="Tamaño"
                value={drawing.fontSize ?? DEFAULT_TEXT_FONT_SIZE}
                className="w-20"
                onChange={(event) =>
                  onUpdate(drawing.id, {
                    fontSize: Number(event.target.value),
                    templateId: undefined,
                  })
                }
              />
            </div>
          );
        })()}
    </div>
  );
}
