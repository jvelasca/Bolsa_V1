/**
 * V2.47 — primer slice móvil de la cabina de trading (DECISIÓN / AUTO / Confirm).
 *
 * Contexto honesto de la deuda: los componentes de mayor valor de la cabina
 * (`operativa-cockpit-card`, `auto-desk-panel`, `decision-explain-panel`,
 * `entry-operating-summary`, `f3-protect-stop-block`, `exit-route-view`) no tenían
 * NI UN SOLO `sm:`/`md:`/`lg:`: se diseñaron para el dock DECISIÓN de escritorio
 * (260–420 px) y se rompían por apilado forzado al llegar a un teléfono.
 *
 * Este slice NO reordena prestaciones (regla 2 de `docs/RESPONSIVE_PREMISES.md`:
 * nada se elimina en estrecho): solo cambia CÓMO se apilan las mismas filas y
 * controles. Dos mecanismos, cada uno en su sitio:
 *
 * 1. Filas etiqueta→valor: `flex-wrap` en ancho (si no cabe, el valor cae a la
 *    línea siguiente en vez de comprimirse) y apilado real en estrecho.
 *    Ancho-agnóstico: cubre también el dock a 260 px sin medir el viewport.
 * 2. Estructura por viewport (este módulo): teléfono ⇒ una columna, valores
 *    alineados a la izquierda, tipografía al suelo legible y objetivos táctiles.
 *
 * Residual declarado (no cerrado aquí): el ancho REAL del dock DECISIÓN en
 * escritorio (260–420 px) se mide en píxeles de componente, no de viewport; su
 * cierre corresponde a una capa de *container queries* como la del workspace de
 * gráficos (`docs/CHART_RESPONSIVE.md`), no a este hook.
 */

import { useMediaQuery } from "@/lib/use-media-query";

/** Teléfono / ventana estrecha: por debajo del `sm` de Tailwind (640 px). */
export const CABIN_NARROW_QUERY = "(max-width: 640px)";

export type CabinWidth = "narrow" | "wide";

/** Marcador estable para test y QA: el layout no se adivina, se declara. */
export function cabinWidth(narrow: boolean): CabinWidth {
  return narrow ? "narrow" : "wide";
}

export function useNarrowCabin(): boolean {
  return useMediaQuery(CABIN_NARROW_QUERY);
}

/**
 * Fila etiqueta→valor compartida por la cabina.
 * · ancho: una línea, `justify-between`, con `flex-wrap` como red de seguridad.
 * · estrecho: etiqueta arriba, valor debajo alineado a la izquierda (nada de
 *   columnas de 90 px peleando por el mismo renglón).
 */
export function cabinRowClass(narrow: boolean): string {
  return narrow
    ? "flex flex-col items-start gap-0.5"
    : "flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5";
}

/** Alineación del valor dentro de la fila: derecha en ancho, izquierda al apilar. */
export function cabinRowValueClass(narrow: boolean): string {
  return narrow ? "text-left" : "text-right";
}
