/**
 * A2 · Celda de dictamen de Asesor (Cartera, Análisis y Diario).
 *
 * Presentacional: no mide, no recalcula la postura y no formatea a mano. Delega
 * en `OperativaDictamenBlock` con `variant="cell"` para que las tres superficies
 * lean la misma etiqueta, el mismo detalle por causa, la misma confianza, las
 * mismas ★ y los mismos motivos.
 *
 * «Midiendo…» y «Sin dictamen» son estados distintos: mientras una fuente
 * carga, la celda no afirma que no haya dictamen.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import {
  OperativaDictamenBlock,
  type OperativaDictamenInputV1,
} from "@/features/trading/operativa-dictamen";

export function AsesorDictamenCell({
  opinion,
  loading = false,
  emptyLabel,
  className,
  children,
}: {
  /** Dictamen completo o entrada mínima tipada; `null` = ausencia declarada. */
  opinion: OperativaDictamenInputV1 | null | undefined;
  /** `true` mientras la fuente se está midiendo y aún no hay opinión. */
  loading?: boolean;
  /** Texto honesto para la ausencia (p. ej. «Sin dictamen»). */
  emptyLabel: string;
  className?: string;
  /** Chips propios del panel (riesgo, veto/aviso…). */
  children?: ReactNode;
}) {
  if (loading && !opinion) {
    return (
      <p
        className={cn("text-[11px] text-muted-foreground", className)}
        data-testid="asesor-dictamen-cell"
        data-state="midiendo"
      >
        Midiendo…
      </p>
    );
  }

  if (!opinion) {
    return (
      <p
        className={cn("text-[11px] text-muted-foreground", className)}
        data-testid="asesor-dictamen-cell"
        data-state="ausente"
      >
        {emptyLabel}
      </p>
    );
  }

  return (
    <OperativaDictamenBlock
      opinion={opinion}
      variant="cell"
      className={className}
    >
      {children}
    </OperativaDictamenBlock>
  );
}
