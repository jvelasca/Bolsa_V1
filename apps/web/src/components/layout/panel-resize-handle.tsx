import { useCallback, useRef } from 'react';
import { cn } from '@/lib/utils';

interface PanelResizeHandleProps {
  label: string;
  onDrag: (deltaPx: number) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  className?: string;
  orientation?: 'vertical' | 'horizontal';
  disabled?: boolean;
}

export function PanelResizeHandle({
  label,
  onDrag,
  onDragStart,
  onDragEnd,
  className,
  orientation = 'vertical',
  disabled = false,
}: PanelResizeHandleProps) {
  const lastRef = useRef(0);
  const isHorizontal = orientation === 'horizontal';

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (disabled || event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();

      const handle = event.currentTarget;
      handle.setPointerCapture(event.pointerId);
      lastRef.current = isHorizontal ? event.clientY : event.clientX;
      document.body.style.cursor = isHorizontal ? 'row-resize' : 'col-resize';
      document.body.style.userSelect = 'none';
      onDragStart?.();

      const onPointerMove = (moveEvent: PointerEvent) => {
        const current = isHorizontal ? moveEvent.clientY : moveEvent.clientX;
        const delta = current - lastRef.current;
        if (delta === 0) return;
        lastRef.current = current;
        onDrag(delta);
      };

      const pointerId = event.pointerId;

      const onPointerUp = () => {
        try {
          handle.releasePointerCapture(pointerId);
        } catch {
          /* pointer already released */
        }
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', onPointerUp);
        window.removeEventListener('pointercancel', onPointerUp);
        onDragEnd?.();
      };

      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp);
      window.addEventListener('pointercancel', onPointerUp);
    },
    [disabled, isHorizontal, onDrag, onDragEnd, onDragStart],
  );

  return (
    <div
      role="separator"
      aria-orientation={isHorizontal ? 'horizontal' : 'vertical'}
      aria-label={label}
      aria-disabled={disabled || undefined}
      title={disabled ? undefined : label}
      onPointerDown={onPointerDown}
      className={cn(
        'group relative shrink-0 touch-none select-none',
        isHorizontal ? 'h-px w-full bg-border' : 'w-px self-stretch bg-border',
        disabled
          ? 'pointer-events-none z-10'
          : cn(
              'z-30',
              isHorizontal
                ? 'cursor-row-resize hover:bg-primary/60 active:bg-primary/80'
                : 'cursor-col-resize hover:bg-primary/60 active:bg-primary/80',
              'before:absolute before:content-[""]',
              isHorizontal
                ? 'before:inset-x-0 before:-top-1.5 before:-bottom-1.5'
                : 'before:inset-y-0 before:-left-1.5 before:-right-1.5',
            ),
        className,
      )}
    />
  );
}
