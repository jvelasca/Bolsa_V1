import { PRICE_SCALE_HIT_WIDTH_PX } from "@/features/charts/chart-scale-utils";

export interface ChartScaleZoomHandlers {
  onVerticalZoom: (direction: "in" | "out") => void;
  onVerticalZoomCommit?: () => void;
  onVolumeZoom?: (direction: "in" | "out") => void;
  onVolumeZoomCommit?: () => void;
}

export interface ChartScaleInteractionOptions {
  hitTarget: HTMLElement;
  captureTarget: HTMLElement;
  handlers: { current: ChartScaleZoomHandlers };
  volumeBandPct?: number;
}

function isOverRightScale(rect: DOMRect, clientX: number): boolean {
  return clientX >= rect.right - PRICE_SCALE_HIT_WIDTH_PX;
}

function isOverVolumeBand(
  rect: DOMRect,
  clientY: number,
  volumeBandPct: number,
): boolean {
  return (
    volumeBandPct > 0 && clientY >= rect.bottom - rect.height * volumeBandPct
  );
}

/**
 * Zoom vertical con rueda + botón pulsado sobre la escala Y.
 * El arrastre en escala lo gestiona attachChartPricePan.
 */
export function attachChartScaleInteraction({
  hitTarget,
  captureTarget,
  handlers,
  volumeBandPct = 0,
}: ChartScaleInteractionOptions): () => void {
  const onWheel = (event: WheelEvent) => {
    if (!(event.buttons & 1)) return;

    const rect = hitTarget.getBoundingClientRect();
    const onVolume = isOverVolumeBand(rect, event.clientY, volumeBandPct);
    const onScale = isOverRightScale(rect, event.clientX);
    if (!onScale) return;

    event.preventDefault();
    event.stopPropagation();

    if (onVolume && handlers.current.onVolumeZoom) {
      handlers.current.onVolumeZoom(event.deltaY < 0 ? "in" : "out");
      handlers.current.onVolumeZoomCommit?.();
      return;
    }

    if (!onVolume) {
      handlers.current.onVerticalZoom(event.deltaY < 0 ? "in" : "out");
      handlers.current.onVerticalZoomCommit?.();
    }
  };

  captureTarget.addEventListener("wheel", onWheel, { passive: false });

  return () => {
    captureTarget.removeEventListener("wheel", onWheel);
  };
}

/** Arrastre vertical en escala Y (solo sub-paneles; sin pan temporal). */
export function attachChartScaleDrag({
  hitTarget,
  captureTarget,
  handlers,
}: Omit<ChartScaleInteractionOptions, "volumeBandPct">): () => void {
  let scalePointerDown = false;
  let lastPointerY = 0;
  let moved = false;

  const endWindowDrag = () => {
    window.removeEventListener("pointermove", onWindowPointerMove);
    window.removeEventListener("pointerup", onWindowPointerUp);
    window.removeEventListener("pointercancel", onWindowPointerUp);
    if (scalePointerDown && moved) handlers.current.onVerticalZoomCommit?.();
    scalePointerDown = false;
    moved = false;
  };

  const onWindowPointerMove = (event: PointerEvent) => {
    if (!scalePointerDown || !(event.buttons & 1)) return;
    const delta = event.clientY - lastPointerY;
    if (Math.abs(delta) < 2) return;
    event.preventDefault();
    handlers.current.onVerticalZoom(delta < 0 ? "in" : "out");
    lastPointerY = event.clientY;
    moved = true;
  };

  const onWindowPointerUp = () => endWindowDrag();

  const onPointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return;
    const rect = hitTarget.getBoundingClientRect();
    if (!isOverRightScale(rect, event.clientX)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    scalePointerDown = true;
    moved = false;
    lastPointerY = event.clientY;
    window.addEventListener("pointermove", onWindowPointerMove);
    window.addEventListener("pointerup", onWindowPointerUp);
    window.addEventListener("pointercancel", onWindowPointerUp);
  };

  const capture = { capture: true };
  captureTarget.addEventListener("pointerdown", onPointerDown, capture);

  return () => {
    endWindowDrag();
    captureTarget.removeEventListener("pointerdown", onPointerDown, capture);
  };
}
