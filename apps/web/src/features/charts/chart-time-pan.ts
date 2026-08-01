import { PRICE_SCALE_HIT_WIDTH_PX } from '@/features/charts/chart-scale-utils';

const AXIS_LOCK_PX = 5;

export interface ChartTimePanOptions {
  hitTarget: HTMLElement;
  captureTarget: HTMLElement;
  onHorizontalPan: (deltaPx: number) => void;
  isDisabled?: () => boolean;
}

/**
 * Arrastre horizontal con botón pulsado: desplaza el eje temporal (sincroniza todos los paneles).
 */
export function attachChartTimePan({
  hitTarget,
  captureTarget,
  onHorizontalPan,
  isDisabled,
}: ChartTimePanOptions): () => void {
  let dragging = false;
  let startX = 0;
  let lastX = 0;

  const endDrag = () => {
    dragging = false;
    window.removeEventListener('pointermove', onWindowMove);
    window.removeEventListener('pointerup', onWindowUp);
    window.removeEventListener('pointercancel', onWindowUp);
  };

  const onWindowMove = (event: PointerEvent) => {
    if (!dragging || !(event.buttons & 1)) return;
    const dx = event.clientX - lastX;
    const totalDx = event.clientX - startX;
    if (Math.abs(totalDx) < AXIS_LOCK_PX) return;
    if (dx !== 0) {
      event.preventDefault();
      onHorizontalPan(dx);
      lastX = event.clientX;
    }
  };

  const onWindowUp = (event: PointerEvent) => {
    if (!dragging) return;
    event.preventDefault();
    endDrag();
  };

  const onPointerDown = (event: PointerEvent) => {
    if (event.button !== 0 || isDisabled?.()) return;

    const rect = hitTarget.getBoundingClientRect();
    const onScale = event.clientX >= rect.right - PRICE_SCALE_HIT_WIDTH_PX;
    if (onScale) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    dragging = true;
    startX = event.clientX;
    lastX = event.clientX;

    window.addEventListener('pointermove', onWindowMove);
    window.addEventListener('pointerup', onWindowUp);
    window.addEventListener('pointercancel', onWindowUp);
  };

  const capture = { capture: true };
  captureTarget.addEventListener('pointerdown', onPointerDown, capture);

  return () => {
    endDrag();
    captureTarget.removeEventListener('pointerdown', onPointerDown, capture);
  };
}
