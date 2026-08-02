/**
 * Pares etiqueta:valor. `columns={1}` = tabla compacta; `2|3` = rejilla responsive
 * que aprovecha el ancho del panel (p. ej. Resumen en Instrumentos).
 */

import { createContext, useContext, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

const KeyValueColumnsContext = createContext<1 | 2 | 3>(1);

export function KeyValueList({
  children,
  className,
  columns = 1,
}: {
  children: ReactNode;
  className?: string;
  /** 1 = etiqueta|valor en bloque; 2|3 = pares en rejilla responsive. */
  columns?: 1 | 2 | 3;
}) {
  if (columns === 1) {
    return (
      <KeyValueColumnsContext.Provider value={1}>
        <dl
          className={cn(
            'grid w-max max-w-full grid-cols-[max-content_minmax(0,max-content)] gap-x-2 gap-y-1.5 text-[11px]',
            className,
          )}
        >
          {children}
        </dl>
      </KeyValueColumnsContext.Provider>
    );
  }

  return (
    <KeyValueColumnsContext.Provider value={columns}>
      <div
        className={cn(
          'grid w-full gap-x-4 gap-y-1.5 text-[11px]',
          columns === 2 && 'grid-cols-1 min-[360px]:grid-cols-2',
          columns === 3 &&
            'grid-cols-1 min-[360px]:grid-cols-2 min-[560px]:grid-cols-3',
          className,
        )}
        role="list"
      >
        {children}
      </div>
    </KeyValueColumnsContext.Provider>
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
  const columns = useContext(KeyValueColumnsContext);

  if (columns === 1) {
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

  return (
    <div
      role="listitem"
      className="grid min-w-0 grid-cols-[max-content_minmax(0,1fr)] gap-x-2"
    >
      <span className="whitespace-nowrap text-muted-foreground after:ml-0 after:content-[':']">
        {label}
      </span>
      <span
        className={cn('min-w-0 break-words tabular-nums text-foreground', valueClassName)}
      >
        {children}
      </span>
    </div>
  );
}
