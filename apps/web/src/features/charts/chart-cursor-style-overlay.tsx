import { useEffect, useReducer, useState } from "react";
import type { IChartApi, Time } from "lightweight-charts";
import {
  DEFAULT_CHART_DRAW_COLOR,
  DEFAULT_DOT_HALO_RADIUS,
  newChartDrawingId,
  semanticIdForDrawingType,
  type ChartDrawTool,
  type ChartDrawing,
} from "@bolsa/shared";
import {
  horzTimeToString,
  markerRotation,
  type ChartPriceSeries,
} from "@/features/charts/chart-drawing-utils";
import {
  isCursorArrowTool,
  usesCustomChartCursor,
} from "@/features/charts/chart-draw-tool-utils";

interface ChartCursorStyleOverlayProps {
  chart: IChartApi | null;
  series: ChartPriceSeries | null;
  container: HTMLDivElement | null;
  height: number;
  tool: ChartDrawTool;
  color?: string;
  onPlaceArrowMarker?: (drawing: ChartDrawing) => void;
}

export function ChartCursorStyleOverlay({
  chart,
  series,
  container,
  height,
  tool,
  color = DEFAULT_CHART_DRAW_COLOR,
  onPlaceArrowMarker,
}: ChartCursorStyleOverlayProps) {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const active = usesCustomChartCursor(tool);

  useEffect(() => {
    if (!active) {
      setPos(null);
    }
  }, [active, tool]);

  useEffect(() => {
    if (!chart || !active) return;

    const handler = (param: { point?: { x: number; y: number } }) => {
      if (!param.point) {
        setPos(null);
        return;
      }
      setPos({ x: param.point.x, y: param.point.y });
    };

    chart.subscribeCrosshairMove(handler);
    const redraw = () => bump();
    chart.timeScale().subscribeVisibleLogicalRangeChange(redraw);
    return () => {
      chart.unsubscribeCrosshairMove(handler);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(redraw);
    };
  }, [active, chart]);

  useEffect(() => {
    if (!chart || !series || tool !== "arrow" || !onPlaceArrowMarker) return;

    const handler = (param: {
      point?: { x: number; y: number };
      time?: Time;
    }) => {
      if (!param.point || param.time == null) return;
      const price = series.coordinateToPrice(param.point.y);
      if (price == null) return;
      const time = horzTimeToString(param.time);
      onPlaceArrowMarker({
        id: newChartDrawingId(),
        type: "arrow-marker",
        point: { time, price },
        direction: "up",
        color,
        semanticId: semanticIdForDrawingType("arrow-marker"),
      });
    };

    chart.subscribeClick(handler);
    return () => chart.unsubscribeClick(handler);
  }, [chart, color, onPlaceArrowMarker, series, tool]);

  if (!active || !container || !pos) return null;

  const width = container.clientWidth;

  return (
    <div
      className="pointer-events-none absolute inset-0 z-[12]"
      style={{ height }}
    >
      <svg className="h-full w-full" width={width} height={height}>
        {tool === "cross" && (
          <g
            stroke={color}
            strokeWidth={1.25}
            strokeDasharray="6 4"
            strokeOpacity={0.9}
          >
            <line x1={pos.x} y1={0} x2={pos.x} y2={height} />
            <line x1={0} y1={pos.y} x2={width} y2={pos.y} />
          </g>
        )}
        {tool === "dot" && (
          <circle
            cx={pos.x}
            cy={pos.y}
            r={4}
            fill={color}
            stroke={color}
            strokeWidth={1}
          />
        )}
        {tool === "dot-halo" && (
          <g>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={DEFAULT_DOT_HALO_RADIUS}
              fill={color}
              fillOpacity={0.22}
              stroke={color}
              strokeOpacity={0.45}
              strokeWidth={1}
            />
            <circle cx={pos.x} cy={pos.y} r={4} fill={color} />
          </g>
        )}
        {isCursorArrowTool(tool) && (
          <g
            transform={`translate(${pos.x}, ${pos.y}) rotate(${markerRotation("up")})`}
            fill={color}
          >
            <path d="M0,-10 L-6,4 L0,0 L6,4 Z" />
          </g>
        )}
      </svg>
    </div>
  );
}
