/**
 * Pares etiqueta:valor tabulados al ancho del texto más largo (sin estirar a extremos).
 */

import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function KeyValueList({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <dl
      className={cn(
        'grid w-max max-w-full grid-cols-[max-content_minmax(0,max-content)] gap-x-2 gap-y-1.5 text-[11px]',
        className,
      )}
    >
      {children}
    </dl>
  );
}

export function KeyValueRow({
  label,
  children,
  valueClassName,
}: {
  label: string;
  children: ReactNode;
  valueClassName?: string;
}) {
  return (
    <>
      <dt className="whitespace-nowrap text-muted-foreground after:ml-0 after:content-[':']">
        {label}
      </dt>
      <dd className={cn('min-w-0 break-words tabular-nums text-foreground', valueClassName)}>
        {children}
      </dd>
    </>
  );
}
