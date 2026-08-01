import { useEffect, useReducer, useRef } from 'react';
import type { IChartApi, Time } from 'lightweight-charts';

import { formatChartTimeAxisLabel } from '@/features/charts/chart-utils';

interface ChartTimeAxisLabelProps {
  chart: IChartApi | null;
  container: HTMLDivElement | null;
  enabled: boolean;
  showTime: boolean;
}

export function ChartTimeAxisLabel({
  chart,
  container,
  enabled,
  showTime,
}: ChartTimeAxisLabelProps) {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const labelRef = useRef<{ x: number; text: string } | null>(null);
  const showTimeRef = useRef(showTime);
  showTimeRef.current = showTime;

  useEffect(() => {
    if (!enabled || !chart || !container) {
      labelRef.current = null;
      bump();
      return;
    }

    const clear = () => {
      if (labelRef.current !== null) {
        labelRef.current = null;
        bump();
      }
    };

    const showAt = (x: number, time: Time | null | undefined) => {
      if (time == null) {
        clear();
        return;
      }
      const text = formatChartTimeAxisLabel(time, showTimeRef.current);
      labelRef.current = { x, text };
      bump();
    };

    const onMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const localX = event.clientX - rect.left;
      const localY = event.clientY - rect.top;
      if (localX < 0 || localY < 0 || localX > rect.width || localY > rect.height) {
        clear();
        return;
      }
      showAt(localX, chart.timeScale().coordinateToTime(localX));
    };

    const onCrosshairMove = (param: { point?: { x: number; y: number }; time?: Time }) => {
      if (!param.point || param.time == null) return;
      showAt(param.point.x, param.time);
    };

    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseleave', clear);
    chart.subscribeCrosshairMove(onCrosshairMove);
    const onRangeChange = () => bump();
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRangeChange);

    return () => {
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mouseleave', clear);
      chart.unsubscribeCrosshairMove(onCrosshairMove);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRangeChange);
    };
  }, [chart, container, enabled, showTime]);

  const label = labelRef.current;
  if (!enabled || !label) return null;

  return (
    <div
      className="pointer-events-none absolute z-[8] whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums shadow-md"
      style={{
        left: label.x,
        bottom: 4,
        transform: 'translateX(-50%)',
        backgroundColor: 'hsl(var(--popover))',
        color: 'hsl(var(--popover-foreground))',
        border: '1px solid hsl(var(--border))',
      }}
    >
      {label.text}
    </div>
  );
}
