/**
 * Estrellas de idoneidad futura (coach / Finalistas).
 * Soporta medias estrellas (pasos de 0.5) en el rango 1–5.
 */

import { Star } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Valor de estrellas con medias permitidas (1, 1.5, …, 5). */
export type FutureStarsValue = number;

type Props = {
  stars: number;
  capped?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  /** Texto extra en title (p. ej. Finalista #1). */
  titlePrefix?: string;
};

/** Normaliza a [0, 5] en pasos de 0.5. */
export function normalizeFutureStars(stars: number): number {
  if (!Number.isFinite(stars) || stars <= 0) return 0;
  const clamped = Math.min(5, Math.max(0, stars));
  return Math.round(clamped * 2) / 2;
}

function formatStarsLabel(n: number): string {
  if (n <= 0) return 'Sin estrellas';
  const text = Number.isInteger(n) ? String(n) : n.toFixed(1);
  return `${text} de 5`;
}

function StarSlot({
  fill,
  px,
}: {
  fill: 'full' | 'half' | 'empty';
  px: string;
}) {
  if (fill === 'full') {
    return <Star className={cn(px, 'fill-amber-400 text-amber-500')} aria-hidden />;
  }
  if (fill === 'empty') {
    return <Star className={cn(px, 'fill-transparent text-muted-foreground/40')} aria-hidden />;
  }
  return (
    <span className={cn('relative inline-block', px)} aria-hidden>
      <Star className={cn(px, 'fill-transparent text-muted-foreground/40')} />
      <span className="absolute inset-0 overflow-hidden" style={{ width: '50%' }}>
        <Star className={cn(px, 'fill-amber-400 text-amber-500')} />
      </span>
    </span>
  );
}

export function BacktestFutureStars({
  stars,
  capped,
  size = 'md',
  className,
  titlePrefix,
}: Props) {
  const n = normalizeFutureStars(stars);
  const px = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  const label = formatStarsLabel(n);
  return (
    <div
      className={cn('inline-flex items-center gap-0.5', className)}
      title={
        titlePrefix
          ? `${titlePrefix} · ${label}${capped ? ' · techo evidencia' : ''}`
          : capped
            ? `${label} · techo por evidencia in-sample (máx. ★3)`
            : `${label} estrellas · sesgo de tendencia futura`
      }
      aria-label={`${titlePrefix ? `${titlePrefix}, ` : ''}${label} estrellas${capped ? ' (techo evidencia)' : ''}`}
    >
      {[1, 2, 3, 4, 5].map((i) => {
        let fill: 'full' | 'half' | 'empty' = 'empty';
        if (n >= i) fill = 'full';
        else if (n >= i - 0.5) fill = 'half';
        return <StarSlot key={i} fill={fill} px={px} />;
      })}
    </div>
  );
}
