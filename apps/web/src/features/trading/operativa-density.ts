/**
 * Densidad tipográfica de DECISIÓN.
 *
 * `compact` es la escala histórica del panel (9/10/11 px) y sigue siendo la de
 * la ventana maximizada y la estrecha. `dock` es la del rail derecho minimizado:
 * el grupo plegado deja respirar el contenido y la letra sube a 11/11/12 px
 * para que se lea sin ampliar la ventana.
 *
 * No cambia contenido ni jerarquía: el mismo texto, con otra escala.
 */

export type OperativaDensity = "compact" | "dock";

/** Micro = etiquetas y metadatos · caption = cuerpo secundario · body = lectura. */
export const OPERATIVA_TEXT: Record<
  OperativaDensity,
  { micro: string; caption: string; body: string }
> = {
  compact: {
    micro: "text-[9px]",
    caption: "text-[10px]",
    body: "text-[11px]",
  },
  dock: {
    micro: "text-[11px]",
    caption: "text-[11px]",
    body: "text-xs",
  },
};
