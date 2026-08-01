/**
 * ResizeObserver con debounce y umbral mínimo para evitar bucles de layout.
 */
export function observeStableSize(
  element: HTMLElement,
  onSize: (width: number, height: number) => void,
  options?: { minDeltaPx?: number; debounceMs?: number },
): () => void {
  const minDelta = options?.minDeltaPx ?? 2;
  const debounceMs = options?.debounceMs ?? 32;
  let lastW = 0;
  let lastH = 0;
  let timer = 0;

  const flush = () => {
    timer = 0;
    const { width, height } = element.getBoundingClientRect();
    const w = Math.floor(width);
    const h = Math.floor(height);
    if (Math.abs(w - lastW) < minDelta && Math.abs(h - lastH) < minDelta) return;
    lastW = w;
    lastH = h;
    onSize(w, h);
  };

  const observer = new ResizeObserver(() => {
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(flush, debounceMs);
  });

  observer.observe(element);
  flush();

  return () => {
    observer.disconnect();
    if (timer) window.clearTimeout(timer);
  };
}
