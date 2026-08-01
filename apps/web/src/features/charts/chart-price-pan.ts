import { PRICE_SCALE_HIT_WIDTH_PX } from '@/features/charts/chart-scale-utils';
import type { ChartScaleZoomHandlers } from '@/features/charts/chart-scale-wheel';

export interface ChartPricePanHandlers {
  onHorizontalPan: (deltaPx: number) => void;
  onPriceVerticalPan: (deltaPx: number, chartHeight: number) => void;
  onPanCommit?: () => void;
}

export interface ChartPricePanOptions {
  hitTarget: HTMLElement;
  captureTarget: HTMLElement;
  panHandlers: { current: ChartPricePanHandlers };
  scaleHandlers?: { current: ChartScaleZoomHandlers };
  volumeBandPct?: number;
  isDisabled?: () => boolean;
}

type DragMode = 'none' | 'pending' | 'time' | 'price-y' | 'scale-y' | 'volume-y';

const AXIS_LOCK_PX = 5;
const ZOOM_STEP_PX = 2;

function isOverRightScale(rect: DOMRect, clientX: number): boolean {
  return clientX >= rect.right - PRICE_SCALE_HIT_WIDTH_PX;
}

function isOverVolumeBand(rect: DOMRect, clientY: number, volumeBandPct: number): boolean {
  return volumeBandPct > 0 && clientY >= rect.bottom - rect.height * volumeBandPct;
}

/**
 * Arrastre con botón pulsado (estilo XTB) en el gráfico de precio:
 * - Horizontal → desplaza el tiempo (sincroniza sub-paneles).
 * - Vertical en el cuerpo → desplaza solo el eje de precio.
 * - Vertical en la escala derecha → zoom Y (precio o volumen).
 */
export function attachChartPricePan({
  hitTarget,
  captureTarget,
  panHandlers,
  scaleHandlers,
  volumeBandPct = 0,
  isDisabled,
}: ChartPricePanOptions): () => void {
  let dragMode: DragMode = 'none';
  let pointerDownOnScale = false;
  let pointerDownOnVolume = false;
  let startX = 0;
  let startY = 0;
  let lastX = 0;
  let lastY = 0;
  let lastZoomY = 0;
  let moved = false;
  let zoomedDuringDrag = false;

  const endWindowDrag = () => {
    window.removeEventListener('pointermove', onWindowPointerMove);
    window.removeEventListener('pointerup', onWindowPointerUp);
    window.removeEventListener('pointercancel', onWindowPointerUp);
    if (dragMode !== 'none' && (moved || zoomedDuringDrag)) {
      panHandlers.current.onPanCommit?.();
      if (zoomedDuringDrag) {
        if (dragMode === 'volume-y') scaleHandlers?.current.onVolumeZoomCommit?.();
        else if (dragMode === 'scale-y') scaleHandlers?.current.onVerticalZoomCommit?.();
      }
    }
    dragMode = 'none';
    pointerDownOnScale = false;
    pointerDownOnVolume = false;
    moved = false;
    zoomedDuringDrag = false;
  };

  const zoomFromPointerY = (clientY: number, volume: boolean) => {
    const delta = clientY - lastZoomY;
    if (Math.abs(delta) < ZOOM_STEP_PX) return;
    const direction = delta < 0 ? 'in' : 'out';
    if (volume) scaleHandlers?.current.onVolumeZoom?.(direction);
    else scaleHandlers?.current.onVerticalZoom(direction);
    lastZoomY = clientY;
    zoomedDuringDrag = true;
  };

  const resolveDragMode = (clientX: number, clientY: number) => {
    const dx = clientX - startX;
    const dy = clientY - startY;
    if (Math.abs(dx) < AXIS_LOCK_PX && Math.abs(dy) < AXIS_LOCK_PX) return;

    const horizontal = Math.abs(dx) >= Math.abs(dy);
    if (horizontal) {
      dragMode = 'time';
      return;
    }

    if (pointerDownOnScale) {
      dragMode = pointerDownOnVolume ? 'volume-y' : 'scale-y';
      lastZoomY = clientY;
      return;
    }

    dragMode = 'price-y';
  };

  const onWindowPointerMove = (event: PointerEvent) => {
    if (dragMode === 'none' || !(event.buttons & 1)) return;

    if (dragMode === 'pending') {
      resolveDragMode(event.clientX, event.clientY);
      if (dragMode === 'pending') return;
      lastX = event.clientX;
      lastY = event.clientY;
    }

    event.preventDefault();

    if (dragMode === 'time') {
      const deltaX = event.clientX - lastX;
      if (deltaX !== 0) {
        panHandlers.current.onHorizontalPan(deltaX);
        lastX = event.clientX;
        moved = true;
      }
      return;
    }

    if (dragMode === 'price-y') {
      const deltaY = event.clientY - lastY;
      if (deltaY !== 0) {
        const height = hitTarget.getBoundingClientRect().height;
        panHandlers.current.onPriceVerticalPan(deltaY, height);
        lastY = event.clientY;
        moved = true;
      }
      return;
    }

    if (dragMode === 'scale-y' || dragMode === 'volume-y') {
      zoomFromPointerY(event.clientY, dragMode === 'volume-y');
    }
  };

  const onWindowPointerUp = (event: PointerEvent) => {
    if (dragMode === 'none') return;
    event.preventDefault();
    endWindowDrag();
  };

  const onPointerDown = (event: PointerEvent) => {
    if (event.button !== 0 || isDisabled?.()) return;

    const rect = hitTarget.getBoundingClientRect();
    pointerDownOnScale = isOverRightScale(rect, event.clientX);
    pointerDownOnVolume =
      pointerDownOnScale && isOverVolumeBand(rect, event.clientY, volumeBandPct);

    event.preventDefault();
    event.stopImmediatePropagation();

    dragMode = 'pending';
    startX = event.clientX;
    startY = event.clientY;
    lastX = event.clientX;
    lastY = event.clientY;
    lastZoomY = event.clientY;
    moved = false;
    zoomedDuringDrag = false;

    window.addEventListener('pointermove', onWindowPointerMove);
    window.addEventListener('pointerup', onWindowPointerUp);
    window.addEventListener('pointercancel', onWindowPointerUp);
  };

  const capture = { capture: true };
  captureTarget.addEventListener('pointerdown', onPointerDown, capture);

  return () => {
    endWindowDrag();
    captureTarget.removeEventListener('pointerdown', onPointerDown, capture);
  };
}
